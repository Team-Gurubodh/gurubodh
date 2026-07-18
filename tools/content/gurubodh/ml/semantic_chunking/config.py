"""Configuration for semantic chunking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SemanticChunkConfig:
    """Settings that control semantic chunking behavior."""

    model_name: str = "BAAI/bge-m3"
    threshold_percentile: float = 82.0
    min_chars: int = 700
    window_size: int = 3
    batch_size: int = 16
    normalize_embeddings: bool = True
    device: str | None = None
