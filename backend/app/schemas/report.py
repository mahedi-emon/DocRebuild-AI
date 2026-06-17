"""
Report Pydantic Schemas
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel


class ReportResponse(BaseModel):
    id: str
    document_id: str
    report_type: str
    overall_score: float | None = None
    data: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    reports: list[ReportResponse]
    total: int


class ReportSummary(BaseModel):
    report_type: str
    overall_score: float | None = None
    created_at: datetime
