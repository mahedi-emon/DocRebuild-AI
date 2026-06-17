"""
Document Pydantic Schemas

Request/Response models for document-related API endpoints.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    file_size: int
    file_type: str
    page_count: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    file_type: str
    page_count: int
    status: str
    output_path: str | None = None
    overall_confidence: float | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentStatusUpdate(BaseModel):
    status: str
    error_message: str | None = None
