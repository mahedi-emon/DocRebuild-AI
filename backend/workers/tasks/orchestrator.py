"""
Pipeline Orchestrator — Master task that chains all processing stages.

This is the entry point for document processing. It sequentially executes
all 12 pipeline stages, handling errors, progress reporting, and stage transitions.

Runs directly in-process (no Celery/Redis required).
"""

from __future__ import annotations

import time
import traceback
import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import get_settings
from app.models.document import Document
from app.models.job import Job, JobStatus, PipelineStage

logger = logging.getLogger(__name__)
settings = get_settings()

import json
from app.utils.text_utils import make_json_serializable

def custom_json_dumps(obj, **kwargs):
    return json.dumps(make_json_serializable(obj), **kwargs)

# Synchronous DB engine for background workers
sync_engine = create_engine(
    settings.database_url.replace("sqlite+aiosqlite", "sqlite"),
    connect_args={"check_same_thread": False},
    json_serializer=custom_json_dumps,
)
SyncSession = sessionmaker(bind=sync_engine)


def get_sync_db() -> Session:
    """Get a synchronous database session for use in background tasks."""
    return SyncSession()


def update_job_stage(
    db: Session,
    job_id: str,
    stage: PipelineStage,
    progress: float = 0.0,
) -> None:
    """Update job stage and progress in the database."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if job:
        job.update_stage(stage, progress)
        db.commit()


def complete_job_stage(db: Session, job_id: str, stage: PipelineStage) -> None:
    """Mark a pipeline stage as complete."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if job:
        job.mark_stage_complete(stage)
        db.commit()


