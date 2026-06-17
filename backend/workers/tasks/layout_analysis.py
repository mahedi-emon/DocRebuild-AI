"""Layout Analysis Task — Stage 2

Detects layout elements (titles, paragraphs, tables, figures, equations)
using DocLayout-YOLO. Falls back to simple full-page paragraph if YOLO unavailable.
"""
from __future__ import annotations
import logging
import numpy as np
from PIL import Image
from app.models.page import Page
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def analyze_layout(document_id: str, job_id: str) -> dict:
    """Analyze page layout using DocLayout-YOLO or fallback."""
    from workers.tasks.orchestrator import get_sync_db, update_job_stage
    from app.models.job import PipelineStage

    db = get_sync_db()
    try:
        pages = db.query(Page).filter(
            Page.document_id == document_id
        ).order_by(Page.page_number).all()

        if not pages:
            logger.warning(f"No pages found for document {document_id}")
            return {"status": "success", "pages": 0, "note": "no pages"}

        # Try to use DocLayout-YOLO
        yolo_available = False
        yolo = None
        if settings.enable_doclayout_yolo:
            try:
                from engines.layout.doclayout_yolo import DocLayoutYOLOEngine
                yolo = DocLayoutYOLOEngine()
                yolo_available = True
                logger.info("DocLayout-YOLO engine loaded")
            except Exception as e:
                logger.warning(f"DocLayout-YOLO not available: {e}")
        else:
            logger.info("DocLayout-YOLO is disabled in configuration")

        fusion = None
        try:
            from engines.layout.layout_fusion import LayoutFusionEngine
            fusion = LayoutFusionEngine()
        except Exception as e:
            logger.warning(f"Layout fusion engine not available: {e}")

        for idx, page in enumerate(pages):
            progress = (idx / len(pages)) * 100
            update_job_stage(db, job_id, PipelineStage.LAYOUT_ANALYSIS, progress)

            if not page.image_path:
                continue

            try:
                image = np.array(Image.open(page.image_path).convert("RGB"))
                img_h, img_w = image.shape[:2]

                if yolo_available and yolo and fusion:
                    yolo_results = yolo.detect(image)
                    layout = fusion.fuse(
                        [yolo_results],
                        page.width or img_w,
                        page.height or img_h,
                    )
                    page.layout_json = layout.to_dict()
                    page.layout_confidence = layout.confidence
                else:
                    # Fallback: treat entire page as a single paragraph
                    page.layout_json = {
                        "width": img_w,
                        "height": img_h,
                        "confidence": 0.5,
                        "element_count": 1,
                        "elements": [{
                            "type": "paragraph",
                            "bbox": [0, 0, img_w, img_h],
                            "confidence": 0.5,
                            "reading_order": 0,
                            "source": "fallback",
                        }],
                    }
                    page.layout_confidence = 0.5

                db.commit()
                logger.info(f"Page {page.page_number}: layout analyzed")

            except Exception as e:
                logger.warning(f"Layout analysis failed for page {page.page_number}: {e}")
                # Fallback to full-page paragraph
                page.layout_json = {
                    "width": page.width or 1000,
                    "height": page.height or 1400,
                    "confidence": 0.3,
                    "element_count": 1,
                    "elements": [{
                        "type": "paragraph",
                        "bbox": [0, 0, page.width or 1000, page.height or 1400],
                        "confidence": 0.3,
                        "reading_order": 0,
                        "source": "error_fallback",
                    }],
                }
                page.layout_confidence = 0.3
                db.commit()

        # Cleanup YOLO model
        if yolo:
            try:
                yolo.cleanup()
            except Exception:
                pass

        return {"status": "success", "pages": len(pages)}
    except Exception as e:
        logger.error(f"Layout analysis failed: {e}")
        raise
    finally:
        db.close()
