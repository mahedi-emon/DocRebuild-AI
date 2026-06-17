"""
API Router — Aggregates all sub-routers into a single router.
"""

from fastapi import APIRouter

from app.api.documents import router as documents_router
from app.api.jobs import router as jobs_router
from app.api.pages import router as pages_router
from app.api.reports import router as reports_router
from app.api.health import router as health_router

api_router = APIRouter(prefix="/api")

api_router.include_router(health_router, prefix="/health", tags=["Health"])
api_router.include_router(documents_router, prefix="/documents", tags=["Documents"])
api_router.include_router(jobs_router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(pages_router, prefix="/pages", tags=["Pages"])
api_router.include_router(reports_router, prefix="/reports", tags=["Reports"])
