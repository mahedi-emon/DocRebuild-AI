"""
Report ORM Model

Stores QA reports, error reports, and confidence reports for processed documents.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReportType(str, enum.Enum):
    QA = "qa"
    ERROR = "error"
    CONFIDENCE = "confidence"
    PAGE_STRUCTURE = "page_structure"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    report_type: Mapped[str] = mapped_column(String(30), nullable=False)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Report data as JSON (schema varies by report_type)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="reports")

    def __repr__(self) -> str:
        return (
            f"<Report(id={self.id!r}, type={self.report_type!r}, "
            f"score={self.overall_score})>"
        )
