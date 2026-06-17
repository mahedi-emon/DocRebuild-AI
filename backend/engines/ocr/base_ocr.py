"""
Base OCR Engine — Abstract interface for all OCR engine implementations.

Every OCR engine must implement this interface to participate in the ensemble.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class OCRWord:
    """A single recognized word with its bounding box and metadata."""
    text: str
    bbox: tuple[float, float, float, float]  # (x1, y1, x2, y2) in pixels
    confidence: float  # 0.0 to 1.0
    language: str = "unknown"  # "bn", "en", "mixed"
    engine: str = ""  # Source engine name
    line_id: int = -1  # Which text line this word belongs to
    word_index: int = -1  # Position within the line


@dataclass
class OCRLine:
    """A text line consisting of multiple words."""
    words: list[OCRWord] = field(default_factory=list)
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)
    text: str = ""
    confidence: float = 0.0
    line_id: int = -1

    def compute_text(self) -> str:
        """Rebuild line text from constituent words."""
        self.text = " ".join(w.text for w in self.words)
        return self.text

    def compute_bbox(self) -> tuple[float, float, float, float]:
        """Compute line bounding box from word bboxes."""
        if not self.words:
            return self.bbox
        x1 = min(w.bbox[0] for w in self.words)
        y1 = min(w.bbox[1] for w in self.words)
        x2 = max(w.bbox[2] for w in self.words)
        y2 = max(w.bbox[3] for w in self.words)
        self.bbox = (x1, y1, x2, y2)
        return self.bbox


@dataclass
class OCRResult:
    """Complete OCR result for a single page/image."""
    lines: list[OCRLine] = field(default_factory=list)
    words: list[OCRWord] = field(default_factory=list)
    full_text: str = ""
    engine: str = ""
    overall_confidence: float = 0.0
    processing_time_ms: float = 0.0

    def compute_full_text(self) -> str:
        """Rebuild full text from all lines."""
        self.full_text = "\n".join(line.compute_text() for line in self.lines)
        return self.full_text

    def compute_overall_confidence(self) -> float:
        """Compute average word-level confidence."""
        if not self.words:
            return 0.0
        self.overall_confidence = sum(w.confidence for w in self.words) / len(self.words)
        return self.overall_confidence

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "engine": self.engine,
            "full_text": self.full_text,
            "overall_confidence": self.overall_confidence,
            "processing_time_ms": self.processing_time_ms,
            "line_count": len(self.lines),
            "word_count": len(self.words),
            "lines": [
                {
                    "line_id": line.line_id,
                    "text": line.text,
                    "bbox": list(line.bbox),
                    "confidence": line.confidence,
                    "words": [
                        {
                            "text": w.text,
                            "bbox": list(w.bbox),
                            "confidence": w.confidence,
                            "language": w.language,
                        }
                        for w in line.words
                    ],
                }
                for line in self.lines
            ],
        }


class BaseOCREngine(ABC):
    """Abstract base class for OCR engines."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name identifier for this engine."""
        ...

    @property
    @abstractmethod
    def supported_languages(self) -> list[str]:
        """List of supported language codes (e.g., ['en', 'bn'])."""
        ...

    @abstractmethod
    def initialize(self) -> None:
        """
        Load models and prepare the engine for inference.
        Called once before the first recognition call.
        """
        ...

    @abstractmethod
    def recognize(self, image: np.ndarray, languages: list[str] | None = None) -> OCRResult:
        """
        Perform OCR on a single image.

        Args:
            image: Input image as numpy array (RGB, HWC format)
            languages: Optional language hints (e.g., ['bn', 'en'])

        Returns:
            OCRResult with detected lines, words, and confidence scores
        """
        ...

    @abstractmethod
    def cleanup(self) -> None:
        """Release resources (GPU memory, file handles, etc.)."""
        ...

    def is_available(self) -> bool:
        """Check if the engine's dependencies are installed."""
        try:
            self.initialize()
            self.cleanup()
            return True
        except Exception:
            return False
