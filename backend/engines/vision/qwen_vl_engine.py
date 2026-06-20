"""
Qwen-VL Vision Engine — OCR validation using Alibaba Qwen-VL.

Uses Qwen-VL-Chat for visual question answering and text extraction
to cross-validate OCR outputs.
"""

from __future__ import annotations

import logging
import time
import tempfile
import os

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class QwenVLEngine:
    """Qwen-VL vision-language model for OCR validation."""

    def __init__(self, model_name: str = "Qwen/Qwen-VL-Chat"):
        self._model_name = model_name
        self._model = None
        self._tokenizer = None
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if device == "cuda" else torch.float32

            logger.info(f"Initializing Qwen-VL ({self._model_name}) on {device}...")
            
            # Load tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(
                self._model_name, trust_remote_code=True
            )
            
            # Load model with automatic device mapping or direct device placement
            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_name,
                device_map="auto" if device == "cuda" else None,
                trust_remote_code=True,
                torch_dtype=dtype,
            )
            
            # Monkey-patch any causal LM submodules to support transformers 4.50+
            try:
                from transformers.generation import GenerationMixin
                import torch.nn as nn
                
                def check_and_patch(obj):
                    if obj is None:
                        return
                    if isinstance(obj, nn.Module) and not hasattr(obj, "generate"):
                        cls = obj.__class__
                        if GenerationMixin not in cls.__bases__:
                            try:
                                cls.__bases__ = cls.__bases__ + (GenerationMixin,)
                                logger.info(f"Dynamically patched {cls.__name__} with GenerationMixin for compatibility")
                            except Exception as e:
                                logger.debug(f"Could not patch {cls.__name__}: {e}")
                    for name, child in getattr(obj, "_modules", {}).items():
                        check_and_patch(child)
                        
                check_and_patch(self._model)
            except Exception as patch_err:
                logger.warning(f"Error executing transformers compat monkey-patch: {patch_err}")

            if device != "cuda":
                self._model = self._model.to(device)
                
            self._model.eval()
            self._device = device
            self._initialized = True
            logger.info(f"Qwen-VL initialized successfully.")
        except ImportError:
            raise ImportError(
                "Transformers / PyTorch not installed. Install with: pip install transformers torch"
            )

    def read_text(self, image: np.ndarray) -> str:
        """Use Qwen-VL to transcribe text from the given image."""
        self.initialize()
        
        pil_image = Image.fromarray(image).convert("RGB")
        temp_path = None
        
        try:
            # Qwen-VL-Chat tokenizer from_list_format requires a local image file path
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                temp_path = f.name
            pil_image.save(temp_path)

            query = self._tokenizer.from_list_format([
                {"image": temp_path},
                {"text": "Read all the text in this image. Output only the text you see."},
            ])
            
            response, _ = self._model.chat(
                self._tokenizer, 
                query=query, 
                history=None
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Qwen-VL read_text failed: {e}")
            return ""
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

    def validate_text(self, image: np.ndarray, ocr_text: str) -> dict:
        """
        Validate OCR text against Qwen-VL transcription.

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
