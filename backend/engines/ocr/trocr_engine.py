"""
TrOCR Engine Wrapper

Wraps Microsoft TrOCR via HuggingFace Transformers.
Operates on pre-segmented text line crops (single line at a time).
Uses trocr-base-printed for typed/printed text.
"""

from __future__ import annotations

import time
import numpy as np
from PIL import Image

from engines.ocr.base_ocr import BaseOCREngine, OCRResult, OCRLine, OCRWord


class TrOCREngine(BaseOCREngine):
    """Microsoft TrOCR engine for single-line text recognition."""

    def __init__(self, model_name: str = "microsoft/trocr-base-printed"):
        self._model_name = model_name
        self._processor = None
        self._model = None
        self._initialized = False

    @property
    def name(self) -> str:
        return "trocr"

    @property
    def supported_languages(self) -> list[str]:
        return ["en"]  # TrOCR primarily supports English/Latin scripts

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            import torch
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel

            self._processor = TrOCRProcessor.from_pretrained(self._model_name)
            self._model = VisionEncoderDecoderModel.from_pretrained(self._model_name)

            # Move to GPU if available
            if torch.cuda.is_available():
                self._model = self._model.to("cuda")

            self._model.eval()
            self._initialized = True
        except ImportError:
            raise ImportError(
                "Transformers not installed. Install with: pip install transformers torch"
            )

    def recognize(self, image: np.ndarray, languages: list[str] | None = None) -> OCRResult:
        """
        Recognize text from a full page image.

        Note: TrOCR works on single lines. For full pages, the image should
        ideally be pre-segmented into lines via layout analysis. Here we
        process the whole image as a single block for compatibility with
        the ensemble interface.
        """
        self.initialize()
        import torch

        start_time = time.time()

        pil_image = Image.fromarray(image).convert("RGB")

        # Process the image
        pixel_values = self._processor(
            images=pil_image, return_tensors="pt"
        ).pixel_values

        if torch.cuda.is_available():
            pixel_values = pixel_values.to("cuda")

        # Generate text
        with torch.no_grad():
            generated_ids = self._model.generate(pixel_values, max_new_tokens=256)

        generated_text = self._processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0]

        elapsed = (time.time() - start_time) * 1000

        # TrOCR doesn't provide per-word bounding boxes,
        # so we create a single line with the full image bbox
        h, w = image.shape[:2]
        bbox = (0, 0, w, h)

        words = []
        for wi, word_text in enumerate(generated_text.split()):
            word = OCRWord(
                text=word_text,
                bbox=bbox,
                confidence=0.85,  # TrOCR doesn't provide per-word confidence
                engine=self.name,
                line_id=0,
                word_index=wi,
            )
            words.append(word)

        line = OCRLine(
            words=words,
            bbox=bbox,
            text=generated_text,
            confidence=0.85,
            line_id=0,
        )

        result = OCRResult(
            lines=[line] if generated_text.strip() else [],
            words=words,
            engine=self.name,
            processing_time_ms=elapsed,
        )
        result.compute_full_text()
        result.compute_overall_confidence()
        return result

    def recognize_line(self, line_image: np.ndarray) -> tuple[str, float]:
        """
        Recognize a single cropped text line image.
        Returns (text, confidence).
        """
        self.initialize()
        import torch

        pil_image = Image.fromarray(line_image).convert("RGB")
        pixel_values = self._processor(
            images=pil_image, return_tensors="pt"
        ).pixel_values

        if torch.cuda.is_available():
            pixel_values = pixel_values.to("cuda")

        with torch.no_grad():
            generated_ids = self._model.generate(pixel_values, max_new_tokens=256)

        text = self._processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0]

        return text, 0.85

    def cleanup(self) -> None:
        import gc

        self._processor = None
        self._model = None
        self._initialized = False
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
