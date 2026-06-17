"""
Table Transformer Engine — Microsoft Table Transformer for table detection and structure recognition.

Uses two DETR-based models:
1. microsoft/table-transformer-detection — finds tables in document images
2. microsoft/table-transformer-structure-recognition — identifies rows, columns, cells
"""

from __future__ import annotations

import logging
import time

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class TableTransformerEngine:
    """Microsoft Table Transformer engine."""

    def __init__(self):
        self._detection_model = None
        self._structure_model = None
        self._detection_processor = None
        self._structure_processor = None
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            import torch
            from transformers import (
                AutoModelForObjectDetection,
                AutoImageProcessor,
            )

            device = "cuda" if torch.cuda.is_available() else "cpu"

            # Table detection model
            self._detection_processor = AutoImageProcessor.from_pretrained(
                "microsoft/table-transformer-detection"
            )
            self._detection_model = AutoModelForObjectDetection.from_pretrained(
                "microsoft/table-transformer-detection"
            ).to(device)

            # Structure recognition model
            self._structure_processor = AutoImageProcessor.from_pretrained(
                "microsoft/table-transformer-structure-recognition"
            )
            self._structure_model = AutoModelForObjectDetection.from_pretrained(
                "microsoft/table-transformer-structure-recognition"
            ).to(device)

            self._device = device
            self._initialized = True
            logger.info("Table Transformer initialized")
        except ImportError:
            raise ImportError("Transformers not installed for Table Transformer")

    def detect_tables(self, image: np.ndarray, threshold: float = 0.7) -> list[dict]:
        """
        Detect table bounding boxes in a document image.

        Returns:
            List of {'bbox': [x1,y1,x2,y2], 'confidence': float}
        """
        self.initialize()
        import torch

        pil_image = Image.fromarray(image).convert("RGB")
        inputs = self._detection_processor(images=pil_image, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._detection_model(**inputs)

        target_sizes = torch.tensor([pil_image.size[::-1]]).to(self._device)
        results = self._detection_processor.post_process_object_detection(
            outputs, target_sizes=target_sizes, threshold=threshold
        )[0]

        tables = []
        for score, label, box in zip(
            results["scores"], results["labels"], results["boxes"]
        ):
            bbox = box.cpu().numpy().tolist()
            tables.append({
                "bbox": bbox,
                "confidence": float(score),
            })

        return tables

    def recognize_structure(self, table_image: np.ndarray) -> dict:
        """
        Recognize the structure (rows, columns, cells) of a cropped table image.

        Returns:
            {'rows': list, 'columns': list, 'cells': list}
        """
        self.initialize()
        import torch

        pil_image = Image.fromarray(table_image).convert("RGB")
        inputs = self._structure_processor(images=pil_image, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._structure_model(**inputs)

        target_sizes = torch.tensor([pil_image.size[::-1]]).to(self._device)
        results = self._structure_processor.post_process_object_detection(
            outputs, target_sizes=target_sizes, threshold=0.5
        )[0]

        # Categorize detections
        rows = []
        columns = []
        cells = []

        id2label = self._structure_model.config.id2label
        for score, label, box in zip(
            results["scores"], results["labels"], results["boxes"]
        ):
            bbox = box.cpu().numpy().tolist()
            label_name = id2label.get(int(label), "unknown")

            entry = {"bbox": bbox, "confidence": float(score), "label": label_name}

            if "row" in label_name.lower():
                rows.append(entry)
            elif "column" in label_name.lower():
                columns.append(entry)
            else:
                cells.append(entry)

        # Sort rows top-to-bottom and columns left-to-right
        rows.sort(key=lambda r: r["bbox"][1])
        columns.sort(key=lambda c: c["bbox"][0])

        return {
            "rows": rows,
            "columns": columns,
            "cells": cells,
            "row_count": len(rows),
            "column_count": len(columns),
        }

    def cleanup(self) -> None:
        import gc
        self._detection_model = None
        self._structure_model = None
        self._detection_processor = None
        self._structure_processor = None
        self._initialized = False
        gc.collect()
