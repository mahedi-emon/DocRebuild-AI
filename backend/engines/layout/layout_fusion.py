"""
Layout Fusion Engine — Merges layout predictions from multiple engines.

Uses Non-Maximum Suppression across engines and confidence-weighted
voting for element type classification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.utils.bbox_utils import BBox, nms, sort_reading_order

logger = logging.getLogger(__name__)


@dataclass
class LayoutElement:
    """A detected layout element with type, position, and confidence."""
    element_type: str
    bbox: BBox
    confidence: float
    reading_order: int = 0
    source_engine: str = ""
    children: list["LayoutElement"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type": self.element_type,
            "bbox": list(self.bbox.to_tuple()),
            "confidence": self.confidence,
            "reading_order": self.reading_order,
            "source": self.source_engine,
        }


@dataclass
class PageLayout:
    """Complete layout structure for a single page."""
    elements: list[LayoutElement] = field(default_factory=list)
    width: int = 0
    height: int = 0
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "confidence": self.confidence,
            "element_count": len(self.elements),
            "elements": [e.to_dict() for e in self.elements],
        }


class LayoutFusionEngine:
    """Fuses layout predictions from multiple layout analysis engines."""

    def __init__(self, iou_threshold: float = 0.5):
        self._iou_threshold = iou_threshold

    def fuse(
        self,
        predictions: list[list[dict]],
        image_width: int,
        image_height: int,
    ) -> PageLayout:
        """
        Fuse layout predictions from multiple engines.

        Args:
            predictions: List of prediction lists from different engines.
                Each prediction: {'type': str, 'bbox': [x1,y1,x2,y2], 'confidence': float}
            image_width: Page image width
            image_height: Page image height

        Returns:
            Fused PageLayout with reading-order-sorted elements
        """
        # Collect all detections
        all_boxes: list[tuple[BBox, float, str]] = []
        for engine_preds in predictions:
            for pred in engine_preds:
                bbox = BBox(*pred["bbox"])
                confidence = pred["confidence"]
                element_type = pred["type"]
                all_boxes.append((bbox, confidence, element_type))

        if not all_boxes:
            return PageLayout(width=image_width, height=image_height)

        # Apply NMS across all engines
        filtered = nms(all_boxes, iou_threshold=self._iou_threshold)

        # Create LayoutElements
        elements = []
        for bbox, confidence, element_type in filtered:
            element = LayoutElement(
                element_type=element_type,
                bbox=bbox,
                confidence=confidence,
            )
            elements.append(element)

        # Sort by reading order
        bboxes = [e.bbox for e in elements]
        order = sort_reading_order(bboxes)

        sorted_elements = []
        for idx, order_idx in enumerate(order):
            element = elements[order_idx]
            element.reading_order = idx
            sorted_elements.append(element)

        # Calculate overall confidence
        overall_confidence = (
            sum(e.confidence for e in sorted_elements) / len(sorted_elements)
            if sorted_elements
            else 0.0
        )

        layout = PageLayout(
            elements=sorted_elements,
            width=image_width,
            height=image_height,
            confidence=overall_confidence,
        )

        logger.info(
            f"Layout fusion: {len(sorted_elements)} elements, "
            f"confidence={overall_confidence:.3f}"
        )
        return layout
