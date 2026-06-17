"""DOCX Reconstruction Task — Stage 9

Builds the final DOCX file from all processed data.
Uses the best available text source:
1. Docling/Marker text (if available — highest quality)
2. OCR ensemble text (fallback)
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from app.models.document import Document
from app.models.page import Page
from app.config import get_settings
logger = logging.getLogger(__name__)
settings = get_settings()

def reconstruct_docx(document_id: str, job_id: str) -> dict:
    from workers.tasks.orchestrator import get_sync_db
    from reconstruction.docx_builder import DocxBuilder
    db = get_sync_db()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        pages = db.query(Page).filter(
            Page.document_id == document_id
        ).order_by(Page.page_number).all()

        if not doc or not pages:
            raise ValueError("Document or pages not found")

        pages_data = []
        for page in pages:
            pages_data.append({
                "page_number": page.page_number,
                "layout": page.layout_json or {},
                "ocr": page.ocr_json or {},
                "tables": page.tables_json or [],
                "equations": page.equations_json or [],
                "image_path": page.image_path or "",
            })

        # Extract understanding text (Docling/Marker markdown) if available
        understanding_text = ""
        if doc.understanding_json:
            try:
                understanding_data = json.loads(doc.understanding_json)
                understanding_text = understanding_data.get("markdown", "")
                if understanding_text:
                    logger.info(
                        f"Using {understanding_data.get('engine', 'unknown')} engine text "
                        f"({len(understanding_text)} chars) for DOCX reconstruction"
                    )
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Could not parse understanding_json: {e}")

        output_dir = settings.output_dir / document_id
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(doc.original_filename).stem
        output_path = str(output_dir / f"{stem}_reconstructed.docx")

        builder = DocxBuilder()
        builder.build(
            pages_data,
            output_path,
            understanding_text=understanding_text,
        )

        doc.output_path = output_path
        db.commit()

        return {"status": "success", "output_path": output_path}
    finally:
        db.close()
