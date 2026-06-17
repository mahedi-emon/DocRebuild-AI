"""
DocRebuild AI — FastAPI Application Entry Point

Mounts all routers, middleware, WebSocket endpoints, and handles
application lifecycle (startup/shutdown).
"""

from __future__ import annotations

import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.api.router import api_router
from app.api.websocket import router as ws_router

settings = get_settings()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    # ── Startup ──
    logger.info("Starting DocRebuild AI", env=settings.app_env.value)
    settings.ensure_directories()
    await init_db()
    logger.info("Database initialized")
    logger.info("Processing mode: Direct in-process (no Redis/Celery required)")

    yield

    # ── Shutdown ──
    logger.info("Shutting down DocRebuild AI")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Production-grade Document Reconstruction Platform. "
            "Converts scanned PDFs and images into editable DOCX files with "
            "multi-OCR ensemble, layout analysis, and vision model validation."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS Middleware ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restricted in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Mount Routers ──
    app.include_router(api_router)
    app.include_router(ws_router)

    # ── Static file serving for uploaded/output files ──
    # These are created by ensure_directories() at startup
    try:
        app.mount(
            "/static/uploads",
            StaticFiles(directory=str(settings.upload_dir)),
            name="uploads",
        )
        app.mount(
            "/static/outputs",
            StaticFiles(directory=str(settings.output_dir)),
            name="outputs",
        )
    except Exception:
        pass  # Directories may not exist on first run before lifespan

    @app.get("/", tags=["Root"])
    async def root():
        return {
            "name": settings.app_name,
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=settings.workers,
    )
