"""Lightweight semantic-chunking records and lazy compatibility exports.

Internal callers should import the narrow component they consume. Importing
configuration or models must not initialize the chunking implementation.
"""

from typing import Any

from gurubodh.ml.semantic_chunking.config import SemanticChunkConfig
from gurubodh.ml.semantic_chunking.models import Chunk, ChunkedDocument

__all__ = [
    "Chunk",
    "ChunkedDocument",
    "ParagraphSegmenter",
    "SemanticChunkConfig",
    "SemanticChunker",
    "SemanticChunkingParagraphSegmenter",
]


def __getattr__(name: str) -> Any:
    """Load implementation classes only for explicit compatibility imports."""
    if name == "SemanticChunker":
        from gurubodh.ml.semantic_chunking.chunker import SemanticChunker

        return SemanticChunker
    if name in {"ParagraphSegmenter", "SemanticChunkingParagraphSegmenter"}:
        from gurubodh.ml.semantic_chunking.segmenter import (
            ParagraphSegmenter,
            SemanticChunkingParagraphSegmenter,
        )

        return {
            "ParagraphSegmenter": ParagraphSegmenter,
            "SemanticChunkingParagraphSegmenter": SemanticChunkingParagraphSegmenter,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
