"""Internal, provider-neutral text-embedding helpers.

The preparation pipeline uses this boundary only for temporary contextual
similarity vectors while it finds semantic breakpoints.  Future CMS snapshot
embedding work can reuse the same batch-loading and provenance behaviour
without coupling vectors to the semantic chunk artifact domain.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from gurubodh.ml.semantic_chunking.config import ModelCacheConfigError

class TextEmbeddingHelper(Protocol):
    """A reusable batch text-encoding boundary."""

    @property
    def metadata(self) -> dict[str, object]:
        """Return pinned provider and model provenance."""

    @property
    def tokenizer(self) -> Any:
        """Return the model tokenizer used for local token estimates."""

    def encode_texts(self, texts: Sequence[str], *, batch_size: int, normalize: bool) -> Any:
        """Encode a batch of texts without assigning ownership to callers."""


@dataclass
class SentenceTransformerEmbeddingHelper:
    """Lazy SentenceTransformers implementation of :class:`TextEmbeddingHelper`."""

    provider: str
    model_name: str
    model_revision: str | None
    cache_dir_resolver: Callable[[], object]
    local_files_only: bool
    device: str | None
    model: Any | None = None
    progress: Callable[[str], None] | None = None

    @property
    def metadata(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model_name,
            "model_revision": self.model_revision,
            "local_files_only": self.local_files_only,
            "device": self.device,
        }

    @property
    def tokenizer(self) -> Any:
        tokenizer = getattr(self._resolved_model(), "tokenizer", None)
        if tokenizer is None:
            raise RuntimeError("The configured text embedding provider does not expose a tokenizer.")
        return tokenizer

    def encode_texts(self, texts: Sequence[str], *, batch_size: int, normalize: bool) -> Any:
        if not texts:
            return []
        embeddings = self._resolved_model().encode(
            list(texts),
            batch_size=batch_size,
            normalize_embeddings=normalize,
            show_progress_bar=False,
        )
        if len(embeddings) != len(texts):
            raise RuntimeError("Text embedding provider returned a different number of vectors than requested texts.")
        return embeddings

    def _resolved_model(self) -> Any:
        if self.model is None:
            if self.progress:
                self.progress(f"Loading contextual similarity model {self.model_name}...")
            self.model = self._load_model()
            if self.progress:
                self.progress("Contextual similarity model ready.")
        return self.model

    def _load_model(self) -> Any:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Semantic chunking requires sentence-transformers. "
                "Install the Gurubodh CLI package dependencies before running semantic chunking."
            ) from exc

        kwargs: dict[str, Any] = {
            "cache_folder": str(self.cache_dir_resolver()),
            "local_files_only": self.local_files_only,
        }
        if self.device:
            kwargs["device"] = self.device
        if self.model_revision:
            kwargs["revision"] = self.model_revision
        try:
            return SentenceTransformer(self.model_name, **kwargs)
        except OSError as exc:
            if not self.local_files_only:
                raise
            revision = self.model_revision or "the requested revision"
            raise ModelCacheConfigError(
                f"Cached model {self.model_name} at revision {revision} is unavailable or incomplete in "
                f"{self.cache_dir_resolver()}. Populate that exact pinned snapshot before running a cached-only job."
            ) from exc
