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
            # Surya v0.17.x API
            from surya.model.recognition.model import load_model as load_rec_model
            from surya.model.recognition.processor import load_processor as load_rec_processor
            from surya.model.detection.segformer import load_model as load_det_model
            from surya.model.detection.segformer import load_processor as load_det_processor

            logger.info("Loading Surya detection model...")
            self._det_model = load_det_model()
            self._det_processor = load_det_processor()

            logger.info("Loading Surya recognition model...")
            self._rec_model = load_rec_model()
            self._rec_processor = load_rec_processor()

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

        from surya.detection import batch_text_detection
        from surya.recognition import batch_recognition

        # Convert numpy array to PIL Image
        pil_image = Image.fromarray(image)

        # Step 1: Detect text lines
        det_predictions = batch_text_detection(
            [pil_image],
            self._det_model,
            self._det_processor,
        )

        # Map language codes for Surya
        lang_list = languages or ["en", "bn"]
        surya_langs = []
        for lang in lang_list:
            surya_langs.append(lang)

        # Step 2: Recognize text in detected lines
        rec_predictions = batch_recognition(
            [pil_image],
            [surya_langs],
            self._rec_model,
            self._rec_processor,
            bboxes=[det_predictions[0]],
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
        self._rec_model = None
        self._rec_processor = None
        self._det_model = None
        self._det_processor = None
        self._initialized = False
        gc.collect()
