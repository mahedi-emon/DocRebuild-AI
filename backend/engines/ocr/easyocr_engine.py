"""
EasyOCR Engine Wrapper

Wraps EasyOCR with Bangla ('bn') and English ('en') readers.
GPU-accelerated when available.
"""

from __future__ import annotations

import time
import numpy as np

from engines.ocr.base_ocr import BaseOCREngine, OCRResult, OCRLine, OCRWord


class EasyOCREngine(BaseOCREngine):
    """EasyOCR engine with GPU support."""

    def __init__(self):
        self._reader = None
        self._initialized = False

    @property
    def name(self) -> str:
        return "easyocr"

    @property
    def supported_languages(self) -> list[str]:
        return ["en", "bn"]

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            import easyocr

            gpu = False
            try:
                import torch
                gpu = torch.cuda.is_available()
            except ImportError:
                pass

            self._reader = easyocr.Reader(
                ["bn", "en"],
                gpu=gpu,
                verbose=False,
            )
            self._initialized = True
        except ImportError:
            raise ImportError("EasyOCR not installed. Install with: pip install easyocr")

    def recognize(self, image: np.ndarray, languages: list[str] | None = None) -> OCRResult:
        self.initialize()
        start_time = time.time()

        # EasyOCR expects numpy array or path
        results_raw = self._reader.readtext(image, detail=1, paragraph=False)

        lines = []
        all_words = []
        line_id = 0

        for detection in results_raw:
            # detection = (bbox_points, text, confidence)
            bbox_points = detection[0]  # [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
            text = detection[1]
            confidence = float(detection[2])

            # Convert polygon to (x1, y1, x2, y2)
            xs = [p[0] for p in bbox_points]
            ys = [p[1] for p in bbox_points]
            bbox = (min(xs), min(ys), max(xs), max(ys))

            # Split into words
            words_in_line = []
            text_words = text.split()
            for wi, word_text in enumerate(text_words):
                word = OCRWord(
                    text=word_text,
                    bbox=bbox,
                    confidence=confidence,
                    engine=self.name,
                    line_id=line_id,
                    word_index=wi,
                )
                words_in_line.append(word)
                all_words.append(word)

            line = OCRLine(
                words=words_in_line,
                bbox=bbox,
                text=text,
                confidence=confidence,
                line_id=line_id,
            )
            lines.append(line)
            line_id += 1

        elapsed = (time.time() - start_time) * 1000

        result = OCRResult(
            lines=lines,
            words=all_words,
            engine=self.name,
            processing_time_ms=elapsed,
        )
        result.compute_full_text()
        result.compute_overall_confidence()
        return result

    def cleanup(self) -> None:
        self._reader = None
        self._initialized = False
