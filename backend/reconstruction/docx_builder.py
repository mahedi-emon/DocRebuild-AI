"""
DOCX Builder — Main document reconstruction engine.

Orchestrates per-page reconstruction, applying styles, spacing, images,
tables, and equations to produce an editable DOCX file that faithfully
reconstructs the original document's layout.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from docx import Document as DocxDocument
from docx.shared import Inches, Pt, Cm, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT

from app.config import get_settings
from reconstruction.style_manager import StyleManager
from reconstruction.page_builder import PageBuilder
from reconstruction.table_builder import TableBuilder
from reconstruction.equation_builder import EquationBuilder
from reconstruction.image_inserter import ImageInserter

logger = logging.getLogger(__name__)
settings = get_settings()


class DocxBuilder:
    """
    Main DOCX reconstruction engine.

    Takes the processed page data (layout, OCR, tables, equations) and
    produces a fully editable DOCX file preserving the original layout.
    """

    def __init__(self):
        self._doc: DocxDocument | None = None
        self._style_manager = StyleManager()
        self._page_builder = PageBuilder()
        self._table_builder = TableBuilder()
        self._equation_builder = EquationBuilder()
        self._image_inserter = ImageInserter()

    def build(
        self,
        pages_data: list[dict],
        output_path: str,
        page_width_inches: float = 8.27,  # A4
        page_height_inches: float = 11.69,  # A4
        margin_inches: float = 1.0,
    ) -> str:
        """
        Build a DOCX document from processed page data.

        Args:
            pages_data: List of per-page dicts with layout, OCR, tables, equations
            output_path: Where to save the generated DOCX
            page_width_inches: Page width (default A4)
            page_height_inches: Page height (default A4)
            margin_inches: Page margins

        Returns:
            Path to the generated DOCX file
        """
        self._doc = DocxDocument()

        # Configure page layout
        self._setup_page(page_width_inches, page_height_inches, margin_inches)

        # Apply base styles
        self._style_manager.apply_default_styles(self._doc)

        # Process each page
        for page_idx, page_data in enumerate(pages_data):
            logger.info(f"Building page {page_idx + 1}/{len(pages_data)}")

            if page_idx > 0:
                # Add page break between pages
                self._doc.add_page_break()

            self._build_page(page_data)

        # Save
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        self._doc.save(str(output_file))

        logger.info(f"DOCX saved to {output_file}")
        return str(output_file)

    def _setup_page(
        self,
        width_inches: float,
        height_inches: float,
        margin_inches: float,
    ) -> None:
        """Configure page dimensions and margins."""
        section = self._doc.sections[0]
        section.page_width = Inches(width_inches)
        section.page_height = Inches(height_inches)
        section.top_margin = Inches(margin_inches)
        section.bottom_margin = Inches(margin_inches)
        section.left_margin = Inches(margin_inches)
        section.right_margin = Inches(margin_inches)

    def _build_page(self, page_data: dict) -> None:
        """
        Reconstruct a single page from its processed data.

        Expected page_data structure:
        {
            'page_number': int,
            'layout': {'elements': [...]},
            'ocr': {'lines': [...], 'full_text': str},
            'tables': [...],
            'equations': [...],
            'image_path': str,
        }
        """
        layout = page_data.get("layout", {})
        ocr_data = page_data.get("ocr", {})
        tables = page_data.get("tables", [])
        equations = page_data.get("equations", [])
        image_path = page_data.get("image_path", "")

        elements = layout.get("elements", [])

        if not elements:
            # Fallback: just add all OCR text as paragraphs
            full_text = ocr_data.get("full_text", "")
            if full_text:
                for line in full_text.split("\n"):
                    if line.strip():
                        self._doc.add_paragraph(line.strip())
            return

        # Process elements in reading order
        table_idx = 0
        equation_idx = 0

        for element in sorted(elements, key=lambda e: e.get("reading_order", 0)):
            element_type = element.get("type", "unknown")
            bbox = element.get("bbox", [0, 0, 100, 100])

            try:
                if element_type == "title":
                    self._add_title(element, ocr_data)
                elif element_type == "subtitle":
                    self._add_subtitle(element, ocr_data)
                elif element_type in ("paragraph", "unknown"):
                    self._add_paragraph(element, ocr_data)
                elif element_type == "table" and table_idx < len(tables):
                    self._table_builder.add_table(self._doc, tables[table_idx])
                    table_idx += 1
                elif element_type == "equation" and equation_idx < len(equations):
                    self._equation_builder.add_equation(self._doc, equations[equation_idx])
                    equation_idx += 1
                elif element_type in ("image", "figure"):
                    self._image_inserter.add_image(self._doc, element, image_path)
                elif element_type == "caption":
                    self._add_caption(element, ocr_data)
                elif element_type == "header":
                    pass  # Headers handled separately
                elif element_type == "footer":
                    pass  # Footers handled separately
                elif element_type == "list":
                    self._add_list(element, ocr_data)
                elif element_type == "exercise":
                    self._add_exercise(element, ocr_data)
                else:
                    # Default: treat as paragraph
                    self._add_paragraph(element, ocr_data)
            except Exception as e:
                logger.warning(f"Error processing {element_type}: {e}")
                # Fallback: add as plain text
                text = self._get_text_for_region(element, ocr_data)
                if text:
                    self._doc.add_paragraph(text)

    def _get_text_for_region(self, element: dict, ocr_data: dict) -> str:
        """Extract OCR text that falls within a layout element's bounding box."""
        bbox = element.get("bbox", [0, 0, 0, 0])
        lines = ocr_data.get("lines", [])

        matching_text = []
        for line in lines:
            line_bbox = line.get("bbox", [0, 0, 0, 0])
            # Check if line overlaps with element bbox
            if self._bboxes_overlap(bbox, line_bbox):
                matching_text.append(line.get("text", ""))

        return " ".join(matching_text) if matching_text else ""

    def _bboxes_overlap(self, bbox1: list, bbox2: list) -> bool:
        """Check if two bounding boxes overlap significantly."""
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])

        if x1 >= x2 or y1 >= y2:
            return False

        intersection = (x2 - x1) * (y2 - y1)
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])

        return intersection / max(area2, 1) > 0.3

    def _add_title(self, element: dict, ocr_data: dict) -> None:
        text = self._get_text_for_region(element, ocr_data)
        if text:
            para = self._doc.add_heading(text, level=1)
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def _add_subtitle(self, element: dict, ocr_data: dict) -> None:
        text = self._get_text_for_region(element, ocr_data)
        if text:
            self._doc.add_heading(text, level=2)

    def _add_paragraph(self, element: dict, ocr_data: dict) -> None:
        text = self._get_text_for_region(element, ocr_data)
        if text:
            para = self._doc.add_paragraph(text)
            para.paragraph_format.space_after = Pt(6)

    def _add_caption(self, element: dict, ocr_data: dict) -> None:
        text = self._get_text_for_region(element, ocr_data)
        if text:
            para = self._doc.add_paragraph(text)
            para.style = "Caption" if "Caption" in self._doc.styles else para.style
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.runs[0] if para.runs else para.add_run("")
            run.italic = True
            run.font.size = Pt(9)

    def _add_list(self, element: dict, ocr_data: dict) -> None:
        text = self._get_text_for_region(element, ocr_data)
        if text:
            for item in text.split("\n"):
                item = item.strip()
                if item:
                    self._doc.add_paragraph(item, style="List Bullet")

    def _add_exercise(self, element: dict, ocr_data: dict) -> None:
        text = self._get_text_for_region(element, ocr_data)
        if text:
            para = self._doc.add_paragraph()
            run = para.add_run(text)
            run.font.size = Pt(11)
            para.paragraph_format.left_indent = Inches(0.5)
            para.paragraph_format.space_before = Pt(12)
