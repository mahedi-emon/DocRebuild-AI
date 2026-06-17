"""
Page ORM Model

Represents a single page within a document, tracking its image,
layout analysis results, OCR results, and confidence scores.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dpi: Mapped[int] = mapped_column(Integer, default=300)

    # Layout analysis results (JSON blob)
    layout_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # OCR results (JSON blob with per-word data)
    ocr_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Document understanding results
    understanding_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Table extraction results
    tables_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Equation extraction results
    equations_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Confidence and quality scores
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    layout_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ssim_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Processing metadata
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="pages")

    def __repr__(self) -> str:
        return (
            f"<Page(id={self.id!r}, doc={self.document_id!r}, "
            f"page={self.page_number}, confidence={self.overall_confidence})>"
        )
