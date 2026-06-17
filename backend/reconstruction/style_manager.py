"""
Style Manager — DOCX style configuration.

Manages document styles including fonts, headings, body text, captions,
and paragraph formatting to match the original document appearance.
Optimized for Bangla text with proper font fallbacks.
"""

from __future__ import annotations

from docx import Document as DocxDocument
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


class StyleManager:
    """Manages DOCX styles for document reconstruction."""

    # Bangla-capable fonts in priority order
    BANGLA_FONTS = [
        "Noto Sans Bengali",
        "SolaimanLipi",
        "Kalpurush",
        "Vrinda",
        "Arial Unicode MS",
    ]

    def apply_default_styles(self, doc: DocxDocument) -> None:
        """Apply default styling to the document with Bangla font support."""
        # Normal style — used for body text
        style = doc.styles["Normal"]
        font = style.font
        font.name = self.BANGLA_FONTS[0]
        font.size = Pt(11)
        style.paragraph_format.space_after = Pt(4)
        style.paragraph_format.space_before = Pt(2)
        style.paragraph_format.line_spacing = 1.15

        # Heading styles with Bangla font
        heading_configs = {
            1: {"size": 24, "bold": True, "space_before": 18, "space_after": 8},
            2: {"size": 20, "bold": True, "space_before": 14, "space_after": 6},
            3: {"size": 16, "bold": True, "space_before": 12, "space_after": 4},
            4: {"size": 14, "bold": True, "space_before": 10, "space_after": 4},
            5: {"size": 12, "bold": True, "space_before": 8, "space_after": 2},
            6: {"size": 11, "bold": True, "space_before": 6, "space_after": 2},
        }

        for level, config in heading_configs.items():
            heading_name = f"Heading {level}"
            if heading_name in doc.styles:
                h_style = doc.styles[heading_name]
                h_style.font.name = self.BANGLA_FONTS[0]
                h_style.font.bold = config["bold"]
                h_style.font.size = Pt(config["size"])
                h_style.paragraph_format.space_before = Pt(config["space_before"])
                h_style.paragraph_format.space_after = Pt(config["space_after"])
                h_style.paragraph_format.line_spacing = 1.2

        # List styles
        for list_style_name in ["List Bullet", "List Number"]:
            if list_style_name in doc.styles:
                list_style = doc.styles[list_style_name]
                list_style.font.name = self.BANGLA_FONTS[0]
                list_style.font.size = Pt(11)
                list_style.paragraph_format.space_after = Pt(2)


class PageBuilder:
    """Placeholder for per-page building logic (used by DocxBuilder)."""
    pass
