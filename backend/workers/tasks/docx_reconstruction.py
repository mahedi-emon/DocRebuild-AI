"""DOCX Reconstruction Task — Stage 9"""
from __future__ import annotations
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
        pages = db.query(Page).filter(Page.document_id == document_id).order_by(Page.page_number).all()
        if not doc or not pages: raise ValueError("Document or pages not found")
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
        output_dir = settings.output_dir / document_id
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(doc.original_filename).stem
        output_path = str(output_dir / f"{stem}_reconstructed.docx")
        builder = DocxBuilder()
        builder.build(pages_data, output_path)
        doc.output_path = output_path
        db.commit()
        return {"status": "success", "output_path": output_path}
    finally: db.close()
