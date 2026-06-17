"""
Marker Engine — High-quality PDF to markdown conversion.

Optimized for books and scientific papers. Uses deep learning models
for layout analysis, OCR, and equation detection.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


class MarkerEngine:
    """Marker PDF converter engine."""

    def __init__(self):
        self._converter = None
        self._model_dict = None
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            from marker.converters.pdf import PdfConverter
            from marker.models import create_model_dict
            from marker.output import text_from_rendered

            self._model_dict = create_model_dict()
            self._converter = PdfConverter(artifact_dict=self._model_dict)
            self._initialized = True
            logger.info("Marker engine initialized")
        except ImportError:
            raise ImportError("Marker not installed. Install with: pip install marker-pdf")

    def understand(self, pdf_path: str) -> dict:
        """
        Convert PDF to structured markdown using Marker.

        Returns dict with:
        - markdown: Full document as clean markdown
        - metadata: Document metadata
        """
        self.initialize()
        from marker.output import text_from_rendered

        start_time = time.time()

        rendered = self._converter(pdf_path)
        text, images, metadata = text_from_rendered(rendered)

        elapsed = (time.time() - start_time) * 1000

        return {
            "engine": "marker",
            "markdown": text,
            "metadata": metadata if isinstance(metadata, dict) else {},
            "image_count": len(images) if images else 0,
            "processing_time_ms": elapsed,
        }

    def cleanup(self) -> None:
        import gc
        self._converter = None
        self._model_dict = None
        self._initialized = False
        gc.collect()
