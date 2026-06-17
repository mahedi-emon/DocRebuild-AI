"""
PaddleOCR Engine Wrapper

Wraps PaddleOCR 3.x for text detection and recognition.
Supports Bangla ('bn') and English ('en') with angle classification.
"""

from __future__ import annotations

import time
import logging
import numpy as np

from engines.ocr.base_ocr import BaseOCREngine, OCRResult, OCRLine, OCRWord

logger = logging.getLogger(__name__)


class PaddleOCREngine(BaseOCREngine):
    """PaddleOCR 3.x engine with angle classification."""

    def __init__(self):
        self._ocr_en = None
        self._ocr_bn = None
        self._initialized = False

    @property
    def name(self) -> str:
        return "paddleocr"

    @property
    def supported_languages(self) -> list[str]:
        return ["en"]

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            from paddleocr import PaddleOCR

            try:
                self._ocr_en = PaddleOCR(
                    use_angle_cls=True,
                    lang="en",
                    show_log=False,
                    use_gpu=self._check_gpu(),
                )
                # Bengali language support
                self._ocr_bn = PaddleOCR(
                    use_angle_cls=True,
                    lang="en",  # PaddleOCR uses 'en' for Latin; Bangla via custom model
                    show_log=False,
                    use_gpu=self._check_gpu(),
                )
            except (TypeError, Exception) as e:
                logger.warning(f"Failed to initialize PaddleOCR with standard arguments, falling back: {e}")
                self._ocr_en = PaddleOCR(lang="en")
                self._ocr_bn = PaddleOCR(lang="en")
            self._initialized = True
        except ImportError:
            raise ImportError(
                "PaddleOCR not installed. Install with: pip install paddleocr paddlepaddle"
            )

    def _check_gpu(self) -> bool:
        try:
            import paddle
            return paddle.device.is_compiled_with_cuda()
        except Exception:
            return False

    def recognize(self, image: np.ndarray, languages: list[str] | None = None) -> OCRResult:
        self.initialize()
        start_time = time.time()

        ocr_engine = self._ocr_en
        result_raw = ocr_engine.ocr(image, cls=True)

        lines = []
        all_words = []
        line_id = 0

        if result_raw:
            for page_result in result_raw:
                if not page_result:
                    continue
                for detection in page_result:
                    # detection = [bbox_points, (text, confidence)]
                    bbox_points = detection[0]  # [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
                    text_info = detection[1]  # (text, confidence)

                    text = text_info[0]
                    confidence = float(text_info[1])

                    # Convert polygon to (x1, y1, x2, y2)
                    xs = [p[0] for p in bbox_points]
                    ys = [p[1] for p in bbox_points]
                    bbox = (min(xs), min(ys), max(xs), max(ys))

                    # Split into words and estimate word-level bounding boxes
                    words_in_line = []
                    text_words = text.split()
                    if len(text_words) > 1:
                        x1, y1, x2, y2 = bbox
                        total_chars = sum(len(w) for w in text_words)
                        current_x = x1
                        line_width = x2 - x1
                        
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
        self._ocr_en = None
        self._ocr_bn = None
        self._initialized = False
