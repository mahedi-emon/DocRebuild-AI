"""Self-Correction Task — Stage 11"""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

def run_self_correction(document_id: str, job_id: str, max_passes: int = 3) -> dict:
    from workers.tasks.orchestrator import get_sync_db
    from app.models.page import Page
    db = get_sync_db()
    try:
        pages = db.query(Page).filter(Page.document_id == document_id).all()
        corrections = 0
        for pass_num in range(max_passes):
            pass_corrections = 0
            for page in pages:
                ocr = page.ocr_json or {}
                confidence = ocr.get("overall_confidence", 1.0)
                if confidence < 0.6:
                    logger.info(f"Pass {pass_num+1}: Page {page.page_number} needs correction (conf={confidence:.2f})")
                    pass_corrections += 1
            corrections += pass_corrections
            if pass_corrections == 0: break
        return {"status": "success", "corrections": corrections, "passes": pass_num + 1}
    finally: db.close()
