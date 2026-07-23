"""Core semantic chunking engine."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from gurubodh.ml.semantic_chunking.config import SemanticChunkConfig
from gurubodh.ml.semantic_chunking.models import (
    Chunk,
    ChunkedDocument,
    text_sha256,
    whitespace_insensitive_sha256,
)
from gurubodh.ml.semantic_chunking.sentence_splitter import SentenceSpan, split_sentence_spans

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class SemanticChunker:
    """Chunk text by detecting large semantic shifts between neighboring sentences."""

    def __init__(
        self,
        config: SemanticChunkConfig | None = None,
        model: "SentenceTransformer | None" = None,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config or SemanticChunkConfig()
        self._model = model
        self._progress = progress

    def chunk_text(self, text: str, source_name: str | None = None) -> ChunkedDocument:
        sentence_spans = split_sentence_spans(text)
        if not sentence_spans:
            return self._build_document(
                text=text,
                source_name=source_name,
                breakpoint_threshold=None,
                chunks=[],
            )

        if len(sentence_spans) == 1:
            chunk = self._build_chunk(index=1, sentence_spans=sentence_spans, source_text=text)
            return self._build_document(
                text=text,
                source_name=source_name,
                breakpoint_threshold=None,
                chunks=self._with_dense_embeddings([chunk]),
            )

        sentences = [span.text for span in sentence_spans]
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

        raw_chunks = self._chunks_from_breakpoints(sentence_spans, breakpoints)
        raw_chunks = self._merge_small_chunks(raw_chunks, self.config.min_chars)

        chunks = [
            self._build_chunk(
                index=index,
                sentence_spans=chunk_sentence_spans,
                source_text=text,
            )
            for index, chunk_sentence_spans in enumerate(raw_chunks, 1)
        ]
        chunks = self._with_dense_embeddings(chunks)

        return self._build_document(
            text=text,
            source_name=source_name,
            breakpoint_threshold=None if math.isinf(threshold) else threshold,
            chunks=chunks,
        )

    @property
    def model(self) -> "SentenceTransformer":
        if self._model is None:
            self._emit_progress(f"Loading embedding model {self.config.model_name}...")
            self._model = self._load_model()
            self._emit_progress("Embedding model ready.")
        return self._model

    def _emit_progress(self, message: str) -> None:
        if self._progress:
            self._progress(message)

    def _load_model(self) -> "SentenceTransformer":
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Semantic chunking requires sentence-transformers. "
                "Install the Gurubodh CLI package dependencies before running semantic chunking."
            ) from exc

        kwargs: dict[str, Any] = {
            "cache_folder": str(self.config.resolved_cache_dir()),
            "local_files_only": self.config.local_files_only,
        }
        if self.config.device:
            kwargs["device"] = self.config.device
        if self.config.model_revision:
            kwargs["revision"] = self.config.model_revision
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
        sentence_spans: list[SentenceSpan],
        breakpoints: set[int],
    ) -> list[list[SentenceSpan]]:
        chunks: list[list[SentenceSpan]] = []
        current: list[SentenceSpan] = []

        for index, sentence in enumerate(sentence_spans):
            if index in breakpoints and current:
                chunks.append(current)
                current = []
            current.append(sentence)

        if current:
            chunks.append(current)

        return chunks

    @staticmethod
    def _merge_small_chunks(
        chunks: list[list[SentenceSpan]],
        min_chars: int,
    ) -> list[list[SentenceSpan]]:
        if min_chars <= 0 or len(chunks) <= 1:
            return chunks

        merged: list[list[SentenceSpan]] = []
        pending_sentences: list[SentenceSpan] = []

        for chunk_sentences in chunks:
            pending_sentences.extend(chunk_sentences)
            if len(" ".join(sentence.text for sentence in pending_sentences)) >= min_chars:
                merged.append(pending_sentences)
                pending_sentences = []

        if pending_sentences:
            if merged:
                merged[-1] = merged[-1] + pending_sentences
            else:
                merged.append(pending_sentences)

        return merged

    def _with_dense_embeddings(self, chunks: list[Chunk]) -> list[Chunk]:
        if not chunks:
            return chunks
        embeddings = self.model.encode(
            [chunk.text for chunk in chunks],
            batch_size=self.config.batch_size,
            normalize_embeddings=self.config.normalize_embeddings,
            show_progress_bar=False,
        )
        if len(embeddings) != len(chunks):
            raise RuntimeError("Embedding model returned a different number of vectors than requested chunks.")
        return [
            replace(chunk, dense_embedding=self._embedding_to_list(embedding))
            for chunk, embedding in zip(chunks, embeddings)
        ]

    @staticmethod
    def _embedding_to_list(embedding: Any) -> list[float]:
        if hasattr(embedding, "tolist"):
            embedding = embedding.tolist()
        return [float(value) for value in embedding]

    def _build_chunk(self, index: int, sentence_spans: list[SentenceSpan], source_text: str) -> Chunk:
        start_char = sentence_spans[0].start_char
        end_char = sentence_spans[-1].end_char
        text = source_text[start_char:end_char]
        return Chunk(
            index=index,
            text=text,
            sentence_count=len(sentence_spans),
            char_count=len(text),
            estimated_embedding_token_count=self._count_embedding_tokens(text),
            start_sentence=sentence_spans[0].source_index,
            end_sentence=sentence_spans[-1].source_index,
            start_char=start_char,
            end_char=end_char,
            chunk_text_sha256=text_sha256(text),
        )

    def _count_embedding_tokens(self, text: str) -> int:
        tokenizer = self._embedding_tokenizer()
        try:
            token_ids = tokenizer.encode(text, add_special_tokens=False)
        except TypeError:
            token_ids = tokenizer.encode(text)
        return len(token_ids)

    def _embedding_tokenizer(self) -> Any:
        tokenizer = getattr(self.model, "tokenizer", None)
        if tokenizer is None:
            raise RuntimeError(
                "Semantic chunking requires the embedding model to expose a tokenizer "
                "for estimated_embedding_token_count."
            )
        return tokenizer

    def _build_document(
        self,
        text: str,
        source_name: str | None,
        breakpoint_threshold: float | None,
        chunks: list[Chunk],
    ) -> ChunkedDocument:
        concatenated = "".join(chunk.text for chunk in sorted(chunks, key=lambda chunk: chunk.index))
        return ChunkedDocument(
            source_name=source_name,
            provider=self.config.provider,
            model_name=self.config.model_name,
            embedding_mode=self.config.embedding_mode,
            embedding_dimension=self.config.embedding_dimension,
            strategy_version=self.config.strategy_version,
            threshold_percentile=self.config.threshold_percentile,
            min_chars=self.config.min_chars,
            window_size=self.config.window_size,
            batch_size=self.config.batch_size,
            normalize_embeddings=self.config.normalize_embeddings,
            device=self.config.device,
            breakpoint_threshold=breakpoint_threshold,
            chunks=chunks,
            source_text_sha256=whitespace_insensitive_sha256(text),
            concatenated_chunks_sha256=whitespace_insensitive_sha256(concatenated),
        )
