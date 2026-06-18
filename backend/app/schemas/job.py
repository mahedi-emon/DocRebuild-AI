"""
Job Pydantic Schemas

Request/Response models for job-related API endpoints.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class JobStartRequest(BaseModel):
    """Options for starting a processing job."""
    enable_vision_validation: bool = True
    enable_bangla_validation: bool = True
    enable_self_correction: bool = True
    max_repair_passes: int = 3
    target_confidence: float = 0.85
    ocr_engines: list[str] | None = None  # None = use all enabled
    dpi: int = 300


class JobStartResponse(BaseModel):
    id: str
    document_id: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StageDetail(BaseModel):
    progress: float
    status: str
    timestamp: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None


class JobResponse(BaseModel):
    id: str
    document_id: str
    status: str
    current_stage: str | None = None
    progress: float
    stage_details: dict[str, StageDetail] | None = None
    celery_task_id: str | None = None
    error_message: str | None = None
    error_stage: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobProgressResponse(BaseModel):
    job_id: str
    status: str
    current_stage: str | None = None
    progress: float
    stage_details: dict[str, StageDetail] | None = None
    elapsed_seconds: float | None = None
    estimated_remaining_seconds: float | None = None
