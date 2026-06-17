"""
Health Check API — Lightweight endpoint for system status.
"""

from __future__ import annotations

import platform
from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("")
async def health_check():
    """Lightweight system health check — no heavy imports."""
    health = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "environment": settings.app_env.value,
        "platform": platform.system(),
        "python": platform.python_version(),
        "processing_mode": "direct_in_process",
        "device": settings.device,
    }

    # Check enabled engines (just reads config, no imports)
    health["engines"] = {
        "ocr": {
            "paddleocr": settings.enable_paddleocr,
            "easyocr": settings.enable_easyocr,
            "doctr": settings.enable_doctr,
            "surya": settings.enable_surya,
            "tesseract": settings.enable_tesseract,
            "trocr": settings.enable_trocr,
        },
        "layout": {
            "doclayout_yolo": settings.enable_doclayout_yolo,
        },
    }

    return health
