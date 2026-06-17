"""
Job ORM Model

Represents a processing job for a document, tracking pipeline stage progression,
progress percentage, and error state.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PipelineStage(str, enum.Enum):
    """Processing pipeline stages in execution order."""
    QUEUED = "queued"
    PDF_INGESTION = "pdf_ingestion"
    LAYOUT_ANALYSIS = "layout_analysis"
    OCR_ENSEMBLE = "ocr_ensemble"
    DOCUMENT_UNDERSTANDING = "document_understanding"
    VISION_VALIDATION = "vision_validation"
    TABLE_EXTRACTION = "table_extraction"
    MATH_RECOGNITION = "math_recognition"
    BANGLA_VALIDATION = "bangla_validation"
    DOCX_RECONSTRUCTION = "docx_reconstruction"
    QUALITY_ASSURANCE = "quality_assurance"
    SELF_CORRECTION = "self_correction"
    VISUAL_VERIFICATION = "visual_verification"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Ordered list of processing stages for progress calculation
PIPELINE_STAGES_ORDER = [
    PipelineStage.PDF_INGESTION,
    PipelineStage.LAYOUT_ANALYSIS,
    PipelineStage.OCR_ENSEMBLE,
    PipelineStage.DOCUMENT_UNDERSTANDING,
    PipelineStage.VISION_VALIDATION,
    PipelineStage.TABLE_EXTRACTION,
    PipelineStage.MATH_RECOGNITION,
    PipelineStage.BANGLA_VALIDATION,
    PipelineStage.DOCX_RECONSTRUCTION,
    PipelineStage.QUALITY_ASSURANCE,
    PipelineStage.SELF_CORRECTION,
    PipelineStage.VISUAL_VERIFICATION,
]

TOTAL_STAGES = len(PIPELINE_STAGES_ORDER)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.PENDING.value)
    current_stage: Mapped[str] = mapped_column(
        String(40), default=PipelineStage.QUEUED.value
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 to 100.0

    # Per-stage progress tracking (JSON: {stage_name: {progress: float, status: str}})
    stage_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Celery task ID for tracking/cancellation
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Error info
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_stage: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="jobs")

    def update_stage(self, stage: PipelineStage, stage_progress: float = 0.0) -> None:
        """Update the current pipeline stage and recalculate overall progress."""
        self.current_stage = stage.value
        self.status = JobStatus.RUNNING.value

        if stage in PIPELINE_STAGES_ORDER:
            stage_index = PIPELINE_STAGES_ORDER.index(stage)
            base_progress = (stage_index / TOTAL_STAGES) * 100
            stage_contribution = (stage_progress / 100.0) * (100.0 / TOTAL_STAGES)
            self.progress = min(base_progress + stage_contribution, 100.0)

        # Update stage details
        if self.stage_details is None:
            self.stage_details = {}
        self.stage_details[stage.value] = {
            "progress": stage_progress,
            "status": "running",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def mark_stage_complete(self, stage: PipelineStage) -> None:
        """Mark a stage as complete in stage_details."""
        if self.stage_details is None:
            self.stage_details = {}
        self.stage_details[stage.value] = {
            "progress": 100.0,
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def mark_completed(self) -> None:
        """Mark the entire job as completed."""
        self.status = JobStatus.COMPLETED.value
        self.current_stage = PipelineStage.COMPLETED.value
        self.progress = 100.0
        self.completed_at = datetime.now(timezone.utc)

    def mark_failed(self, stage: PipelineStage, error: str) -> None:
        """Mark the job as failed at a specific stage."""
        self.status = JobStatus.FAILED.value
        self.current_stage = PipelineStage.FAILED.value
        self.error_stage = stage.value
        self.error_message = error
        self.completed_at = datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return (
            f"<Job(id={self.id!r}, doc={self.document_id!r}, "
            f"stage={self.current_stage!r}, progress={self.progress:.1f}%)>"
        )
