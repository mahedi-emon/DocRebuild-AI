"""
InternVL Vision Engine — OCR validation using OpenGVLab InternVL.

Uses InternVL2 (e.g. InternVL2-8B) for visual question answering and 
text extraction to cross-validate OCR outputs.
"""

from __future__ import annotations

import logging
import time

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


# ── InternVL Specific Image Preprocessing ────────────────────────────────────
# The following preprocessing function is standard for InternVL models
# to maintain proper aspect ratio slicing.

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def build_transform(input_size):
    import torchvision.transforms as T
    from torchvision.transforms.functional import InterpolationMode
    
    transform = T.Compose([
        T.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
        T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ])
    return transform


def find_closest_aspect_ratio(aspect_ratio, target_ratios, width, height, image_size):
    best_ratio_diff = float("inf")
    best_ratio = (1, 1)
    area = width * height
    for ratio in target_ratios:
        target_aspect_ratio = ratio[0] / ratio[1]
        ratio_diff = abs(aspect_ratio - target_aspect_ratio)
        if ratio_diff < best_ratio_diff:
            best_ratio_diff = ratio_diff
            best_ratio = ratio
        elif ratio_diff == best_ratio_diff:
            if area > 0.5 * image_size * image_size * ratio[0] * ratio[1]:
                best_ratio = ratio
    return best_ratio


def dynamic_preprocess(image, min_num=1, max_num=12, image_size=448, use_thumbnail=False):
    orig_width, orig_height = image.size
    aspect_ratio = orig_width / orig_height

    # Calculate the best double-grid layout
    target_ratios = set()
    for i in range(min_num, max_num + 1):
        for j in range(min_num, max_num + 1):
            if i * j <= max_num:
                target_ratios.add((i, j))
    target_ratios = list(target_ratios)

    target_aspect_ratio = find_closest_aspect_ratio(
        aspect_ratio, target_ratios, orig_width, orig_height, image_size
    )

    # Calculate target width and height
    target_width = image_size * target_aspect_ratio[0]
    target_height = image_size * target_aspect_ratio[1]
    blocks = target_aspect_ratio[0] * target_aspect_ratio[1]

    # Resize the image
    resized_img = image.resize((target_width, target_height))
    processed_images = []
    for i in range(blocks):
        box = (
            (i % target_aspect_ratio[0]) * image_size,
            (i // target_aspect_ratio[0]) * image_size,
            ((i % target_aspect_ratio[0]) + 1) * image_size,
            ((i // target_aspect_ratio[0]) + 1) * image_size
        )
        split_img = resized_img.crop(box)
        processed_images.append(split_img)
    assert len(processed_images) == blocks

    if use_thumbnail and len(processed_images) > 1:
        thumbnail_img = image.resize((image_size, image_size))
        processed_images.append(thumbnail_img)
    return processed_images


class InternVLEngine:
    """InternVL vision-language model for OCR validation."""

    def __init__(self, model_name: str = "OpenGVLab/InternVL2-8B"):
        self._model_name = model_name
        self._model = None
        self._tokenizer = None
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if device == "cuda" else torch.float32

            logger.info(f"Initializing InternVL ({self._model_name}) on {device}...")
            
            # Load tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(
                self._model_name, trust_remote_code=True, use_fast=False
            )
            
            # Load model
            self._model = AutoModel.from_pretrained(
                self._model_name,
                device_map="auto" if device == "cuda" else None,
                trust_remote_code=True,
                torch_dtype=dtype,
            )
            if device != "cuda":
                self._model = self._model.to(device)
                
            self._model.eval()
            self._device = device
            self._dtype = dtype
            self._initialized = True
            logger.info("InternVL initialized successfully.")
        except ImportError:
            raise ImportError(
                "Transformers / PyTorch / Torchvision not installed. "
                "Install with: pip install transformers torch torchvision"
            )

    def load_image_pixel_values(self, image: Image.Image, input_size: int = 448) -> torch.Tensor:
        """Preprocess PIL Image to match InternVL expected tensor format."""
        import torch
        transform = build_transform(input_size=input_size)
        images = dynamic_preprocess(image, image_size=input_size, use_thumbnail=True)
        pixel_values = [transform(img) for img in images]
        pixel_values = torch.stack(pixel_values)
        return pixel_values.to(self._device, self._dtype)

    def read_text(self, image: np.ndarray) -> str:
        """Use InternVL to transcribe text from the given image."""
        self.initialize()
        import torch
        
        pil_image = Image.fromarray(image).convert("RGB")
        try:
            pixel_values = self.load_image_pixel_values(pil_image)
            
            # Formulate InternVL standard generation prompt
            question = "<image>\nRead all the text in this image. Output only the text you see."
            
            generation_config = dict(max_new_tokens=1024, do_sample=False)
            
            # InternVL models with trust_remote_code=True expose a custom .chat function
            response, _ = self._model.chat(
                self._tokenizer,
                pixel_values,
                question,
                generation_config
            )
            return response.strip()
        except Exception as e:
            logger.error(f"InternVL read_text failed: {e}")
            return ""

    def validate_text(self, image: np.ndarray, ocr_text: str) -> dict:
        """
        Validate OCR text against InternVL transcription.

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
        self._tokenizer = None
        self._initialized = False
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
