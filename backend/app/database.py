"""
DocRebuild AI — Database Configuration

Async SQLAlchemy engine + session factory for SQLite.
Provides get_db() dependency for FastAPI route injection.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

import json
from app.utils.text_utils import make_json_serializable

def custom_json_dumps(obj, **kwargs):
    return json.dumps(make_json_serializable(obj), **kwargs)

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    connect_args={"check_same_thread": False},  # Required for SQLite
    json_serializer=custom_json_dumps,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


async def init_db() -> None:
    """Create all tables (called on app startup) and apply migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Apply column migrations for existing databases
        await conn.run_sync(_migrate_columns)
        # Clean up stale running jobs/documents from previous crashes
        await conn.run_sync(_cleanup_stale_records)


def _cleanup_stale_records(connection) -> None:
    """Reset jobs and documents that were left in running/processing state due to a crash."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        # Update jobs
        res_jobs = connection.execute(
            __import__("sqlalchemy").text(
                "UPDATE jobs SET status = 'failed', error_message = 'Job interrupted due to server restart' WHERE status = 'running'"
            )
        )
        # Update documents
        res_docs = connection.execute(
            __import__("sqlalchemy").text(
                "UPDATE documents SET status = 'failed', error_message = 'Processing interrupted due to server restart' WHERE status = 'processing'"
            )
        )
        if res_jobs.rowcount > 0 or res_docs.rowcount > 0:
            logger.info(
                f"Cleaned up stale jobs ({res_jobs.rowcount} updated) and "
                f"documents ({res_docs.rowcount} updated) on startup."
            )
    except Exception as e:
        logger.warning(f"Failed to cleanup stale records on startup: {e}")


def _migrate_columns(connection) -> None:
    """Add missing columns to existing tables (lightweight migration)."""
    import logging
    logger = logging.getLogger(__name__)

    # Check and add understanding_json column to documents table
    try:
        result = connection.execute(
            __import__("sqlalchemy").text("PRAGMA table_info(documents)")
        )
        columns = {row[1] for row in result}
        if "understanding_json" not in columns:
            connection.execute(
                __import__("sqlalchemy").text(
                    "ALTER TABLE documents ADD COLUMN understanding_json TEXT"
                )
            )
            logger.info("Migration: Added 'understanding_json' column to documents table")
    except Exception as e:
        logger.warning(f"Migration check failed (may be OK on first run): {e}")


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
