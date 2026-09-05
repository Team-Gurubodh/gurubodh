import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gurubodh.ml.embeddings import SentenceTransformerEmbeddingHelper
from gurubodh.ml.semantic_chunking.chunker import SemanticChunker
from gurubodh.ml.semantic_chunking.config import (
    DEFAULT_MODEL_NAME,
    DEFAULT_PROVIDER,
    MODEL_CACHE_ENV_VAR,
    ModelCacheConfigError,
    SemanticChunkConfig,
    SemanticChunkConfigError,
)
from gurubodh.ml.semantic_chunking.file_io import validate_document_for_source
from gurubodh.ml.semantic_chunking.models import Chunk, ChunkedDocument, text_sha256, whitespace_insensitive_sha256


class FakeTokenizer:
    def encode(self, text, add_special_tokens=False):
        return text.split()


class FakeEmbeddingModel:
    def __init__(self):
        self.calls = []
        self.tokenizer = FakeTokenizer()

    def encode(self, texts, batch_size, normalize_embeddings, show_progress_bar):
        self.calls.append({
            "texts": texts, "batch_size": batch_size,
            "normalize_embeddings": normalize_embeddings, "show_progress_bar": show_progress_bar,
        })
        return [[1.0, 0.0] if index % 2 == 0 else [0.0, 1.0] for index, _ in enumerate(texts)]


def make_document(source_name, chunks, source_text):
    return ChunkedDocument(
        source_name=source_name, provider=DEFAULT_PROVIDER, model_name=DEFAULT_MODEL_NAME,
        strategy_version="semantic-window-v1", threshold_percentile=80.0, min_chars=0,
        window_size=3, batch_size=16, normalize_contextual_vectors=True, device=None,
        breakpoint_threshold=None, chunks=chunks,
        source_text_sha256=whitespace_insensitive_sha256(source_text),
        concatenated_chunks_sha256=whitespace_insensitive_sha256("".join(chunk.text for chunk in chunks)),
    )


