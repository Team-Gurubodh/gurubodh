"""Core semantic chunking engine."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from gurubodh.ml.semantic_chunking.config import SemanticChunkConfig
from gurubodh.ml.semantic_chunking.models import Chunk, ChunkedDocument
from gurubodh.ml.semantic_chunking.sentence_splitter import split_sentences

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class SemanticChunker:
    """Chunk text by detecting large semantic shifts between neighboring sentences."""

    def __init__(
        self,
        config: SemanticChunkConfig | None = None,
        model: "SentenceTransformer | None" = None,
    ) -> None:
        self.config = config or SemanticChunkConfig()
        self.model = model or self._load_model()

    def chunk_text(self, text: str, source_name: str | None = None) -> ChunkedDocument:
        sentences = split_sentences(text)
        if not sentences:
            return ChunkedDocument(
                source_name=source_name,
                model_name=self.config.model_name,
                threshold_percentile=self.config.threshold_percentile,
                breakpoint_threshold=None,
                chunks=[],
            )

        if len(sentences) == 1:
            chunk = self._build_chunk(index=1, sentences=sentences, start_sentence=0)
            return ChunkedDocument(
                source_name=source_name,
                model_name=self.config.model_name,
                threshold_percentile=self.config.threshold_percentile,
                breakpoint_threshold=None,
                chunks=[chunk],
            )

        windows = self._contextual_windows(sentences)
        embeddings = self.model.encode(
            windows,
            batch_size=self.config.batch_size,
            normalize_embeddings=self.config.normalize_embeddings,
            show_progress_bar=False,
        )
        distances = self._cosine_distances(embeddings)
        threshold = self._percentile(distances, self.config.threshold_percentile)
        breakpoints = self._initial_breakpoints(distances, threshold)

        raw_chunks = self._chunks_from_breakpoints(sentences, breakpoints)
        raw_chunks = self._merge_small_chunks(raw_chunks, self.config.min_chars)

        chunks = [
            self._build_chunk(
                index=index,
                sentences=chunk_sentences,
                start_sentence=start_sentence,
            )
            for index, (start_sentence, chunk_sentences) in enumerate(raw_chunks, 1)
        ]

        return ChunkedDocument(
            source_name=source_name,
            model_name=self.config.model_name,
            threshold_percentile=self.config.threshold_percentile,
            breakpoint_threshold=None if math.isinf(threshold) else threshold,
            chunks=chunks,
        )

    def _load_model(self) -> "SentenceTransformer":
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Semantic chunking requires sentence-transformers. "
                "Install the Gurubodh CLI package dependencies before creating a SemanticChunker."
            ) from exc

        kwargs = {}
        if self.config.device:
            kwargs["device"] = self.config.device
        return SentenceTransformer(self.config.model_name, **kwargs)

    def _contextual_windows(self, sentences: list[str]) -> list[str]:
        radius = max(0, self.config.window_size // 2)
        windows = []
        for index in range(len(sentences)):
            start = max(0, index - radius)
            end = min(len(sentences), index + radius + 1)
            windows.append(" ".join(sentences[start:end]))
        return windows

    @staticmethod
    def _cosine_distances(embeddings: Any) -> list[float]:
        import numpy as np

        embeddings = np.asarray(embeddings)
        if len(embeddings) < 2:
            return []

        distances: list[float] = []
        for left, right in zip(embeddings[:-1], embeddings[1:]):
            denom = np.linalg.norm(left) * np.linalg.norm(right)
            similarity = float(np.dot(left, right) / denom) if denom else 0.0
            distances.append(1.0 - similarity)
        return distances

    @staticmethod
    def _percentile(values: list[float], amount: float) -> float:
        import numpy as np

        if not values:
            return math.inf
        return float(np.percentile(np.array(values), amount))

    @staticmethod
    def _initial_breakpoints(distances: list[float], threshold: float) -> set[int]:
        return {index + 1 for index, distance in enumerate(distances) if distance >= threshold}

    @staticmethod
    def _chunks_from_breakpoints(
        sentences: list[str],
        breakpoints: set[int],
    ) -> list[tuple[int, list[str]]]:
        chunks: list[tuple[int, list[str]]] = []
        current: list[str] = []
        current_start = 0

        for index, sentence in enumerate(sentences):
            if index in breakpoints and current:
                chunks.append((current_start, current))
                current = []
                current_start = index
            current.append(sentence)

        if current:
            chunks.append((current_start, current))

        return chunks

    @staticmethod
    def _merge_small_chunks(
        chunks: list[tuple[int, list[str]]],
        min_chars: int,
    ) -> list[tuple[int, list[str]]]:
        if min_chars <= 0 or len(chunks) <= 1:
            return chunks

        merged: list[tuple[int, list[str]]] = []
        pending_sentences: list[str] = []
        pending_start: int | None = None

        for start, chunk_sentences in chunks:
            if pending_start is None:
                pending_start = start
            pending_sentences.extend(chunk_sentences)
            if len(" ".join(pending_sentences)) >= min_chars:
                merged.append((pending_start, pending_sentences))
                pending_sentences = []
                pending_start = None

        if pending_sentences:
            if merged:
                previous_start, previous_sentences = merged[-1]
                merged[-1] = (previous_start, previous_sentences + pending_sentences)
            else:
                merged.append((pending_start or 0, pending_sentences))

        return merged

    @staticmethod
    def _build_chunk(index: int, sentences: list[str], start_sentence: int) -> Chunk:
        text = " ".join(sentences).strip()
        return Chunk(
            index=index,
            text=text,
            sentence_count=len(sentences),
            char_count=len(text),
            start_sentence=start_sentence,
            end_sentence=start_sentence + len(sentences) - 1,
        )
