"""
Image Utilities — Preprocessing, cropping, and comparison helpers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image


def load_image(path: str) -> np.ndarray:
    """Load an image as a numpy array (RGB)."""
    img = Image.open(path).convert("RGB")
    return np.array(img)


def save_image(array: np.ndarray, path: str) -> str:
    """Save a numpy array as an image file."""
    img = Image.fromarray(array)
    img.save(path)
    return path


def crop_region(
    image: np.ndarray,
    bbox: tuple[int, int, int, int],
    padding: int = 0,
) -> np.ndarray:
    """
    Crop a region from an image using a bounding box.

    Args:
        image: Source image as numpy array
        bbox: (x1, y1, x2, y2) bounding box coordinates
        padding: Extra pixels to include around the crop
    """
    h, w = image.shape[:2]
    x1, y1, x2, y2 = bbox

    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(w, x2 + padding)
    y2 = min(h, y2 + padding)

    return image[y1:y2, x1:x2]


def resize_image(
    image: np.ndarray,
    target_width: Optional[int] = None,
    target_height: Optional[int] = None,
    max_size: int = 4096,
) -> np.ndarray:
    """Resize an image maintaining aspect ratio."""
    h, w = image.shape[:2]
    img = Image.fromarray(image)

    if target_width and target_height:
        img = img.resize((target_width, target_height), Image.LANCZOS)
    elif target_width:
        ratio = target_width / w
        new_h = int(h * ratio)
        img = img.resize((target_width, new_h), Image.LANCZOS)
    elif target_height:
        ratio = target_height / h
        new_w = int(w * ratio)
        img = img.resize((new_w, target_height), Image.LANCZOS)
    else:
        # Enforce max size
        if max(w, h) > max_size:
            ratio = max_size / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    return np.array(img)


def preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    """
    Preprocess an image for OCR: grayscale, contrast enhancement, denoising.
    """
    import cv2

    # Convert to grayscale if color
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image

    # Lightweight bilateral filter (preserves character edges while smoothing noise).
    # This is 4000x faster on CPU than fastNlMeansDenoising (takes milliseconds vs minutes).
    denoised = cv2.bilateralFilter(gray, 9, 75, 75)

    # CLAHE for contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    # Convert back to RGB (3-channel) for OCR engines that expect it
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)


def compute_iou(box1: tuple, box2: tuple) -> float:
    """Compute Intersection over Union between two bounding boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0.0
