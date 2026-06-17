"""
Page Pydantic Schemas
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel


class PageResponse(BaseModel):
    id: str
    document_id: str
    page_number: int
    image_path: str | None = None
    width: int | None = None
    height: int | None = None
    dpi: int
    ocr_confidence: float | None = None
    layout_confidence: float | None = None
    overall_confidence: float | None = None
    ssim_score: float | None = None
    processing_time_ms: int | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PageDetailResponse(PageResponse):
    layout_json: dict | None = None
    ocr_json: dict | None = None
    understanding_json: dict | None = None
    tables_json: list | None = None
    equations_json: list | None = None


class PageListResponse(BaseModel):
    pages: list[PageResponse]
    total: int
