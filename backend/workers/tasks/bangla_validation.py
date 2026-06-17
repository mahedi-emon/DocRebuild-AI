"""Bangla Validation Task — Stage 8"""
from __future__ import annotations
import logging
from app.models.page import Page
from app.config import get_settings
logger = logging.getLogger(__name__)
settings = get_settings()

def validate_bangla(document_id: str, job_id: str) -> dict:
    from workers.tasks.orchestrator import get_sync_db
    from engines.language.bangla_validator import BanglaValidator
    db = get_sync_db()
    try:
        pages = db.query(Page).filter(Page.document_id == document_id).order_by(Page.page_number).all()
        validator = BanglaValidator(dictionary_path=str(settings.bangla_dictionary_path))
        for page in pages:
            ocr = page.ocr_json or {}
            text = ocr.get("full_text", "")
            if not text: continue
            result = validator.validate_text(text)
            if result["invalid_words"]:
                logger.info(f"Page {page.page_number}: {len(result['invalid_words'])} invalid Bangla words")
                ocr["bangla_validation"] = result
                page.ocr_json = ocr
                db.commit()
        return {"status": "success"}
    finally: db.close()
