"""
DocRebuild AI — Application Configuration

Loads settings from environment variables / .env file using pydantic-settings.
All configuration knobs for engines, paths, limits, and feature toggles.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DeviceType(str, Enum):
    AUTO = "auto"
    CPU = "cpu"
    CUDA = "cuda"


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Main application settings loaded from .env"""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────
    app_name: str = "DocRebuild AI"
    app_env: Environment = Environment.DEVELOPMENT
    debug: bool = True
    log_level: str = "INFO"

    # ── Server ───────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1

    # ── Database ─────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./data/docrebuild.db"

    # ── Redis ────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── File Storage ─────────────────────────────────────────
    upload_dir: Path = Path("./data/uploads")
    output_dir: Path = Path("./data/outputs")
    temp_dir: Path = Path("./data/temp")
    max_file_size_mb: int = 500
    allowed_extensions: str = ".pdf,.png,.jpg,.jpeg,.tiff,.bmp"

    # ── Models ───────────────────────────────────────────────
    model_cache_dir: Path = Path("./data/models")
    gpu_memory_limit_mb: int = 8000
    device: str = "auto"

    # ── OCR Engine Toggles ───────────────────────────────────
    enable_surya: bool = True
    enable_paddleocr: bool = True
    enable_tesseract: bool = True
    enable_easyocr: bool = True
    enable_trocr: bool = True
    enable_doctr: bool = True

    # ── Layout Engine Toggles ────────────────────────────────
    enable_doclayout_yolo: bool = True
    enable_layout_parser: bool = True
    enable_detectron2: bool = True

    # ── Understanding Engine Toggles ─────────────────────────
    enable_docling: bool = True
    enable_marker: bool = True
    enable_nougat: bool = True

    # ── Vision Model Toggles ────────────────────────────────
    enable_florence2: bool = True
    enable_qwen_vl: bool = False
    enable_internvl: bool = False

    # ── Table Extraction Toggles ─────────────────────────────
    enable_table_transformer: bool = True
    enable_camelot: bool = True
    enable_tabula: bool = True

    # ── Math Recognition Toggles ─────────────────────────────
    enable_pix2tex: bool = True
    enable_latex_ocr: bool = True

    # ── Language Validation ──────────────────────────────────
    enable_bangla_validation: bool = True
    bangla_dictionary_path: Path = Path("./data/bangla_dictionary.txt")

    # ── Processing Defaults ──────────────────────────────────
    default_dpi: int = 300
    ocr_confidence_threshold: float = 0.7
    vision_validation_threshold: float = 0.6
    max_repair_passes: int = 3
    ensemble_min_engines: int = 3

    # ── Celery ───────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def compute_device(self) -> str:
        """Resolve the compute device (auto-detect GPU availability)."""
        if self.device == "auto":
            try:
                import torch
                return "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                return "cpu"
        return self.device

    def ensure_directories(self) -> None:
        """Create all required data directories."""
        for d in [self.upload_dir, self.output_dir, self.temp_dir, self.model_cache_dir]:
            d.mkdir(parents=True, exist_ok=True)

    @field_validator("upload_dir", "output_dir", "temp_dir", "model_cache_dir", mode="before")
    @classmethod
    def resolve_path(cls, v: str | Path) -> Path:
        return Path(v).resolve() if not Path(v).is_absolute() else Path(v)


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance (cached)."""
    settings = Settings()
    settings.ensure_directories()
    return settings