class SemanticChunkingTests(unittest.TestCase):
    def test_config_defaults_are_chunking_specific(self):
        config = SemanticChunkConfig()
        self.assertEqual(config.provider, "semantic-chunking")
        self.assertEqual(config.model_name, "BAAI/bge-m3")
        self.assertTrue(config.normalize_contextual_vectors)
        self.assertNotIn("embedding", json.dumps(config.provider_metadata()))
        with self.assertRaises(SemanticChunkConfigError):
            SemanticChunkConfig(provider="other")
        with self.assertRaises(SemanticChunkConfigError):
            SemanticChunkConfig(normalize_contextual_vectors="yes")

    def test_missing_model_cache_env_var_is_clear(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ModelCacheConfigError) as exc:
                SemanticChunkConfig.from_env().resolved_cache_dir()
        self.assertIn(MODEL_CACHE_ENV_VAR, str(exc.exception))

    def test_embedding_helper_loads_pinned_model_and_encodes_batches(self):
        calls = []

        class CapturingSentenceTransformer:
            def __init__(self, model_name, **kwargs):
                calls.append((model_name, kwargs))
                self.tokenizer = FakeTokenizer()

            def encode(self, texts, **kwargs):
                calls.append((list(texts), kwargs))
                return [[0.5, 0.5] for _ in texts]

        with tempfile.TemporaryDirectory() as cache_dir:
            helper = SentenceTransformerEmbeddingHelper(
                provider="sentence-transformers", model_name="BAAI/bge-m3",
                model_revision="5617a9f61b028005a4858fdac845db406aefb181",
                cache_dir_resolver=lambda: Path(cache_dir), local_files_only=True, device="cpu",
            )
            with patch.dict(sys.modules, {"sentence_transformers": SimpleNamespace(SentenceTransformer=CapturingSentenceTransformer)}):
                vectors = helper.encode_texts(["one", "two"], batch_size=2, normalize=True)

        self.assertEqual(vectors, [[0.5, 0.5], [0.5, 0.5]])
        self.assertEqual(calls[0][0], "BAAI/bge-m3")
        self.assertEqual(calls[0][1]["revision"], "5617a9f61b028005a4858fdac845db406aefb181")
        self.assertTrue(calls[0][1]["local_files_only"])
        self.assertEqual(helper.metadata["provider"], "sentence-transformers")
        self.assertEqual(calls[1][1]["batch_size"], 2)

    def test_contextual_encoding_is_the_only_encoding_pass(self):
        model = FakeEmbeddingModel()
        document = SemanticChunker(SemanticChunkConfig(min_chars=0, threshold_percentile=50.0), model=model).chunk_text(
            "पहला वाक्य।\n\nदूसरा वाक्य।", "chapter.txt"
        )

        self.assertEqual(document.chunk_count, 2)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(len(model.calls[0]["texts"]), 2)
        self.assertEqual(document.chunks[0].estimated_token_count, 2)
        self.assertFalse(hasattr(document.chunks[0], "dense_embedding"))
        self.assertEqual(document.source_text_sha256, document.concatenated_chunks_sha256)

        # Fixed pre-repair output: catch changes to text, codepoint spans,
        # checksums and token accounting without loading a real model.
        self.assertEqual([chunk.to_dict() for chunk in document.chunks], [
            {
                "index": 1, "text": "पहला वाक्य।", "sentence_count": 1,
                "char_count": 11, "estimated_token_count": 2,
                "start_sentence": 0, "end_sentence": 0, "start_char": 0, "end_char": 11,
                "chunk_text_sha256": "fcac1a80ea6e68669ef4942137d2dc17f45a14e84649d2a2dae04bbe51af5833",
            },
            {
                "index": 2, "text": "दूसरा वाक्य।", "sentence_count": 1,
                "char_count": 12, "estimated_token_count": 2,
                "start_sentence": 1, "end_sentence": 1, "start_char": 13, "end_char": 25,
                "chunk_text_sha256": "9a6153560c03229b235ec02bf409d22ef5c868d9b641332dee2810f061cd09cf",
            },
        ])
        self.assertEqual(document.estimated_token_count, 4)
        self.assertEqual(
            document.source_text_sha256,
            "df2047898e9ee03e96504738037caf7d1523fec64a50ab620516805c8894a11f",
        )
        self.assertEqual(model.calls, [{
            "texts": ["पहला वाक्य। दूसरा वाक्य।", "पहला वाक्य। दूसरा वाक्य।"],
            "batch_size": 16, "normalize_embeddings": True, "show_progress_bar": False,
        }])
        validate_document_for_source("पहला वाक्य।\n\nदूसरा वाक्य।", document)

    def test_cached_model_failure_is_caught_through_legacy_config_error(self):
        def unavailable_model(*args, **kwargs):
            raise OSError("missing pinned snapshot")

        helper = SentenceTransformerEmbeddingHelper(
            provider="sentence-transformers", model_name="BAAI/bge-m3",
            model_revision="5617a9f61b028005a4858fdac845db406aefb181",
            cache_dir_resolver=lambda: Path("/unused-model-cache"),
            local_files_only=True, device="cpu",
        )
        with patch.dict(sys.modules, {"sentence_transformers": SimpleNamespace(SentenceTransformer=unavailable_model)}):
            with self.assertRaisesRegex(ModelCacheConfigError, "unavailable or incomplete") as exc:
                helper.encode_texts(["text"], batch_size=1, normalize=True)
        from gurubodh.ml.errors import ModelCacheConfigError as SharedModelCacheConfigError

        self.assertIs(type(exc.exception), SharedModelCacheConfigError)
        self.assertIsInstance(exc.exception.__cause__, OSError)

    def test_coverage_validation_rejects_non_whitespace_gap(self):
        source = "पहला। छूटा।"
        chunk = Chunk(
            index=1, text="पहला।", sentence_count=1, char_count=len("पहला।"),
            estimated_token_count=1, start_sentence=0, end_sentence=0,
            start_char=0, end_char=len("पहला।"), chunk_text_sha256=text_sha256("पहला।"),
        )
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            validate_document_for_source(source, make_document("chapter.txt", [chunk], source))


if __name__ == "__main__":
    unittest.main()
