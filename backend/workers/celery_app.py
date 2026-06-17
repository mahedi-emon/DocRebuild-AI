"""
Celery Application Configuration

Configures the Celery app with Redis broker, task routing, serialization,
and retry policies for the DocRebuild AI processing pipeline.
"""

from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "docrebuild",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Result expiry
    result_expires=86400,  # 24 hours

    # Task routing — separate queues for different workload types
    task_routes={
        "workers.tasks.pdf_ingestion.*": {"queue": "general"},
        "workers.tasks.layout_analysis.*": {"queue": "gpu"},
        "workers.tasks.ocr_ensemble.*": {"queue": "gpu"},
        "workers.tasks.document_understanding.*": {"queue": "gpu"},
        "workers.tasks.vision_validation.*": {"queue": "gpu"},
        "workers.tasks.table_extraction.*": {"queue": "general"},
        "workers.tasks.math_recognition.*": {"queue": "gpu"},
        "workers.tasks.bangla_validation.*": {"queue": "general"},
        "workers.tasks.docx_reconstruction.*": {"queue": "general"},
        "workers.tasks.quality_assurance.*": {"queue": "general"},
        "workers.tasks.self_correction.*": {"queue": "general"},
        "workers.tasks.visual_verification.*": {"queue": "general"},
        "workers.tasks.orchestrator.*": {"queue": "general"},
    },

    # Default queue
    task_default_queue="general",

    # Retry policy
    task_annotations={
        "*": {
            "rate_limit": "10/m",
            "max_retries": 3,
            "default_retry_delay": 30,
        }
    },

    # Worker settings
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks (memory cleanup)
    worker_max_memory_per_child=4000000,  # 4GB max per worker (in KB)
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["workers.tasks"])
