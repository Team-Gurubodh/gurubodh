import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gurubodh.ml.semantic_chunking.chunker import SemanticChunker
from gurubodh.ml.semantic_chunking.cli import build_parser
from gurubodh.ml.semantic_chunking.config import (
    DEFAULT_EMBEDDING_DIMENSION,
    DEFAULT_EMBEDDING_MODE,
    DEFAULT_MODEL_NAME,
    DEFAULT_PROVIDER,
    DEFAULT_STRATEGY_VERSION,
    MODEL_CACHE_ENV_VAR,
    ModelCacheConfigError,
    SemanticChunkConfig,
    SemanticChunkConfigError,
)
from gurubodh.ml.semantic_chunking.file_io import chunk_folder, validate_document_for_source
from gurubodh.ml.semantic_chunking.models import Chunk, ChunkedDocument, text_sha256, whitespace_insensitive_sha256
from gurubodh.ml.semantic_chunking.segmenter import SemanticChunkingParagraphSegmenter


class FakeEmbeddingModel:
    def __init__(self):
        self.calls = []
        self.tokenizer = FakeTokenizer()

    def encode(self, windows, batch_size, normalize_embeddings, show_progress_bar):
        self.calls.append(
            {
                "windows": windows,
                "batch_size": batch_size,
                "normalize_embeddings": normalize_embeddings,
                "show_progress_bar": show_progress_bar,
            }
        )
        return [[1.0, 0.0] if index % 2 == 0 else [0.0, 1.0] for index, _ in enumerate(windows)]


class FakeTokenizer:
    def __init__(self):
        self.calls = []

    def encode(self, text, add_special_tokens=False):
        self.calls.append({"text": text, "add_special_tokens": add_special_tokens})
        return text.split()


def make_document(source_name, chunks, source_text):
    concatenated = "".join(chunk.text for chunk in chunks)
    return ChunkedDocument(
        source_name=source_name,
        provider=DEFAULT_PROVIDER,
        model_name=DEFAULT_MODEL_NAME,
        embedding_mode=DEFAULT_EMBEDDING_MODE,
        embedding_dimension=DEFAULT_EMBEDDING_DIMENSION,
        strategy_version=DEFAULT_STRATEGY_VERSION,
        threshold_percentile=80.0,
        min_chars=0,
        window_size=3,
        batch_size=16,
        normalize_embeddings=True,
        device=None,
        breakpoint_threshold=None,
        chunks=chunks,
        source_text_sha256=whitespace_insensitive_sha256(source_text),
        concatenated_chunks_sha256=whitespace_insensitive_sha256(concatenated),
    )


class EmptySegmenter:
    provider_metadata = {}

    def segment(self, text, source_name=None):
        return make_document(source_name, [], text)


