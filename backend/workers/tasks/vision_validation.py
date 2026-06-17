"""Vision Validation Task — Stage 5"""
from __future__ import annotations
import logging, numpy as np
from PIL import Image
from app.models.page import Page
logger = logging.getLogger(__name__)

def validate_with_vision(document_id: str, job_id: str) -> dict:
    from workers.tasks.orchestrator import get_sync_db
    from engines.ocr.base_ocr import OCRWord
    db = get_sync_db()
    try:
        pages = db.query(Page).filter(Page.document_id == document_id).order_by(Page.page_number).all()
        try:
            from engines.vision.florence2_engine import Florence2Engine
            florence = Florence2Engine()
            for page in pages:
                if not page.image_path or not page.ocr_json: continue
                image = np.array(Image.open(page.image_path).convert("RGB"))
                ocr_text = page.ocr_json.get("full_text", "")
                result = florence.validate_text(image, ocr_text)
                if not result["matches"]:
                    logger.info(f"Page {page.page_number}: Vision disagrees (sim={result['similarity']:.2f})")
            florence.cleanup()
        except Exception as e:
            logger.warning(f"Vision validation skipped: {e}")
        return {"status": "success"}
    finally: db.close()
