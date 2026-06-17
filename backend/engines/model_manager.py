"""
Model Manager — GPU memory management for AI models.

Tracks loaded models, their VRAM usage, and implements LRU eviction
when memory thresholds are reached. Thread-safe with locking.
"""

from __future__ import annotations

import gc
import time
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Metadata about a loaded model."""
    name: str
    category: str  # ocr, layout, vision, table, math
    estimated_vram_mb: float
    loaded_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    instance: object = None

    def touch(self):
        """Update last_used timestamp."""
        self.last_used = time.time()


class ModelManager:
    """
    Manages GPU memory by tracking loaded models and evicting
    least-recently-used models when memory is constrained.
    """

    def __init__(self, max_vram_mb: float = 8000):
        self._max_vram_mb = max_vram_mb
        self._models: OrderedDict[str, ModelInfo] = OrderedDict()
        self._lock = threading.RLock()
        self._current_vram_usage = 0.0

    @property
    def loaded_models(self) -> list[str]:
        with self._lock:
            return list(self._models.keys())

    @property
    def vram_usage_mb(self) -> float:
        with self._lock:
            return self._current_vram_usage

    @property
    def vram_available_mb(self) -> float:
        return max(0, self._max_vram_mb - self._current_vram_usage)

    def is_loaded(self, model_name: str) -> bool:
        with self._lock:
            return model_name in self._models

    def register(
        self,
        model_name: str,
        category: str,
        estimated_vram_mb: float,
        instance: object = None,
    ) -> bool:
        """
        Register a model as loaded. Evicts LRU models if necessary.

        Returns:
            True if the model was registered (enough memory), False otherwise.
        """
        with self._lock:
            # Already loaded
            if model_name in self._models:
                self._models[model_name].touch()
                self._models.move_to_end(model_name)
                return True

            # Check if we need to evict
            while (
                self._current_vram_usage + estimated_vram_mb > self._max_vram_mb
                and self._models
            ):
                evicted_name, evicted_info = self._models.popitem(last=False)
                self._current_vram_usage -= evicted_info.estimated_vram_mb
                logger.info(
                    f"Evicted model '{evicted_name}' "
                    f"(freed ~{evicted_info.estimated_vram_mb:.0f}MB)"
                )
                # Cleanup the evicted model
                if evicted_info.instance is not None:
                    if hasattr(evicted_info.instance, "cleanup"):
                        evicted_info.instance.cleanup()
                    del evicted_info.instance

                gc.collect()
                self._try_clear_gpu_cache()

            # Check if there's now enough room
            if self._current_vram_usage + estimated_vram_mb > self._max_vram_mb:
                logger.warning(
                    f"Cannot load '{model_name}': requires {estimated_vram_mb}MB, "
                    f"available {self.vram_available_mb:.0f}MB"
                )
                return False

            # Register
            self._models[model_name] = ModelInfo(
                name=model_name,
                category=category,
                estimated_vram_mb=estimated_vram_mb,
                instance=instance,
            )
            self._current_vram_usage += estimated_vram_mb
            logger.info(
                f"Registered model '{model_name}' "
                f"(~{estimated_vram_mb:.0f}MB, total: {self._current_vram_usage:.0f}MB)"
            )
            return True

    def get(self, model_name: str) -> object | None:
        """Get a loaded model instance and update its LRU timestamp."""
        with self._lock:
            if model_name in self._models:
                self._models[model_name].touch()
                self._models.move_to_end(model_name)
                return self._models[model_name].instance
            return None

    def unload(self, model_name: str) -> bool:
        """Explicitly unload a model."""
        with self._lock:
            if model_name not in self._models:
                return False

            info = self._models.pop(model_name)
            self._current_vram_usage -= info.estimated_vram_mb

            if info.instance is not None:
                if hasattr(info.instance, "cleanup"):
                    info.instance.cleanup()
                del info.instance

            gc.collect()
            self._try_clear_gpu_cache()
            logger.info(f"Unloaded model '{model_name}'")
            return True

    def unload_category(self, category: str) -> int:
        """Unload all models in a category. Returns count of unloaded models."""
        with self._lock:
            to_unload = [
                name for name, info in self._models.items()
                if info.category == category
            ]

        count = 0
        for name in to_unload:
            if self.unload(name):
                count += 1
        return count

    def unload_all(self) -> None:
        """Unload all models."""
        with self._lock:
            names = list(self._models.keys())
        for name in names:
            self.unload(name)

    def status(self) -> dict:
        """Get current model manager status."""
        with self._lock:
            return {
                "max_vram_mb": self._max_vram_mb,
                "used_vram_mb": self._current_vram_usage,
                "available_vram_mb": self.vram_available_mb,
                "loaded_models": [
                    {
                        "name": info.name,
                        "category": info.category,
                        "vram_mb": info.estimated_vram_mb,
                        "loaded_at": info.loaded_at,
                        "last_used": info.last_used,
                    }
                    for info in self._models.values()
                ],
            }

    def _try_clear_gpu_cache(self) -> None:
        """Attempt to clear GPU cache if PyTorch is available."""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass


# Global singleton
_model_manager: ModelManager | None = None


def get_model_manager() -> ModelManager:
    """Get the global model manager instance."""
    global _model_manager
    if _model_manager is None:
        from app.config import get_settings
        settings = get_settings()
        _model_manager = ModelManager(max_vram_mb=settings.gpu_memory_limit_mb)
    return _model_manager
