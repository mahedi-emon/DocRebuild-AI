"""Document Understanding Task — Stage 4"""
from __future__ import annotations
import logging
from app.models.document import Document
from app.config import get_settings
logger = logging.getLogger(__name__)
settings = get_settings()

def understand_document(document_id: str, job_id: str) -> dict:
    from workers.tasks.orchestrator import get_sync_db
    db = get_sync_db()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc: raise ValueError(f"Document {document_id} not found")
        results = {}
        if settings.enable_docling:
            try:
                from engines.understanding.docling_engine import DoclingEngine
                engine = DoclingEngine()
                results["docling"] = engine.understand(doc.file_path)
                engine.cleanup()
            except Exception as e:
                logger.warning(f"Docling failed: {e}")
        else:
            logger.info("Docling engine is disabled in configuration")
            
        if settings.enable_marker:
            try:
                from engines.understanding.marker_engine import MarkerEngine
                engine = MarkerEngine()
                results["marker"] = engine.understand(doc.file_path)
                engine.cleanup()
            except Exception as e:
                logger.warning(f"Marker failed: {e}")
        else:
            logger.info("Marker engine is disabled in configuration")
            
        return {"status": "success", "engines_used": list(results.keys())}
    finally: db.close()