def process_document(document_id: str, job_id: str, options: dict | None = None):
    """
    Master orchestrator task — processes a document through all pipeline stages.
    Runs directly in-process (called from a background thread).

    Args:
        document_id: UUID of the document to process
        job_id: UUID of the processing job
        options: Processing options (engine toggles, thresholds, etc.)
    """
    options = options or {}
    db = get_sync_db()

    try:
        # Mark job as running
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = JobStatus.RUNNING.value
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        logger.info(f"Starting pipeline for document {document_id}, job {job_id}")

        # ── Stage 1: PDF Ingestion ──
        _run_stage(
            db, job_id, document_id, PipelineStage.PDF_INGESTION,
            "workers.tasks.pdf_ingestion", "ingest_pdf",
            {"document_id": document_id, "job_id": job_id, "dpi": options.get("dpi", 300)},
        )

        # ── Stage 2: Layout Analysis ──
        _run_stage(
            db, job_id, document_id, PipelineStage.LAYOUT_ANALYSIS,
            "workers.tasks.layout_analysis", "analyze_layout",
            {"document_id": document_id, "job_id": job_id},
            optional=True,  # Skip if DocLayout-YOLO not available
        )

        # ── Stage 3: OCR Ensemble ──
        _run_stage(
            db, job_id, document_id, PipelineStage.OCR_ENSEMBLE,
            "workers.tasks.ocr_ensemble", "run_ocr_ensemble",
            {"document_id": document_id, "job_id": job_id, "options": options},
        )

        # ── Stage 4: Document Understanding ──
        _run_stage(
            db, job_id, document_id, PipelineStage.DOCUMENT_UNDERSTANDING,
            "workers.tasks.document_understanding", "understand_document",
            {"document_id": document_id, "job_id": job_id},
            optional=True,
        )

        # ── Stage 5: Vision Validation ──
        if options.get("enable_vision_validation", True):
            _run_stage(
                db, job_id, document_id, PipelineStage.VISION_VALIDATION,
                "workers.tasks.vision_validation", "validate_with_vision",
                {"document_id": document_id, "job_id": job_id},
                optional=True,
            )
        else:
            complete_job_stage(db, job_id, PipelineStage.VISION_VALIDATION)

        # ── Stage 6: Table Extraction ──
        _run_stage(
            db, job_id, document_id, PipelineStage.TABLE_EXTRACTION,
            "workers.tasks.table_extraction", "extract_tables",
            {"document_id": document_id, "job_id": job_id},
            optional=True,
        )

        # ── Stage 7: Math Recognition ──
        _run_stage(
            db, job_id, document_id, PipelineStage.MATH_RECOGNITION,
            "workers.tasks.math_recognition", "recognize_math",
            {"document_id": document_id, "job_id": job_id},
            optional=True,
        )

        # ── Stage 8: Bangla Validation ──
        if options.get("enable_bangla_validation", True):
            _run_stage(
                db, job_id, document_id, PipelineStage.BANGLA_VALIDATION,
                "workers.tasks.bangla_validation", "validate_bangla",
                {"document_id": document_id, "job_id": job_id},
                optional=True,
            )
        else:
            complete_job_stage(db, job_id, PipelineStage.BANGLA_VALIDATION)

        # ── Stage 9: DOCX Reconstruction ──
        _run_stage(
            db, job_id, document_id, PipelineStage.DOCX_RECONSTRUCTION,
            "workers.tasks.docx_reconstruction", "reconstruct_docx",
            {"document_id": document_id, "job_id": job_id},
        )

        # ── Stage 10: Quality Assurance ──
        _run_stage(
            db, job_id, document_id, PipelineStage.QUALITY_ASSURANCE,
            "workers.tasks.quality_assurance", "run_qa",
            {"document_id": document_id, "job_id": job_id},
            optional=True,
        )

        # ── Stage 11: Self-Correction ──
        if options.get("enable_self_correction", True):
            _run_stage(
                db, job_id, document_id, PipelineStage.SELF_CORRECTION,
                "workers.tasks.self_correction", "run_self_correction",
                {
                    "document_id": document_id,
                    "job_id": job_id,
                    "max_passes": options.get("max_repair_passes", 3),
                },
                optional=True,
            )
        else:
            complete_job_stage(db, job_id, PipelineStage.SELF_CORRECTION)

        # ── Stage 12: Visual Verification ──
        _run_stage(
            db, job_id, document_id, PipelineStage.VISUAL_VERIFICATION,
            "workers.tasks.visual_verification", "verify_visual",
            {"document_id": document_id, "job_id": job_id},
            optional=True,
        )

        # ── Mark Complete ──
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.mark_completed()

        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.status = "completed"

        db.commit()
        logger.info(f"Pipeline completed successfully for document {document_id}")

        return {"status": "completed", "document_id": document_id, "job_id": job_id}

    except Exception as e:
        logger.error(f"Pipeline failed for document {document_id}: {e}")
        logger.error(traceback.format_exc())

        # Mark job as failed
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            current_stage = PipelineStage(job.current_stage) if job.current_stage else PipelineStage.QUEUED
            job.mark_failed(current_stage, str(e))

        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.status = "failed"
            document.error_message = str(e)

        db.commit()

        return {
            "status": "failed",
            "document_id": document_id,
            "job_id": job_id,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
    finally:
        db.close()


def _run_stage(
    db: Session,
    job_id: str,
    document_id: str,
    stage: PipelineStage,
    module_name: str,
    function_name: str,
    kwargs: dict,
    optional: bool = False,
) -> dict:
    """
    Execute a single pipeline stage and handle progress/error tracking.
    Calls the stage function directly (synchronous) within the orchestrator.

    Args:
        optional: If True, stage failures are logged as warnings but don't stop the pipeline.
    """
    import importlib
    import gc

    update_job_stage(db, job_id, stage, 0.0)
    stage_start = time.time()
    logger.info(f"═══ Starting stage: {stage.value} ═══")

    try:
        module = importlib.import_module(module_name)
        func = getattr(module, function_name)
        result = func(**kwargs)
        elapsed = time.time() - stage_start
        complete_job_stage(db, job_id, stage)
        logger.info(f"═══ Completed stage: {stage.value} in {elapsed:.1f}s ═══")
        return result or {}
    except Exception as e:
        elapsed = time.time() - stage_start
        if optional:
            logger.warning(f"═══ Optional stage {stage.value} failed after {elapsed:.1f}s (skipping): {e} ═══")
            complete_job_stage(db, job_id, stage)
            return {}
        else:
            logger.error(f"═══ Required stage {stage.value} FAILED after {elapsed:.1f}s: {e} ═══")
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.mark_failed(stage, str(e))
            db.commit()
            raise
    finally:
        # Force garbage collection after each stage to prevent RAM accumulation
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

