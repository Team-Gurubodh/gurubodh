"""Provider boundary for paragraph segmentation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from gurubodh.ml.semantic_chunking.chunker import SemanticChunker
from gurubodh.ml.semantic_chunking.config import SemanticChunkConfig
from gurubodh.ml.semantic_chunking.models import ChunkedDocument


ParagraphSegmentation = ChunkedDocument


class ParagraphSegmenter(Protocol):
    """Boundary used by commands and future pipelines that need paragraphs."""

    @property
    def provider_metadata(self) -> dict:
        """Return provider/model identity and embedding settings."""

    def segment(self, text: str, source_name: str | None = None) -> ParagraphSegmentation:
        """Segment source text into paragraph-like semantic chunks."""


@dataclass
class SemanticChunkingParagraphSegmenter:
    """Paragraph segmenter backed by the local semantic chunker."""

    config: SemanticChunkConfig
    chunker: SemanticChunker | None = None
    progress: Callable[[str], None] | None = None

    @property
    def provider_metadata(self) -> dict:
        return self.config.provider_metadata()

    def segment(self, text: str, source_name: str | None = None) -> ParagraphSegmentation:
        chunker = self.chunker or SemanticChunker(self.config, progress=self.progress)
        self.chunker = chunker
        return chunker.chunk_text(text, source_name=source_name)
