"""
Surya OCR Engine Wrapper

Wraps Surya OCR v0.17.x for high-quality text recognition.
Supports Bangla and English natively.
"""

from __future__ import annotations

import time
import logging
import numpy as np
from PIL import Image

from engines.ocr.base_ocr import BaseOCREngine, OCRResult, OCRLine, OCRWord

logger = logging.getLogger(__name__)


class SuryaOCREngine(BaseOCREngine):
    """Surya OCR v0.17.x engine."""

    def __init__(self):
        self._rec_model = None
        self._rec_processor = None
        self._det_model = None
        self._det_processor = None
        self._initialized = False

    @property
    def name(self) -> str:
        return "surya"

    @property
    def supported_languages(self) -> list[str]:
        return ["en", "bn", "hi", "ar", "zh", "ja", "ko"]

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            # Import new object-oriented predictor classes
            from surya.foundation import FoundationPredictor
            from surya.detection import DetectionPredictor
            from surya.recognition import RecognitionPredictor

            logger.info("Loading Surya foundation predictor...")
            self._foundation_predictor = FoundationPredictor()

            logger.info("Loading Surya detection predictor...")
            self._det_predictor = DetectionPredictor()

            logger.info("Loading Surya recognition predictor...")
            self._rec_predictor = RecognitionPredictor(self._foundation_predictor)

            self._initialized = True
            logger.info("Surya OCR v0.17.x initialized successfully")
        except ImportError as e:
            raise ImportError(
                f"Surya OCR not available: {e}. Install with: pip install surya-ocr>=0.17.0"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Surya OCR: {e}")

    def recognize(self, image: np.ndarray, languages: list[str] | None = None) -> OCRResult:
        self.initialize()
        start_time = time.time()

        # Convert numpy array to PIL Image
        pil_image = Image.fromarray(image)

        # Map language codes for Surya
        lang_list = languages or ["en", "bn"]

        # Run detection and recognition using the new predictor API
        rec_predictions = self._rec_predictor(
            [pil_image],
            task_names=["ocr_with_boxes"],
            det_predictor=self._det_predictor,
        )

        lines = []
        all_words = []
        line_id = 0

        if rec_predictions:
            page_pred = rec_predictions[0]
            for text_line in page_pred.text_lines:
                text = text_line.text
                if not text or not text.strip():
                    continue

                # Get bounding box
                bbox = (0, 0, image.shape[1], image.shape[0])
                if hasattr(text_line, 'bbox') and text_line.bbox:
                    b = text_line.bbox
                    bbox = (b[0], b[1], b[2], b[3])
                elif hasattr(text_line, 'polygon') and text_line.polygon:
                    pts = text_line.polygon
                    bbox = (
                        min(p[0] for p in pts),
                        min(p[1] for p in pts),
                        max(p[0] for p in pts),
                        max(p[1] for p in pts),
                    )

                confidence = getattr(text_line, 'confidence', 0.85)

                # Split into words with estimated per-word bounding boxes
                words_in_line = []
                text_words = text.split()
                if len(text_words) > 1:
                    x1, y1, x2, y2 = bbox
                    total_chars = max(sum(len(w) for w in text_words), 1)
                    line_width = x2 - x1
                    current_x = x1

                    for wi, word_text in enumerate(text_words):
                        word_len = len(word_text)
                        word_width = line_width * (word_len / total_chars)
                        word_bbox = (current_x, y1, current_x + word_width, y2)
                        current_x += word_width

                        word = OCRWord(
                            text=word_text,
                            bbox=word_bbox,
                            confidence=confidence,
                            engine=self.name,
                            line_id=line_id,
                            word_index=wi,
                        )
                        words_in_line.append(word)
                        all_words.append(word)
                else:
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

                if words_in_line:
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

        logger.info(f"Surya OCR: {len(all_words)} words, {len(lines)} lines in {elapsed:.0f}ms")
        return result

    def cleanup(self) -> None:
        import gc
        self._foundation_predictor = None
        self._rec_predictor = None
        self._det_predictor = None
        self._initialized = False
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
