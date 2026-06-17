"""
Style Manager — DOCX style configuration.

Manages document styles including fonts, headings, body text, captions,
and paragraph formatting to match the original document appearance.
"""

from __future__ import annotations

from docx import Document as DocxDocument
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


class StyleManager:
    """Manages DOCX styles for document reconstruction."""

    def apply_default_styles(self, doc: DocxDocument) -> None:
        """Apply default styling to the document."""
        style = doc.styles["Normal"]
        font = style.font
        font.name = "Noto Sans Bengali"  # Good Bangla support
        font.size = Pt(11)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.line_spacing = 1.15

        # Heading styles
        for level in range(1, 7):
            heading_name = f"Heading {level}"
            if heading_name in doc.styles:
                h_style = doc.styles[heading_name]
                h_style.font.name = "Noto Sans Bengali"
                h_style.font.bold = True
                sizes = {1: 24, 2: 20, 3: 16, 4: 14, 5: 12, 6: 11}
                h_style.font.size = Pt(sizes.get(level, 11))
                h_style.paragraph_format.space_before = Pt(18)
                h_style.paragraph_format.space_after = Pt(6)


class PageBuilder:
    """Placeholder for per-page building logic (used by DocxBuilder)."""
    pass
