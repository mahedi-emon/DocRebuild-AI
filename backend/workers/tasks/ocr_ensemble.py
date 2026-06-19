"""
OCR Ensemble Task — Stage 3

Runs the multi-OCR ensemble on all pages of a document.
Includes image pre-processing (contrast enhancement, denoising)
for improved OCR accuracy on scanned documents.
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
    """Run OCR ensemble on all pages of a document sequentially, engine-by-engine."""
    from workers.tasks.orchestrator import get_sync_db, update_job_stage
    from app.models.job import PipelineStage
    from engines.ocr.ensemble import create_ensemble
    import gc

    # Set thread limits inside background worker thread to prevent OpenMP/MKL deadlocks
    try:
        import torch
        torch.set_num_threads(4)
    except ImportError:
        pass
    try:
        import cv2
        cv2.setNumThreads(0)
    except ImportError:
        pass

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

        # Create ensemble wrapper
        ensemble = create_ensemble()
        
        # Results accumulator: page.page_number -> {engine_name: OCRResult}
        results_by_page = {page.page_number: {} for page in pages}
        
        # Filter engines that will actually run based on requested languages (default 'bn', 'en', and 'ar')
        languages = ["bn", "en", "ar"]
        engines_to_run = []
        for engine in ensemble._engines:
            # Check availability first to filter out engines without installed dependencies/executables
            if not engine.is_available():
                logger.warning(f"OCR engine '{engine.name}' is enabled in settings but dependencies are not available. Skipping.")
                continue

            if languages:
                if "bn" in languages:
                    if "bn" in engine.supported_languages:
                        engines_to_run.append(engine)
                else:
                    if any(lang in engine.supported_languages for lang in languages):
                        engines_to_run.append(engine)
            else:
                engines_to_run.append(engine)

        if not engines_to_run:
            logger.warning("No OCR engines match the requested languages. Using all registered engines as fallback.")
            engines_to_run = ensemble._engines

        total_engines = len(engines_to_run)
        total_pages = len(pages)
        # Total steps: (number of engines * number of pages) + number of pages for fusion
        total_steps = (total_engines * total_pages) + total_pages
        step_count = 0

        logger.info(f"Starting sequential OCR run with {total_engines} engines: {[e.name for e in engines_to_run]}")

        for engine_idx, engine in enumerate(engines_to_run):
            try:
                # Initialize the engine (loads model weights into RAM)
                logger.info(f"Loading/initializing OCR engine: {engine.name}")
                engine.initialize()
                
                for idx, page in enumerate(pages):
                    # Update progress
                    progress = (step_count / total_steps) * 100
                    update_job_stage(db, job_id, PipelineStage.OCR_ENSEMBLE, progress)
                    step_count += 1

                    if not page.image_path:
                        logger.warning(f"Page {page.page_number} has no image, skipping OCR")
                        continue

                    # Load and preprocess image on the fly with context manager
                    with Image.open(page.image_path) as img:
                        image = np.array(img.convert("RGB"))

                    # Only preprocess for Tesseract engine
                    if engine.name == "tesseract":
                        ocr_input_image = _preprocess_image(image)
                    else:
                        ocr_input_image = image

                    # Run recognition on appropriate image
                    logger.info(f"Running engine '{engine.name}' on page {page.page_number}...")
                    result = engine.recognize(ocr_input_image, languages=languages)
                    results_by_page[page.page_number][engine.name] = result

            except Exception as e:
                logger.error(f"Engine {engine.name} failed during sequential document run: {e}")
            finally:
                # Always cleanup/unload the model immediately to free memory
                logger.info(f"Unloading/cleaning up OCR engine: {engine.name}")
                engine.cleanup()
                gc.collect()

        # Step 2: Fuse results page-by-page
        results_summary = []
        for idx, page in enumerate(pages):
            progress = (step_count / total_steps) * 100
            update_job_stage(db, job_id, PipelineStage.OCR_ENSEMBLE, progress)
            step_count += 1

            page_results = results_by_page[page.page_number]
            if not page_results:
                logger.warning(f"Page {page.page_number} has no OCR results, skipping fusion")
                continue

            # Fuse results from all engines for this page
            result = ensemble.fuse_results(page_results)

            # Store results in DB
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
                f"Fused Page {page.page_number}: {len(result.words)} words, "
                f"{len(result.lines)} lines, "
                f"confidence={result.overall_confidence:.3f}"
            )

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


def _preprocess_image(image: np.ndarray) -> np.ndarray:
    """
    Pre-process image for better OCR accuracy.
    Uses contrast enhancement and denoising while preserving color
    for engines that benefit from it.
    """
    try:
        from app.utils.image_utils import preprocess_for_ocr
        processed = preprocess_for_ocr(image)
        logger.debug("Image pre-processed with contrast enhancement and denoising")
        return processed
    except ImportError:
        logger.warning("Could not import image pre-processing utilities, using raw image")
        return image
    except Exception as e:
        logger.warning(f"Image pre-processing failed, using raw image: {e}")
        return image
