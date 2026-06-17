"""
Pages API — Retrieve per-page data (layout, OCR, tables, equations).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.page import Page
from app.schemas.page import PageResponse, PageDetailResponse, PageListResponse

router = APIRouter()


@router.get("/{document_id}", response_model=PageListResponse)
async def list_pages(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all pages for a document."""
    result = await db.execute(
        select(Page)
        .where(Page.document_id == document_id)
        .order_by(Page.page_number)
    )
    pages = result.scalars().all()
    return PageListResponse(
        pages=[PageResponse.model_validate(p) for p in pages],
        total=len(pages),
    )


@router.get("/{document_id}/{page_number}", response_model=PageDetailResponse)
async def get_page_detail(
    document_id: str,
    page_number: int,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed data for a specific page including layout, OCR, tables, equations."""
    result = await db.execute(
        select(Page).where(
            Page.document_id == document_id,
            Page.page_number == page_number,
        )
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.get("/{document_id}/{page_number}/image")
async def get_page_image(
    document_id: str,
    page_number: int,
    db: AsyncSession = Depends(get_db),
):
    """Serve the rendered page image."""
    from fastapi.responses import FileResponse
    from pathlib import Path

    result = await db.execute(
        select(Page).where(
            Page.document_id == document_id,
            Page.page_number == page_number,
        )
    )
    page = result.scalar_one_or_none()
    if not page or not page.image_path:
        raise HTTPException(status_code=404, detail="Page image not found")

    image_path = Path(page.image_path)
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Page image file not found on disk")

    return FileResponse(str(image_path), media_type="image/png")
