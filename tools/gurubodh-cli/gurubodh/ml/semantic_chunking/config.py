"""Configuration for semantic chunking."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from gurubodh.ml.errors import ModelCacheConfigError

MODEL_CACHE_ENV_VAR = "GURUBODH_MODEL_CACHE_DIR"
SUPPORTED_PROVIDER = "semantic-chunking"
SUPPORTED_MODEL_NAME = "BAAI/bge-m3"
SUPPORTED_STRATEGY_VERSION = "semantic-window-v1"


class SemanticChunkConfigError(ValueError):
    """Raised when semantic chunking configuration is invalid."""


@dataclass(frozen=True)
class SemanticChunkConfig:
    """Settings that control semantic chunking behavior."""

    provider: str
    model_name: str
    threshold_percentile: float
    min_chars: int
    window_size: int
    batch_size: int
    normalize_contextual_vectors: bool
    device: str | None
    strategy_version: str
    model_revision: str | None
    local_files_only: bool
    cache_dir: Path | str | None = None

    def __post_init__(self) -> None:
        self._validate()

    @classmethod
    def from_env(cls, **settings) -> "SemanticChunkConfig":
        """Build config with the Gurubodh model cache env var as the cache path."""
        cache_dir = settings.pop("cache_dir", None) or os.environ.get(MODEL_CACHE_ENV_VAR)
        return cls(cache_dir=cache_dir, **settings)

    def resolved_cache_dir(self) -> Path:
        """Return the required local model cache directory."""
        cache_dir = self.cache_dir or os.environ.get(MODEL_CACHE_ENV_VAR)
        if not cache_dir:
            raise ModelCacheConfigError(
                f"{MODEL_CACHE_ENV_VAR} must be set before running semantic chunking. "
                "Set it to the local Hugging Face model cache directory."
            )
        return Path(cache_dir).expanduser().resolve()

    def provider_metadata(self) -> dict:
        """Return provider/model metadata that must travel with generated chunks."""
        return {
            "provider": self.provider,
            "model": self.model_name,
            "model_revision": self.model_revision,
            "strategy_version": self.strategy_version,
            "normalize_contextual_vectors": self.normalize_contextual_vectors,
            "batch_size": self.batch_size,
            "device": self.device,
        }

    def parameters_metadata(self) -> dict:
        """Return output-affecting chunking parameters."""
        return {
            "threshold_percentile": self.threshold_percentile,
            "min_chars": self.min_chars,
            "window_size": self.window_size,
            "batch_size": self.batch_size,
            "normalize_contextual_vectors": self.normalize_contextual_vectors,
            "device": self.device,
        }

    def _validate(self) -> None:
        if self.provider != SUPPORTED_PROVIDER:
            raise SemanticChunkConfigError(f"Unsupported semantic chunking provider: {self.provider}")
        if self.model_name != SUPPORTED_MODEL_NAME:
            raise SemanticChunkConfigError(f"Unsupported semantic chunking model: {self.model_name}")
        if not 0.0 <= self.threshold_percentile <= 100.0:
            raise SemanticChunkConfigError("threshold_percentile must be between 0 and 100.")
        if self.min_chars < 0:
            raise SemanticChunkConfigError("min_chars must be zero or greater.")
        if self.window_size < 1:
            raise SemanticChunkConfigError("window_size must be one or greater.")
        if self.batch_size < 1:
            raise SemanticChunkConfigError("batch_size must be one or greater.")
        if not isinstance(self.normalize_contextual_vectors, bool):
            raise SemanticChunkConfigError("normalize_contextual_vectors must be true or false.")
        if self.device not in {None, "cpu", "mps", "cuda"}:
            raise SemanticChunkConfigError("device must be one of: cpu, mps, cuda.")
        if self.strategy_version != SUPPORTED_STRATEGY_VERSION:
            raise SemanticChunkConfigError(
                f"Unsupported semantic chunking strategy_version: {self.strategy_version}"
            )
        if not isinstance(self.local_files_only, bool):
            raise SemanticChunkConfigError("local_files_only must be true or false.")
