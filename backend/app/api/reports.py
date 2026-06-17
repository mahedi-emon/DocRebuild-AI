"""
Reports API — Retrieve QA, Error, Confidence, and Page Structure reports.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.report import Report
from app.schemas.report import ReportResponse, ReportListResponse

router = APIRouter()


@router.get("/{document_id}", response_model=ReportListResponse)
async def list_reports(
    document_id: str,
    report_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all reports for a document, optionally filtered by type."""
    query = (
        select(Report)
        .where(Report.document_id == document_id)
        .order_by(Report.created_at.desc())
    )
    if report_type:
        query = query.where(Report.report_type == report_type)

    result = await db.execute(query)
    reports = result.scalars().all()
    return ReportListResponse(
        reports=[ReportResponse.model_validate(r) for r in reports],
        total=len(reports),
    )


@router.get("/detail/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific report by ID."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
