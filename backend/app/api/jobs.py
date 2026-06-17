"""
Jobs API — Start processing jobs, check status, and track progress.

Uses background threading for processing (no Celery/Redis required).
"""

from __future__ import annotations

import threading
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.document import Document
from app.models.job import Job, JobStatus
from app.schemas.job import (
    JobStartRequest,
    JobStartResponse,
    JobResponse,
    JobProgressResponse,
    StageDetail,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Track active processing threads
_active_threads: dict[str, threading.Thread] = {}


def _run_pipeline_in_background(document_id: str, job_id: str, options: dict):
    """Run the pipeline orchestrator in a background thread."""
    try:
        from workers.tasks.orchestrator import process_document
        result = process_document(
            document_id=document_id,
            job_id=job_id,
            options=options,
        )
        logger.info(f"Pipeline finished: {result.get('status', 'unknown')}")
    except Exception as e:
        logger.error(f"Pipeline thread crashed: {e}")
    finally:
        _active_threads.pop(job_id, None)


@router.post("/start/{document_id}", response_model=JobStartResponse, status_code=201)
async def start_job(
    document_id: str,
    options: JobStartRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Start a document processing job."""
    # Validate document exists
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check for existing active jobs
    existing = await db.execute(
        select(Job).where(
            Job.document_id == document_id,
            Job.status.in_([JobStatus.PENDING.value, JobStatus.RUNNING.value]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="An active job already exists for this document",
        )

    # Create job
    job = Job(
        document_id=document_id,
        status=JobStatus.PENDING.value,
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    # Update document status
    document.status = "processing"
    await db.commit()

    # Get job id before starting thread
    job_id = job.id
    opts = options.model_dump() if options else {}

    # Launch processing in a background thread (no Celery/Redis required)
    thread = threading.Thread(
        target=_run_pipeline_in_background,
        args=(document_id, job_id, opts),
        daemon=True,
        name=f"pipeline-{job_id[:8]}",
    )
    thread.start()
    _active_threads[job_id] = thread
    logger.info(f"Started pipeline thread for job {job_id}")

    return job


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get job details by ID."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/progress", response_model=JobProgressResponse)
async def get_job_progress(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed job progress including per-stage status."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    elapsed = None
    remaining = None
    if job.started_at:
        started_at = job.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        if job.progress > 0 and job.progress < 100:
            remaining = (elapsed / job.progress) * (100 - job.progress)

    return JobProgressResponse(
        job_id=job.id,
        status=job.status,
        current_stage=job.current_stage,
        progress=job.progress,
        stage_details=(
            {k: StageDetail(**v) for k, v in job.stage_details.items()}
            if job.stage_details
            else None
        ),
        elapsed_seconds=elapsed,
        estimated_remaining_seconds=remaining,
    )


@router.post("/{job_id}/cancel", status_code=200)
async def cancel_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running job."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in [JobStatus.PENDING.value, JobStatus.RUNNING.value]:
        raise HTTPException(status_code=400, detail="Job is not active")

    job.status = JobStatus.CANCELLED.value
    job.completed_at = datetime.now(timezone.utc)

    # Update document status
    doc_result = await db.execute(
        select(Document).where(Document.id == job.document_id)
    )
    document = doc_result.scalar_one_or_none()
    if document:
        document.status = "uploaded"

    # Remove from active threads
    _active_threads.pop(job_id, None)

    return {"message": "Job cancelled", "job_id": job_id}


@router.get("/document/{document_id}", response_model=list[JobResponse])
async def list_jobs_for_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all jobs for a document."""
    result = await db.execute(
        select(Job)
        .where(Job.document_id == document_id)
        .order_by(Job.created_at.desc())
    )
    return result.scalars().all()
