"""
OCR Ensemble Task — Stage 3

Runs the multi-OCR ensemble on all pages of a document.
"""

from __future__ import annotations

import logging
import numpy as np
from PIL import Image

from app.config import get_settings
from app.models.document import Document
from app.models.page import Page

logger = logging.getLogger(__name__)
settings = get_settings()


def run_ocr_ensemble(document_id: str, job_id: str, options: dict | None = None) -> dict:
    """Run OCR ensemble on all pages of a document."""
    from workers.tasks.orchestrator import get_sync_db, update_job_stage
    from app.models.job import PipelineStage
    from engines.ocr.ensemble import create_ensemble

    db = get_sync_db()
    options = options or {}

    try:
        pages = (
            db.query(Page)
            .filter(Page.document_id == document_id)
            .order_by(Page.page_number)
            .all()
        )

        if not pages:
            raise ValueError(f"No pages found for document {document_id}")

        # Create and initialize ensemble
        ensemble = create_ensemble()
        initialized = ensemble.initialize_engines()
        logger.info(f"Initialized {len(initialized)} OCR engines: {initialized}")

        total_pages = len(pages)
        results_summary = []

        for idx, page in enumerate(pages):
            # Update progress
            progress = (idx / total_pages) * 100
            update_job_stage(db, job_id, PipelineStage.OCR_ENSEMBLE, progress)

            if not page.image_path:
                logger.warning(f"Page {page.page_number} has no image, skipping OCR")
                continue

            # Load page image
            image = np.array(Image.open(page.image_path).convert("RGB"))

            # Run ensemble
            result = ensemble.recognize(image, languages=["bn", "en"])

            # Store results
            page.ocr_json = result.to_dict()
            page.ocr_confidence = result.overall_confidence

            results_summary.append({
                "page_number": page.page_number,
                "word_count": len(result.words),
                "line_count": len(result.lines),
                "confidence": result.overall_confidence,
                "time_ms": result.processing_time_ms,
            })

            db.commit()
            logger.info(
                f"Page {page.page_number}: {len(result.words)} words, "
                f"confidence={result.overall_confidence:.3f}"
            )

        # Cleanup
        ensemble.cleanup_all()

        return {
            "status": "success",
            "pages_processed": len(results_summary),
            "results": results_summary,
        }

    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
