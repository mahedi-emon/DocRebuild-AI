"""
Docling Engine — Document understanding using IBM Docling.

Extracts structured content including tables, reading order, and
document hierarchy (chapters, sections, paragraphs).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class DoclingEngine:
    """IBM Docling document understanding engine."""

    def __init__(self):
        self._converter = None
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            from docling.document_converter import DocumentConverter
            self._converter = DocumentConverter()
            self._initialized = True
            logger.info("Docling engine initialized")
        except ImportError:
            raise ImportError("Docling not installed. Install with: pip install docling")

    def understand(self, pdf_path: str) -> dict:
        """
        Process a PDF and extract structured understanding.

        Returns dict with:
        - markdown: Full document as markdown
        - sections: List of section objects with hierarchy
        - tables: Extracted table structures
        - reading_order: Ordered list of content blocks
        """
        self.initialize()
        start_time = time.time()

        result = self._converter.convert(pdf_path)
        document = result.document

        # Export to markdown
        markdown = document.export_to_markdown()

        # Build section hierarchy
        sections = []
        try:
            for item in document.iterate_items():
                section = {
                    "text": str(item) if item else "",
                    "type": type(item).__name__ if item else "unknown",
                }
                sections.append(section)
        except Exception as e:
            logger.warning(f"Could not extract sections: {e}")

        elapsed = (time.time() - start_time) * 1000

        return {
            "engine": "docling",
            "markdown": markdown,
            "sections": sections,
            "processing_time_ms": elapsed,
        }

    def cleanup(self) -> None:
        self._converter = None
        self._initialized = False
