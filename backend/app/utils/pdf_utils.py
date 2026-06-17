"""
PDF Utilities — Page counting, rendering, and metadata extraction.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF


def get_pdf_page_count(pdf_path: str) -> int:
    """Get the number of pages in a PDF file."""
    try:
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


def render_pdf_pages(
    pdf_path: str,
    output_dir: str,
    dpi: int = 300,
    pages: Optional[list[int]] = None,
) -> list[dict]:
    """
    Render PDF pages to high-resolution PNG images.

    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save page images
        dpi: Resolution in dots per inch (default 300)
        pages: Optional list of page numbers to render (0-indexed). None = all pages.

    Returns:
        List of dicts with page_number, image_path, width, height
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0  # 72 DPI is the default PDF resolution
    matrix = fitz.Matrix(zoom, zoom)

    results = []
    page_range = pages if pages else range(len(doc))

    for page_num in page_range:
        if page_num >= len(doc):
            continue

        page = doc[page_num]
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        image_filename = f"page_{page_num + 1:04d}.png"
        image_path = output_path / image_filename
        pix.save(str(image_path))

        results.append({
            "page_number": page_num + 1,  # 1-indexed for display
            "image_path": str(image_path),
            "width": pix.width,
            "height": pix.height,
            "dpi": dpi,
        })

    doc.close()
    return results


def get_pdf_metadata(pdf_path: str) -> dict:
    """Extract metadata from a PDF file."""
    try:
        doc = fitz.open(pdf_path)
        metadata = doc.metadata or {}
        result = {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "subject": metadata.get("subject", ""),
            "creator": metadata.get("creator", ""),
            "producer": metadata.get("producer", ""),
            "page_count": len(doc),
            "page_sizes": [],
        }
        for page in doc:
            rect = page.rect
            result["page_sizes"].append({
                "width_pt": rect.width,
                "height_pt": rect.height,
                "width_in": rect.width / 72.0,
                "height_in": rect.height / 72.0,
            })
        doc.close()
        return result
    except Exception as e:
        return {"error": str(e)}
