"""Document Understanding Task — Stage 4

Runs document understanding engines (Docling, Marker) to extract
high-quality structured text (markdown). Results are stored in the
Document model and used as the primary text source during DOCX reconstruction.
"""
from __future__ import annotations
import json
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
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        results = {}

        # Try Marker first (generally better for Bangla books)
        if settings.enable_marker:
            try:
                from engines.understanding.marker_engine import MarkerEngine
                engine = MarkerEngine()
                marker_result = engine.understand(doc.file_path)
                results["marker"] = marker_result
                logger.info(
                    f"Marker produced {len(marker_result.get('markdown', ''))} chars "
                    f"in {marker_result.get('processing_time_ms', 0):.0f}ms"
                )
                engine.cleanup()
            except Exception as e:
                logger.warning(f"Marker failed: {e}")
        else:
            logger.info("Marker engine is disabled in configuration")

        # Try Docling as secondary/fallback
        if settings.enable_docling:
            try:
                from engines.understanding.docling_engine import DoclingEngine
                engine = DoclingEngine()
                docling_result = engine.understand(doc.file_path)
                results["docling"] = docling_result
                logger.info(
                    f"Docling produced {len(docling_result.get('markdown', ''))} chars "
                    f"in {docling_result.get('processing_time_ms', 0):.0f}ms"
                )
                engine.cleanup()
            except Exception as e:
                logger.warning(f"Docling failed: {e}")
        else:
            logger.info("Docling engine is disabled in configuration")

        # Store the best result in the document record
        # Prefer Marker if both are available (usually better for Bangla)
        best_markdown = ""
        best_engine = ""
        if "marker" in results and results["marker"].get("markdown"):
            best_markdown = results["marker"]["markdown"]
            best_engine = "marker"
        elif "docling" in results and results["docling"].get("markdown"):
            best_markdown = results["docling"]["markdown"]
            best_engine = "docling"

        if best_markdown:
            understanding_data = json.dumps({
                "engine": best_engine,
                "markdown": best_markdown,
                "engines_tried": list(results.keys()),
            }, ensure_ascii=False)
            doc.understanding_json = understanding_data
            db.commit()
            logger.info(
                f"Stored {len(best_markdown)} chars of understanding text "
                f"from {best_engine} engine"
            )

        return {"status": "success", "engines_used": list(results.keys()), "primary_engine": best_engine}
    finally:
        db.close()
