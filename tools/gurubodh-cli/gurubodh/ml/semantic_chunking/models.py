"""Data models returned by the semantic chunker."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib


@dataclass(frozen=True)
class Chunk:
    """One semantically coherent chunk of source text."""

    index: int
    text: str
    sentence_count: int
    char_count: int
    start_sentence: int
    end_sentence: int
    start_char: int
    end_char: int
    chunk_text_sha256: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ChunkedDocument:
    """A document after semantic chunking."""

    source_name: str | None
    provider: str
    model_name: str
    embedding_mode: str
    embedding_dimension: int
    strategy_version: str
    threshold_percentile: float
    min_chars: int
    window_size: int
    batch_size: int
    normalize_embeddings: bool
    device: str | None
    breakpoint_threshold: float | None
    chunks: list[Chunk]
    source_text_sha256: str | None = None
    concatenated_chunks_sha256: str | None = None
    index_unit: str = "python-codepoint"
    span_semantics: str = "zero-based-end-exclusive"
    warning: str | None = None

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    def to_dict(self) -> dict:
        return {
            "source_name": self.source_name,
            "provider": self.provider,
            "model": self.model_name,
            "embedding_mode": self.embedding_mode,
            "embedding_dimension": self.embedding_dimension,
            "strategy_version": self.strategy_version,
            "index_unit": self.index_unit,
            "span_semantics": self.span_semantics,
            "threshold_percentile": self.threshold_percentile,
            "parameters": {
                "threshold_percentile": self.threshold_percentile,
                "min_chars": self.min_chars,
                "window_size": self.window_size,
                "batch_size": self.batch_size,
                "normalize_embeddings": self.normalize_embeddings,
                "device": self.device,
            },
            "source_text_sha256": self.source_text_sha256,
            "concatenated_chunks_sha256": self.concatenated_chunks_sha256,
            "chunk_count": self.chunk_count,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "diagnostics": {
                "breakpoint_threshold": self.breakpoint_threshold,
                "warning": self.warning,
            },
        }


def text_sha256(text: str) -> str:
    """Return SHA-256 for UTF-8 encoded text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def whitespace_insensitive_sha256(text: str) -> str:
    """Return SHA-256 after removing Python-recognized Unicode whitespace."""
    return text_sha256("".join(char for char in text if not char.isspace()))
