"""
Documents API — Upload, list, retrieve, and download documents.
"""

from __future__ import annotations

import os
import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.document import Document
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentResponse,
    DocumentListResponse,
)
from app.utils.pdf_utils import get_pdf_page_count

router = APIRouter()
settings = get_settings()


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF or image document for processing."""
    # Validate file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed: {settings.allowed_extensions_list}",
        )

    # Read file to check size
    content = await file.read()
    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum of {settings.max_file_size_mb}MB",
        )

    # Generate unique filename
    doc_id = str(uuid.uuid4())
    safe_filename = f"{doc_id}{ext}"
    doc_dir = settings.upload_dir / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    file_path = doc_dir / safe_filename

    # Save file
    with open(file_path, "wb") as f:
        f.write(content)

    # Get page count for PDFs
    page_count = 0
    if ext == ".pdf":
        page_count = get_pdf_page_count(str(file_path))
    else:
        page_count = 1  # Single image

    # Create DB record
    document = Document(
        id=doc_id,
        filename=safe_filename,
        original_filename=file.filename,
        file_path=str(file_path),
        file_size=len(content),
        file_type=ext.lstrip("."),
        page_count=page_count,
        status="uploaded",
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)

    return document


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all documents with optional status filter and pagination."""
    query = select(Document).order_by(Document.created_at.desc())
    count_query = select(func.count(Document.id))

    if status:
        query = query.where(Document.status == status)
        count_query = count_query.where(Document.status == status)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    documents = result.scalars().all()

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get document details by ID."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Download the generated DOCX file for a document."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.status != "completed" or not document.output_path:
        raise HTTPException(
            status_code=400,
            detail="Document has not been processed yet or processing failed",
        )

    output_path = Path(document.output_path)
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found on disk")

    # Generate a friendly download name
    original_stem = Path(document.original_filename).stem
    download_name = f"{original_stem}_reconstructed.docx"

    return FileResponse(
        path=str(output_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=download_name,
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and all its associated data."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove files from disk
    doc_upload_dir = settings.upload_dir / document_id
    if doc_upload_dir.exists():
        shutil.rmtree(doc_upload_dir)

    doc_output_dir = settings.output_dir / document_id
    if doc_output_dir.exists():
        shutil.rmtree(doc_output_dir)

    await db.delete(document)
