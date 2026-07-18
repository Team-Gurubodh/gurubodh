"""Data models returned by the semantic chunker."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Chunk:
    """One semantically coherent chunk of source text."""

    index: int
    text: str
    sentence_count: int
    char_count: int
    start_sentence: int
    end_sentence: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ChunkedDocument:
    """A document after semantic chunking."""

    source_name: str | None
    model_name: str
    threshold_percentile: float
    breakpoint_threshold: float | None
    chunks: list[Chunk]

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    def to_dict(self) -> dict:
        return {
            "source_name": self.source_name,
            "model": self.model_name,
            "threshold_percentile": self.threshold_percentile,
            "breakpoint_threshold": self.breakpoint_threshold,
            "chunk_count": self.chunk_count,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
        }
