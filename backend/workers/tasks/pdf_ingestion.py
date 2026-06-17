"""
PDF Ingestion Task — Stage 1

Converts PDF pages to high-resolution images and creates Page records in the database.
For image inputs (PNG, JPG, etc.), copies/converts the image directly.
"""

from __future__ import annotations

import shutil
import logging
from pathlib import Path

from PIL import Image

from app.config import get_settings
from app.models.document import Document
from app.models.page import Page
from app.utils.pdf_utils import render_pdf_pages

logger = logging.getLogger(__name__)
settings = get_settings()


def ingest_pdf(document_id: str, job_id: str, dpi: int = 300) -> dict:
    """
    Render all PDF pages as images and create Page records.
    For image files (not PDF), creates a single Page record.
    """
    from workers.tasks.orchestrator import get_sync_db

    db = get_sync_db()

    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        file_path = Path(document.file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Document file not found: {file_path}")

        # Output directory for page images
        pages_dir = settings.upload_dir / document_id / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)

        pages_data = []

        if document.file_type == "pdf":
            # Render PDF pages
            logger.info(f"Rendering PDF pages at {dpi} DPI...")
            pages_data = render_pdf_pages(
                pdf_path=str(file_path),
                output_dir=str(pages_dir),
                dpi=dpi,
            )
            logger.info(f"Rendered {len(pages_data)} PDF pages")
        else:
            # Single image input (PNG, JPG, JPEG, TIFF, BMP)
            logger.info(f"Processing single image: {file_path.name}")
            image_dest = pages_dir / "page_0001.png"

            # Always open and save as PNG for consistency
            img = Image.open(str(file_path)).convert("RGB")
            img.save(str(image_dest))
            width, height = img.size

            pages_data = [{
                "page_number": 1,
                "image_path": str(image_dest),
                "width": width,
                "height": height,
                "dpi": dpi,
            }]
            logger.info(f"Image saved: {width}x{height} pixels")

        # Create Page records
        for page_info in pages_data:
            page = Page(
                document_id=document_id,
                page_number=page_info["page_number"],
                image_path=page_info["image_path"],
                width=page_info["width"],
                height=page_info["height"],
                dpi=page_info.get("dpi", dpi),
            )
            db.add(page)

        # Update document page count
        document.page_count = len(pages_data)
        db.commit()

        logger.info(f"PDF ingestion complete: {len(pages_data)} pages for document {document_id}")

        return {
            "status": "success",
            "page_count": len(pages_data),
            "pages": [
                {"page_number": p["page_number"], "image_path": p["image_path"]}
                for p in pages_data
            ],
        }

    except Exception as e:
        logger.error(f"PDF ingestion failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()
