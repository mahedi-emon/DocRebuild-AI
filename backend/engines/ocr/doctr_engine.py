"""
DocTR Engine Wrapper

Wraps Mindee DocTR (python-doctr) for end-to-end document text recognition.
Provides word-level bounding boxes and confidence scores.
"""

from __future__ import annotations

import time
import numpy as np

from engines.ocr.base_ocr import BaseOCREngine, OCRResult, OCRLine, OCRWord


class DocTREngine(BaseOCREngine):
    """Mindee DocTR OCR engine."""

    def __init__(self):
        self._model = None
        self._initialized = False

    @property
    def name(self) -> str:
        return "doctr"

    @property
    def supported_languages(self) -> list[str]:
        return ["en", "bn"]

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            from doctr.models import ocr_predictor

            self._model = ocr_predictor(pretrained=True)
            self._initialized = True
        except ImportError:
            raise ImportError(
                "DocTR not installed. Install with: pip install python-doctr[torch]"
            )

    def recognize(self, image: np.ndarray, languages: list[str] | None = None) -> OCRResult:
        self.initialize()
        from doctr.io import DocumentFile

        start_time = time.time()

        # DocTR expects a list of numpy arrays
        doc = [image]
        result_raw = self._model(doc)

        lines = []
        all_words = []
        line_id = 0

        img_h, img_w = image.shape[:2]

        for page in result_raw.pages:
            for block in page.blocks:
                for line_data in block.lines:
                    words_in_line = []

                    for wi, word_data in enumerate(line_data.words):
                        # DocTR returns normalized coordinates (0-1)
                        geo = word_data.geometry
                        # geo is ((x_min, y_min), (x_max, y_max)) normalized
                        x1 = geo[0][0] * img_w
                        y1 = geo[0][1] * img_h
                        x2 = geo[1][0] * img_w
                        y2 = geo[1][1] * img_h
                        bbox = (x1, y1, x2, y2)

                        word = OCRWord(
                            text=word_data.value,
                            bbox=bbox,
                            confidence=word_data.confidence,
                            engine=self.name,
                            line_id=line_id,
                            word_index=wi,
                        )
                        words_in_line.append(word)
                        all_words.append(word)

                    if words_in_line:
                        line = OCRLine(
                            words=words_in_line,
                            line_id=line_id,
                        )
                        line.compute_text()
                        line.compute_bbox()
                        line.confidence = (
                            sum(w.confidence for w in words_in_line) / len(words_in_line)
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
        import gc

        self._model = None
        self._initialized = False
        gc.collect()
