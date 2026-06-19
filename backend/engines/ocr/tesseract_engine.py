"""
Tesseract OCR Engine Wrapper

Wraps pytesseract for text recognition with configurable PSM modes.
Uses 'ben+eng' language packs for Bangla+English documents.
"""

from __future__ import annotations

import time
import numpy as np

from engines.ocr.base_ocr import BaseOCREngine, OCRResult, OCRLine, OCRWord


class TesseractOCREngine(BaseOCREngine):
    """Tesseract OCR engine via pytesseract."""

    def __init__(self, psm: int = 3):
        """
        Args:
            psm: Page Segmentation Mode (3=fully automatic, 6=uniform block, 11=sparse text)
        """
        self._psm = psm
        self._initialized = False

    @property
    def name(self) -> str:
        return "tesseract"

    @property
    def supported_languages(self) -> list[str]:
        return ["en", "bn", "ar"]

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            import pytesseract
            # Verify tesseract is accessible
            pytesseract.get_tesseract_version()
            self._initialized = True
        except Exception as e:
            raise ImportError(
                f"Tesseract not available: {e}. "
                "Install Tesseract-OCR and pytesseract. "
                "Also install Bengali and Arabic language packs: apt-get install tesseract-ocr-ben tesseract-ocr-ara"
            )

    def recognize(self, image: np.ndarray, languages: list[str] | None = None) -> OCRResult:
        self.initialize()
        import pytesseract
        from PIL import Image

        start_time = time.time()

        pil_image = Image.fromarray(image)

        # Determine language string
        lang = "ben+eng"
        if languages:
            lang_map = {"en": "eng", "bn": "ben", "ar": "ara"}
            lang_parts = [lang_map.get(l, l) for l in languages]
            lang_parts = [p for p in lang_parts if p]
            if lang_parts:
                lang = "+".join(lang_parts)

        # Get detailed data with bounding boxes
        custom_config = f"--psm {self._psm} --oem 3"
        data = pytesseract.image_to_data(
            pil_image,
            lang=lang,
            config=custom_config,
            output_type=pytesseract.Output.DICT,
        )

        lines = []
        all_words = []
        current_line_id = -1
        current_line_words = []

        n_boxes = len(data["text"])
        for i in range(n_boxes):
            text = data["text"][i].strip()
            conf = float(data["conf"][i])

            if conf < 0:
                continue  # Skip invalid entries

            # Tesseract confidence is 0-100, normalize to 0-1
            confidence = conf / 100.0

            x = data["left"][i]
            y = data["top"][i]
            w = data["width"][i]
            h = data["height"][i]
            bbox = (x, y, x + w, y + h)

            block_num = data["block_num"][i]
            line_num = data["line_num"][i]
            line_id = block_num * 1000 + line_num

            if text:
                word = OCRWord(
                    text=text,
                    bbox=bbox,
                    confidence=confidence,
                    engine=self.name,
                    line_id=line_id,
                    word_index=data["word_num"][i],
                )
                all_words.append(word)

                if line_id != current_line_id:
                    # Save previous line
                    if current_line_words:
                        line = OCRLine(words=current_line_words, line_id=current_line_id)
                        line.compute_text()
                        line.compute_bbox()
                        line.confidence = (
                            sum(w.confidence for w in current_line_words)
                            / len(current_line_words)
                        )
                        lines.append(line)
                    current_line_id = line_id
                    current_line_words = [word]
                else:
                    current_line_words.append(word)

        # Don't forget the last line
        if current_line_words:
            line = OCRLine(words=current_line_words, line_id=current_line_id)
            line.compute_text()
            line.compute_bbox()
            line.confidence = (
                sum(w.confidence for w in current_line_words) / len(current_line_words)
            )
            lines.append(line)

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
        self._initialized = False
