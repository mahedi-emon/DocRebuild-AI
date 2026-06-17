"""
DocLayout-YOLO Engine — Layout detection using YOLO-based model.

Detects document elements: title, paragraph, table, figure, caption,
equation, list, header, footer, page_number.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

from app.utils.bbox_utils import BBox

logger = logging.getLogger(__name__)

# DocLayout-YOLO class mapping
DOCLAYOUT_CLASSES = {
    0: "title",
    1: "plain_text",
    2: "abandon",
    3: "figure",
    4: "figure_caption",
    5: "table",
    6: "table_caption",
    7: "table_footnote",
    8: "isolate_formula",
    9: "formula_caption",
}


class DocLayoutYOLOEngine:
    """DocLayout-YOLO layout detection engine."""

    def __init__(self, model_path: str | None = None):
        self._model_path = model_path
        self._model = None
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            from doclayout_yolo import YOLO

            if self._model_path:
                self._model = YOLO(self._model_path)
            else:
                # Use default pre-trained model
                from huggingface_hub import hf_hub_download

                model_path = hf_hub_download(
                    repo_id="juliozhao/DocLayout-YOLO-DocStructBench",
                    filename="doclayout_yolo_docstructbench_imgsz1024.pt",
                )
                self._model = YOLO(model_path)

            self._initialized = True
            logger.info("DocLayout-YOLO initialized")
        except ImportError as e:
            raise ImportError(f"DocLayout-YOLO not available: {e}")

    def detect(self, image: np.ndarray) -> list[dict]:
        """
        Detect layout elements in an image.

        Returns:
            List of dicts with 'type', 'bbox', 'confidence' keys
        """
        self.initialize()
        start_time = time.time()

        results = self._model.predict(image, imgsz=1024, conf=0.2, iou=0.45)

        elements = []
        if results and len(results) > 0:
            result = results[0]
            boxes = result.boxes

            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i])
                conf = float(boxes.conf[i])
                xyxy = boxes.xyxy[i].cpu().numpy()

                element_type = DOCLAYOUT_CLASSES.get(cls_id, "unknown")

                # Map to our standard types
                type_mapping = {
                    "plain_text": "paragraph",
                    "figure": "image",
                    "figure_caption": "caption",
                    "table_caption": "caption",
                    "isolate_formula": "equation",
                    "formula_caption": "caption",
                    "table_footnote": "paragraph",
                    "abandon": "unknown",
                }
                standard_type = type_mapping.get(element_type, element_type)

                elements.append({
                    "type": standard_type,
                    "bbox": [float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])],
                    "confidence": conf,
                    "engine": "doclayout_yolo",
                    "raw_type": element_type,
                })

        elapsed = (time.time() - start_time) * 1000
        logger.info(f"DocLayout-YOLO detected {len(elements)} elements in {elapsed:.0f}ms")
        return elements

    def cleanup(self) -> None:
        self._model = None
        self._initialized = False
