"""
Florence-2 Vision Engine — OCR validation using Microsoft Florence-2.

Uses Florence-2-large for visual question answering to cross-validate
OCR output against the original document image.
"""

from __future__ import annotations

import logging
import time

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class Florence2Engine:
    """Microsoft Florence-2 vision-language model for OCR validation."""

    def __init__(self, model_name: str = "microsoft/Florence-2-large"):
        self._model_name = model_name
        self._model = None
        self._processor = None
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            import torch
            from transformers import AutoProcessor, AutoModelForCausalLM

            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if device == "cuda" else torch.float32

            self._processor = AutoProcessor.from_pretrained(
                self._model_name, trust_remote_code=True
            )
            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_name,
                torch_dtype=dtype,
                trust_remote_code=True,
            ).to(device)
            self._model.eval()
            self._device = device
            self._dtype = dtype
            self._initialized = True
            logger.info(f"Florence-2 initialized on {device}")
        except ImportError:
            raise ImportError(
                "Transformers not installed. Install with: pip install transformers torch"
            )

    def read_text(self, image: np.ndarray) -> str:
        """Use Florence-2 OCR capability to read text from an image region."""
        self.initialize()
        import torch

        pil_image = Image.fromarray(image).convert("RGB")
        prompt = "<OCR>"

        inputs = self._processor(
            text=prompt, images=pil_image, return_tensors="pt"
        ).to(self._device, self._dtype)

        with torch.no_grad():
            generated_ids = self._model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=1024,
                num_beams=3,
            )

        text = self._processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
        parsed = self._processor.post_process_generation(
            text, task=prompt, image_size=(pil_image.width, pil_image.height)
        )
        return parsed.get("<OCR>", text)

    def validate_text(self, image: np.ndarray, ocr_text: str) -> dict:
        """
        Validate OCR text against what Florence-2 sees in the image.

        Returns:
            {'matches': bool, 'vision_text': str, 'similarity': float}
        """
        vision_text = self.read_text(image)
        from app.utils.text_utils import text_similarity
        sim = text_similarity(ocr_text, vision_text)

        return {
            "matches": sim > 0.7,
            "vision_text": vision_text,
            "ocr_text": ocr_text,
            "similarity": sim,
        }

    def cleanup(self) -> None:
        import gc
        self._model = None
        self._processor = None
        self._initialized = False
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
