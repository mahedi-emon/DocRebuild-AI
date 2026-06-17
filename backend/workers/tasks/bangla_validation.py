"""Bangla Validation Task — Stage 8

Validates Bangla text and APPLIES corrections back to the OCR data.
Previously this only logged validation results without fixing anything.
"""
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
        pages = db.query(Page).filter(
            Page.document_id == document_id
        ).order_by(Page.page_number).all()

        validator = BanglaValidator(
            dictionary_path=str(settings.bangla_dictionary_path)
        )

        total_corrections = 0
        total_invalid = 0

        for page in pages:
            ocr = page.ocr_json or {}
            text = ocr.get("full_text", "")
            if not text:
                continue

            result = validator.validate_text(text)
            invalid_count = len(result["invalid_words"])
            total_invalid += invalid_count

            if invalid_count > 0:
                logger.info(
                    f"Page {page.page_number}: {invalid_count} invalid Bangla words found"
                )

            # Apply corrections back to OCR data
            corrected_text = result.get("corrected_text", "")
            if corrected_text and corrected_text != text:
                ocr["full_text"] = corrected_text
                ocr["full_text_original"] = text  # Keep original for reference
                total_corrections += 1
                logger.info(
                    f"Page {page.page_number}: Applied Bangla text corrections"
                )

            # Store validation metadata
            ocr["bangla_validation"] = {
                "total_words": result["total_words"],
                "valid_words": result["valid_words"],
                "invalid_count": invalid_count,
                "confidence": result["confidence"],
            }

            page.ocr_json = ocr
            db.commit()

        logger.info(
            f"Bangla validation complete: {total_invalid} invalid words found, "
            f"{total_corrections} pages corrected"
        )
        return {
            "status": "success",
            "total_invalid_words": total_invalid,
            "pages_corrected": total_corrections,
        }
    finally:
        db.close()