class SemanticChunkingTests(unittest.TestCase):
    def test_config_defaults_and_provider_metadata_are_explicit(self):
        config = SemanticChunkConfig()

        self.assertEqual(config.provider, "semantic-chunking")
        self.assertEqual(config.model_name, "BAAI/bge-m3")
        self.assertEqual(config.threshold_percentile, 80.0)
        self.assertEqual(config.min_chars, 650)
        self.assertEqual(config.window_size, 3)
        self.assertEqual(config.batch_size, 16)
        self.assertTrue(config.normalize_embeddings)
        self.assertEqual(config.embedding_mode, "dense")
        self.assertEqual(config.embedding_dimension, 1024)
        self.assertEqual(config.strategy_version, "semantic-window-v1")
        self.assertEqual(config.provider_metadata()["provider"], "semantic-chunking")

    def test_config_rejects_invalid_values(self):
        with self.assertRaises(SemanticChunkConfigError):
            SemanticChunkConfig(provider="sarvam")
        with self.assertRaises(SemanticChunkConfigError):
            SemanticChunkConfig(threshold_percentile=101)
        with self.assertRaises(SemanticChunkConfigError):
            SemanticChunkConfig(window_size=0)
        with self.assertRaises(SemanticChunkConfigError):
            SemanticChunkConfig(embedding_dimension=768)

    def test_missing_model_cache_env_var_is_clear(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ModelCacheConfigError) as exc:
                SemanticChunkConfig.from_env().resolved_cache_dir()

        self.assertIn(MODEL_CACHE_ENV_VAR, str(exc.exception))

    def test_semantic_chunker_constructs_without_loading_model(self):
        with patch.object(SemanticChunker, "_load_model") as load_model:
            chunker = SemanticChunker(SemanticChunkConfig())

        load_model.assert_not_called()
        self.assertIsNone(chunker._model)

    def test_semantic_chunker_uses_injected_model_and_emits_spans_and_checksums(self):
        model = FakeEmbeddingModel()
        config = SemanticChunkConfig(min_chars=0, threshold_percentile=50.0)
        document = SemanticChunker(config, model=model).chunk_text("पहला वाक्य।\n\nदूसरा वाक्य।", "chapter.txt")

        self.assertEqual(document.chunk_count, 2)
        self.assertEqual(document.source_text_sha256, document.concatenated_chunks_sha256)
        self.assertEqual(document.chunks[0].start_char, 0)
        self.assertEqual(document.chunks[0].end_char, len("पहला वाक्य।"))
        self.assertEqual(document.chunks[0].chunk_text_sha256, text_sha256("पहला वाक्य।"))
        self.assertEqual(document.chunks[0].estimated_embedding_token_count, 2)
        self.assertEqual(document.estimated_embedding_token_count, 4)
        self.assertFalse(model.tokenizer.calls[0]["add_special_tokens"])
        self.assertEqual(model.calls[0]["batch_size"], 16)

    def test_chunk_folder_writes_json_markdown_and_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "text_and_metadata"
            output_parent = root / "chapters"
            source_dir.mkdir()
            source_text = "पहला वाक्य।\n\nदूसरा वाक्य।"
            (source_dir / "001.txt").write_text(source_text, encoding="utf-8")
            config = SemanticChunkConfig(min_chars=0, threshold_percentile=50.0)
            segmenter = SemanticChunkingParagraphSegmenter(config, SemanticChunker(config, model=FakeEmbeddingModel()))

            documents = chunk_folder(source_dir, output_parent, config, segmenter=segmenter)

            output_dir = output_parent / "semantic_chunks_bge_m3"
            payload = json.loads((output_dir / "001.chunks.json").read_text(encoding="utf-8"))
            summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(len(documents), 1)
            self.assertEqual(payload["provider"], "semantic-chunking")
            self.assertEqual(payload["model"], "BAAI/bge-m3")
            self.assertEqual(payload["token_counting"]["tokenizer"], "BAAI/bge-m3")
            self.assertFalse(payload["token_counting"]["includes_special_tokens"])
            self.assertEqual(payload["chunks"][0]["estimated_embedding_token_count"], 2)
            self.assertEqual(payload["estimated_embedding_token_count"], 4)
            self.assertEqual(summary["files"][0]["estimated_embedding_token_count"], 4)
            self.assertEqual(payload["source_text_sha256"], payload["concatenated_chunks_sha256"])
            self.assertTrue((output_dir / "001.chunks.md").exists())
            self.assertTrue((output_dir / "summary.json").exists())

    def test_chunk_folder_reports_progress(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            output_parent = root / "out"
            source_dir.mkdir()
            source_text = "पहला वाक्य।"
            (source_dir / "001.txt").write_text(source_text, encoding="utf-8")
            events = []

            chunk_folder(
                source_dir,
                output_parent,
                SemanticChunkConfig(),
                segmenter=SemanticChunkingParagraphSegmenter(
                    SemanticChunkConfig(),
                    SemanticChunker(SemanticChunkConfig(), model=FakeEmbeddingModel()),
                ),
                progress=events.append,
            )

            self.assertIn("Found 1 chapter text file.", events)
            self.assertIn("[1/1] 001.txt: reading source text", events)
            self.assertIn(f"[1/1] 001.txt: segmenting {len(source_text)} characters", events)
            self.assertIn("[1/1] 001.txt: validating chunks", events)
            self.assertIn("[1/1] 001.txt: wrote 1 chunk", events)
            self.assertIn("Writing summary.json", events)
            self.assertIn("Semantic chunking complete: 1 file, 1 chunk", events)

    def test_checksum_mismatch_prevents_output_for_failed_chapter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            output_parent = root / "out"
            source_dir.mkdir()
            (source_dir / "001.txt").write_text("अक्षर बचेगा।", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                chunk_folder(
                    source_dir,
                    output_parent,
                    SemanticChunkConfig(),
                    segmenter=EmptySegmenter(),
                )

            output_dir = output_parent / "semantic_chunks_bge_m3"
            self.assertFalse((output_dir / "001.chunks.json").exists())
            self.assertFalse((output_dir / "001.chunks.md").exists())

    def test_validate_document_rejects_non_whitespace_gap(self):
        source_text = "पहला। छूटा।"
        chunk = Chunk(
            index=1,
            text="पहला।",
            sentence_count=1,
            char_count=len("पहला।"),
            estimated_embedding_token_count=1,
            start_sentence=0,
            end_sentence=0,
            start_char=0,
            end_char=len("पहला।"),
            chunk_text_sha256=text_sha256("पहला।"),
        )
        document = make_document("chapter.txt", [chunk], source_text)

        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            validate_document_for_source(source_text, document)

    def test_generate_chunks_parser_accepts_poc_arguments(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "--source-dir",
                "/tmp/source",
                "--output-dir",
                "/tmp/output",
                "--threshold-percentile",
                "82",
                "--min-chars",
                "700",
                "--window-size",
                "3",
                "--batch-size",
                "16",
                "--device",
                "cpu",
                "--chapter",
                "001",
                "--chapters",
                "002",
                "003.txt",
                "--overwrite",
            ]
        )

        self.assertEqual(args.threshold_percentile, 82)
        self.assertEqual(args.min_chars, 700)
        self.assertEqual(args.device, "cpu")
        self.assertEqual(args.chapters, ["001"])
        self.assertEqual(args.chapter_list, ["002", "003.txt"])
        self.assertTrue(args.overwrite)


if __name__ == "__main__":
    unittest.main()
