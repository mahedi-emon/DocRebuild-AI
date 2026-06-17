"""
Pix2Tex Engine — Equation image to LaTeX conversion.

Uses the pix2tex (LaTeX-OCR) model to convert images of mathematical
equations into editable LaTeX code.
"""

from __future__ import annotations

import logging
import time

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class Pix2TexEngine:
    """Pix2Tex LaTeX OCR engine."""

    def __init__(self):
        self._model = None
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            from pix2tex.cli import LatexOCR
            self._model = LatexOCR()
            self._initialized = True
            logger.info("Pix2Tex engine initialized")
        except ImportError:
            raise ImportError("Pix2Tex not installed. Install with: pip install pix2tex")

    def recognize(self, image: np.ndarray) -> dict:
        """
        Convert an equation image to LaTeX.

        Returns:
            {'latex': str, 'confidence': float, 'time_ms': float}
        """
        self.initialize()
        start_time = time.time()

        pil_image = Image.fromarray(image).convert("RGB")
        latex = self._model(pil_image)

        elapsed = (time.time() - start_time) * 1000

        # Validate LaTeX syntax
        is_valid = self._validate_latex(latex)

        return {
            "latex": latex,
            "is_valid": is_valid,
            "confidence": 0.85 if is_valid else 0.5,
            "engine": "pix2tex",
            "processing_time_ms": elapsed,
        }

    def _validate_latex(self, latex: str) -> bool:
        """Basic LaTeX syntax validation."""
        if not latex or not latex.strip():
            return False

        # Check balanced braces
        depth = 0
        for char in latex:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            if depth < 0:
                return False

        return depth == 0

    def cleanup(self) -> None:
        self._model = None
        self._initialized = False
