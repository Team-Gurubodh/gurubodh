"""Configuration for semantic chunking."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


MODEL_CACHE_ENV_VAR = "GURUBODH_MODEL_CACHE_DIR"
DEFAULT_PROVIDER = "semantic-chunking"
DEFAULT_MODEL_NAME = "BAAI/bge-m3"
DEFAULT_STRATEGY_VERSION = "semantic-window-v1"
DEFAULT_EMBEDDING_MODE = "dense"
DEFAULT_EMBEDDING_DIMENSION = 1024


class SemanticChunkConfigError(ValueError):
    """Raised when semantic chunking configuration is invalid."""


class ModelCacheConfigError(RuntimeError):
    """Raised when semantic chunking cannot resolve the local model cache."""


@dataclass(frozen=True)
class SemanticChunkConfig:
    """Settings that control semantic chunking behavior."""

    provider: str = DEFAULT_PROVIDER
    model_name: str = DEFAULT_MODEL_NAME
    threshold_percentile: float = 80.0
    min_chars: int = 650
    window_size: int = 3
    batch_size: int = 16
    normalize_embeddings: bool = True
    device: str | None = None
    embedding_mode: str = DEFAULT_EMBEDDING_MODE
    embedding_dimension: int = DEFAULT_EMBEDDING_DIMENSION
    strategy_version: str = DEFAULT_STRATEGY_VERSION
    model_revision: str | None = None
    cache_dir: Path | str | None = None
    local_files_only: bool = False

    def __post_init__(self) -> None:
        self._validate()

    @classmethod
    def from_env(cls, **overrides) -> "SemanticChunkConfig":
        """Build config with the Gurubodh model cache env var as the cache path."""
        cache_dir = overrides.pop("cache_dir", None) or os.environ.get(MODEL_CACHE_ENV_VAR)
        return cls(cache_dir=cache_dir, **overrides)

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
            "embedding_mode": self.embedding_mode,
            "embedding_dimension": self.embedding_dimension,
            "strategy_version": self.strategy_version,
            "normalize_embeddings": self.normalize_embeddings,
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
            "normalize_embeddings": self.normalize_embeddings,
            "device": self.device,
        }

    def _validate(self) -> None:
        if self.provider != DEFAULT_PROVIDER:
            raise SemanticChunkConfigError(f"Unsupported semantic chunking provider: {self.provider}")
        if self.model_name != DEFAULT_MODEL_NAME:
            raise SemanticChunkConfigError(f"Unsupported semantic chunking model: {self.model_name}")
        if not 0.0 <= self.threshold_percentile <= 100.0:
            raise SemanticChunkConfigError("threshold_percentile must be between 0 and 100.")
        if self.min_chars < 0:
            raise SemanticChunkConfigError("min_chars must be zero or greater.")
        if self.window_size < 1:
            raise SemanticChunkConfigError("window_size must be one or greater.")
        if self.batch_size < 1:
            raise SemanticChunkConfigError("batch_size must be one or greater.")
        if not isinstance(self.normalize_embeddings, bool):
            raise SemanticChunkConfigError("normalize_embeddings must be true or false.")
        if self.device not in {None, "cpu", "mps", "cuda"}:
            raise SemanticChunkConfigError("device must be one of: cpu, mps, cuda.")
        if self.embedding_mode != DEFAULT_EMBEDDING_MODE:
            raise SemanticChunkConfigError("Only dense embedding mode is supported.")
        if self.embedding_dimension != DEFAULT_EMBEDDING_DIMENSION:
            raise SemanticChunkConfigError("BGE-M3 dense embedding_dimension must be 1024.")
        if self.strategy_version != DEFAULT_STRATEGY_VERSION:
            raise SemanticChunkConfigError(
                f"Unsupported semantic chunking strategy_version: {self.strategy_version}"
            )
        if not isinstance(self.local_files_only, bool):
            raise SemanticChunkConfigError("local_files_only must be true or false.")
