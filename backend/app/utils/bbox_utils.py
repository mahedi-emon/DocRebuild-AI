"""
Bounding Box Utilities — Coordinate math, normalization, and matching.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BBox:
    """Axis-aligned bounding box with (x1, y1, x2, y2) coordinates."""
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    def to_tuple(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    def intersects(self, other: "BBox") -> bool:
        return not (
            self.x2 <= other.x1
            or self.x1 >= other.x2
            or self.y2 <= other.y1
            or self.y1 >= other.y2
        )

    def iou(self, other: "BBox") -> float:
        """Intersection over Union."""
        ix1 = max(self.x1, other.x1)
        iy1 = max(self.y1, other.y1)
        ix2 = min(self.x2, other.x2)
        iy2 = min(self.y2, other.y2)

        intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        union = self.area + other.area - intersection

        return intersection / union if union > 0 else 0.0

    def contains(self, other: "BBox") -> bool:
        return (
            self.x1 <= other.x1
            and self.y1 <= other.y1
            and self.x2 >= other.x2
            and self.y2 >= other.y2
        )

    def expand(self, padding: float) -> "BBox":
        return BBox(
            self.x1 - padding,
            self.y1 - padding,
            self.x2 + padding,
            self.y2 + padding,
        )

    def normalize(self, width: float, height: float) -> "BBox":
        """Normalize coordinates to [0, 1] range."""
        return BBox(
            self.x1 / width,
            self.y1 / height,
            self.x2 / width,
            self.y2 / height,
        )

    def denormalize(self, width: float, height: float) -> "BBox":
        """Convert normalized [0, 1] coordinates back to pixel coordinates."""
        return BBox(
            self.x1 * width,
            self.y1 * height,
            self.x2 * width,
            self.y2 * height,
        )

    @classmethod
    def from_points(cls, points: list[list[float]]) -> "BBox":
        """Create BBox from a polygon (list of [x, y] points)."""
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return cls(min(xs), min(ys), max(xs), max(ys))


def nms(boxes: list[tuple[BBox, float, str]], iou_threshold: float = 0.5) -> list[tuple[BBox, float, str]]:
    """
    Non-Maximum Suppression.

    Args:
        boxes: List of (bbox, confidence, label) tuples
        iou_threshold: IoU threshold for suppression

    Returns:
        Filtered list of boxes after NMS
    """
    if not boxes:
        return []

    # Sort by confidence (descending)
    boxes = sorted(boxes, key=lambda x: x[1], reverse=True)
    selected = []

    while boxes:
        best = boxes.pop(0)
        selected.append(best)

        remaining = []
        for box in boxes:
            if best[0].iou(box[0]) < iou_threshold:
                remaining.append(box)
        boxes = remaining

    return selected


def match_boxes(
    boxes_a: list[BBox],
    boxes_b: list[BBox],
    iou_threshold: float = 0.3,
) -> list[tuple[int, int, float]]:
    """
    Match bounding boxes between two lists using IoU.

    Returns:
        List of (index_a, index_b, iou_score) tuples for matched pairs.
    """
    matches = []
    used_b = set()

    for i, box_a in enumerate(boxes_a):
        best_j = -1
        best_iou = 0.0

        for j, box_b in enumerate(boxes_b):
            if j in used_b:
                continue
            iou = box_a.iou(box_b)
            if iou > best_iou and iou >= iou_threshold:
                best_iou = iou
                best_j = j

        if best_j >= 0:
            matches.append((i, best_j, best_iou))
            used_b.add(best_j)

    return matches


def sort_reading_order(boxes: list[BBox], column_threshold: float = 0.3) -> list[int]:
    """
    Sort bounding boxes in reading order (top-to-bottom, left-to-right).
    Handles multi-column layouts by detecting column boundaries.

    Returns:
        List of indices in reading order.
    """
    if not boxes:
        return []

    # Detect columns by clustering x-centers
    centers = [(i, box.center[0], box.center[1]) for i, box in enumerate(boxes)]

    # Simple column detection: sort by y first, then x within same row band
    page_width = max(b.x2 for b in boxes) if boxes else 1
    row_height = min(b.height for b in boxes) * 1.5 if boxes else 50

    # Group into rows (boxes with similar y-centers)
    rows: list[list[tuple[int, float, float]]] = []
    sorted_by_y = sorted(centers, key=lambda c: c[2])

    current_row = [sorted_by_y[0]]
    for center in sorted_by_y[1:]:
        if abs(center[2] - current_row[0][2]) < row_height:
            current_row.append(center)
        else:
            rows.append(current_row)
            current_row = [center]
    rows.append(current_row)

    # Sort each row by x-coordinate
    result = []
    for row in rows:
        sorted_row = sorted(row, key=lambda c: c[1])
        result.extend(idx for idx, _, _ in sorted_row)

    return result
