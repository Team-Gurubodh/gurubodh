import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from gurubodh.config import load_generate_chunks_job
from gurubodh.ml.semantic_chunking.config import SemanticChunkConfig
from gurubodh.ml.semantic_chunking.models import Chunk, ChunkedDocument, text_sha256, whitespace_insensitive_sha256
from gurubodh.naming import chapter_output_filename
from gurubodh.pipelines.generate_chunks import run_generate_chunks_job
from gurubodh.project import ProjectContext


def base_config(root_dir):
    return {
        "schema_version": "1.0.0",
        "pipeline": "generate-chunks",
        "source": {
            "backend": "local",
            "root_dir": str(root_dir),
            "subject_dir": "123_spand_rahasya",
        },
        "destination": {
            "backend": "local",
            "root_dir": str(root_dir),
            "subject_dir": "123_spand_rahasya",
        },
        "naming": {
            "category_code": "CAT001",
            "subject_code": "SUB123",
            "title_slug": "spand-rahasya",
            "version": "01",
            "subversion": "01",
        },
        "chunking": {
            "provider": "semantic-chunking",
            "model": "BAAI/bge-m3",
            "model_revision": None,
            "embedding_mode": "dense",
            "embedding_dimension": 1024,
            "threshold_percentile": 80.0,
            "min_chars": 600,
            "window_size": 3,
            "batch_size": 16,
            "normalize_embeddings": True,
            "device": None,
            "local_files_only": False,
        },
    }


def metadata_for(config, chapter_number, text):
    text_name = chapter_output_filename(config, chapter_number, ".txt")
    metadata_name = chapter_output_filename(config, chapter_number, ".json")
    subject_dir = config["source"]["subject_dir"]
    relative_text = f"chapters/text_and_metadata/{text_name}"
    relative_metadata = f"chapters/text_and_metadata/{metadata_name}"
    return {
        "document": {
            "category_code": config["naming"]["category_code"],
            "subject_code": config["naming"]["subject_code"],
            "title_slug": config["naming"]["title_slug"],
            "chapter_number": f"{chapter_number:03d}",
            "version": "v01.01",
        },
        "storage": {
            "artifacts": {
                "text": {
                    "backend": "local",
                    "path": relative_text,
                    "url": None,
                },
                "metadata": {
                    "backend": "local",
                    "path": relative_metadata,
                    "url": None,
                },
            }
        },
        "integrity": {
            "artifacts": {
                "text": {
                    "algorithm": "sha256",
                    "encoding": "UTF-8",
                    "line_endings": "LF",
                    "scope": "artifact-bytes",
                    "value": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                }
            }
        },
        "files": {
            "text_filename": text_name,
            "metadata_filename": metadata_name,
        },
        "subject_dir": subject_dir,
    }


def write_prepared_chapter(root_dir, config, chapter_number=1, text="पहला वाक्य।\n"):
    subject_dir = Path(root_dir) / config["source"]["subject_dir"]
    text_dir = subject_dir / "chapters" / "text_and_metadata"
    text_dir.mkdir(parents=True, exist_ok=True)
    text_name = chapter_output_filename(config, chapter_number, ".txt")
    metadata_name = chapter_output_filename(config, chapter_number, ".json")
    (text_dir / text_name).write_text(text, encoding="utf-8")
    (text_dir / metadata_name).write_text(
        json.dumps(metadata_for(config, chapter_number, text), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class FakeSegmenter:
    provider_metadata = {}

    def segment(self, text, source_name=None):
        chunk_text = text.strip()
        chunk = Chunk(
            index=1,
            text=chunk_text,
            sentence_count=1,
            char_count=len(chunk_text),
            estimated_embedding_token_count=2,
            start_sentence=0,
            end_sentence=0,
            start_char=0,
            end_char=len(chunk_text),
            chunk_text_sha256=text_sha256(chunk_text),
            dense_embedding=[0.25] * 1024,
        )
        return ChunkedDocument(
            source_name=source_name,
            provider="semantic-chunking",
            model_name="BAAI/bge-m3",
            embedding_mode="dense",
            embedding_dimension=1024,
            strategy_version="semantic-window-v1",
            threshold_percentile=80.0,
            min_chars=650,
            window_size=3,
            batch_size=16,
            normalize_embeddings=True,
            device=None,
            breakpoint_threshold=None,
            chunks=[chunk],
            source_text_sha256=whitespace_insensitive_sha256(text),
            concatenated_chunks_sha256=whitespace_insensitive_sha256(chunk_text),
        )


class FakeR2Client:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})
        self.uploads = []
        self.deleted_prefixes = []

    def list_keys(self, bucket, prefix):
        return sorted(key for key in self.objects if key.startswith(prefix))

    def prefix_has_objects(self, bucket, prefix):
        return any(key.startswith(prefix) for key in self.objects)

    def exists(self, bucket, key):
        return key in self.objects

    def download_file(self, bucket, key, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(self.objects[key], encoding="utf-8")

    def upload_file(self, path, bucket, key):
        self.uploads.append((Path(path).name, bucket, key))
        self.objects[key] = Path(path).read_text(encoding="utf-8")

    def delete_prefix(self, bucket, prefix):
        self.deleted_prefixes.append((bucket, prefix))
        deleted = [key for key in self.objects if key.startswith(prefix)]
        for key in deleted:
            del self.objects[key]
        return deleted


class GenerateChunksPipelineTests(unittest.TestCase):
    def write_config(self, config):
        path = Path(self.temp_dir.name) / "generate-chunks.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return load_generate_chunks_job(path), path

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.context = ProjectContext(root=Path(self.temp_dir.name), legacy_converter=Path(self.temp_dir.name) / "converter.js")

    def test_local_job_writes_chunk_json_summary_and_audit_without_metadata_mutation(self):
        config = base_config(Path(self.temp_dir.name))
        write_prepared_chapter(self.temp_dir.name, config)
        metadata_path = (
            Path(self.temp_dir.name)
            / "123_spand_rahasya"
            / "chapters"
            / "text_and_metadata"
            / chapter_output_filename(config, 1, ".json")
        )
        before_metadata = metadata_path.read_text(encoding="utf-8")
        loaded, config_path = self.write_config(config)

        with redirect_stdout(StringIO()):
            result = run_generate_chunks_job(
                self.context,
                loaded,
                config_path=config_path,
                segmenter=FakeSegmenter(),
                progress=lambda message: None,
            )

        output_dir = Path(self.temp_dir.name) / "123_spand_rahasya" / "chapters" / "semantic_chunks_and_embeddings"
        chunk_path = output_dir / "CAT001_SUB123_spand-rahasya_001_v01.01.chunks.json"
        summary_path = output_dir / "summary.json"
        payload = json.loads(chunk_path.read_text(encoding="utf-8"))
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        reports = list((Path(self.temp_dir.name) / "123_spand_rahasya" / "run_reports").glob("*generate-chunks*.json"))

        self.assertEqual(result["processed_chapter_count"], 1)
        self.assertTrue(chunk_path.exists())
        self.assertTrue(summary_path.exists())
        self.assertEqual(payload["chunks"][0]["dense_embedding"], [0.25] * 1024)
        self.assertEqual(payload["embedding"]["embedding_dimension"], 1024)
        self.assertEqual(summary["counts"]["total_chunk_count"], 1)
        self.assertEqual(summary["chapters"][0]["chunk_filename"], chunk_path.name)
        self.assertEqual(len(reports), 1)
        self.assertEqual(metadata_path.read_text(encoding="utf-8"), before_metadata)
        self.assertFalse(list(output_dir.glob("*.md")))

    def test_local_overwrite_is_scoped_to_semantic_output_dir(self):
        config = base_config(Path(self.temp_dir.name))
        write_prepared_chapter(self.temp_dir.name, config)
        subject_dir = Path(self.temp_dir.name) / "123_spand_rahasya"
        output_dir = subject_dir / "chapters" / "semantic_chunks_and_embeddings"
        output_dir.mkdir(parents=True)
        (output_dir / "stale.chunks.json").write_text("{}", encoding="utf-8")
        keep_path = subject_dir / "full_subject" / "keep.txt"
        keep_path.parent.mkdir(parents=True, exist_ok=True)
        keep_path.write_text("keep", encoding="utf-8")
        loaded, config_path = self.write_config(config)

        with redirect_stdout(StringIO()):
            run_generate_chunks_job(
                self.context,
                loaded,
                overwrite=True,
                config_path=config_path,
                segmenter=FakeSegmenter(),
                progress=lambda message: None,
            )

        self.assertFalse((output_dir / "stale.chunks.json").exists())
        self.assertTrue(keep_path.exists())

    def test_chapter_filter_skips_unlisted_chapters(self):
        config = base_config(Path(self.temp_dir.name))
        config["chapters"] = ["002"]
        write_prepared_chapter(self.temp_dir.name, config, chapter_number=1, text="पहला।\n")
        write_prepared_chapter(self.temp_dir.name, config, chapter_number=2, text="दूसरा।\n")
        loaded, config_path = self.write_config(config)

        with redirect_stdout(StringIO()):
            result = run_generate_chunks_job(
                self.context,
                loaded,
                config_path=config_path,
                segmenter=FakeSegmenter(),
                progress=lambda message: None,
            )

        output_dir = Path(self.temp_dir.name) / "123_spand_rahasya" / "chapters" / "semantic_chunks_and_embeddings"
        self.assertEqual(result["processed_chapter_count"], 1)
        self.assertEqual(result["skipped_chapter_count"], 1)
        self.assertFalse((output_dir / "CAT001_SUB123_spand-rahasya_001_v01.01.chunks.json").exists())
        self.assertTrue((output_dir / "CAT001_SUB123_spand-rahasya_002_v01.01.chunks.json").exists())

    def test_r2_job_reads_source_deletes_only_output_prefix_and_uploads_reports(self):
        config = base_config(Path(self.temp_dir.name))
        text = "पहला वाक्य।\n"
        text_name = chapter_output_filename(config, 1, ".txt")
        metadata_name = chapter_output_filename(config, 1, ".json")
        r2_config = json.loads(json.dumps(config))
        r2_config["source"] = {
            "backend": "r2",
            "bucket": "gurubodh-library-dev",
            "prefix": "cms_library",
            "subject_dir": "123_spand_rahasya",
            "url_base": None,
        }
        r2_config["destination"] = json.loads(json.dumps(r2_config["source"]))
        metadata = metadata_for(config, 1, text)
        metadata["storage"]["artifacts"]["text"] = {
            "backend": "r2",
            "bucket": "gurubodh-library-dev",
            "key": f"cms_library/123_spand_rahasya/chapters/text_and_metadata/{text_name}",
            "url": None,
        }
        metadata["storage"]["artifacts"]["metadata"] = {
            "backend": "r2",
            "bucket": "gurubodh-library-dev",
            "key": f"cms_library/123_spand_rahasya/chapters/text_and_metadata/{metadata_name}",
            "url": None,
        }
        client = FakeR2Client(
            {
                f"cms_library/123_spand_rahasya/chapters/text_and_metadata/{text_name}": text,
                f"cms_library/123_spand_rahasya/chapters/text_and_metadata/{metadata_name}": json.dumps(metadata, ensure_ascii=False),
                "cms_library/123_spand_rahasya/chapters/semantic_chunks_and_embeddings/stale.chunks.json": "{}",
                "cms_library/123_spand_rahasya/full_subject/keep.txt": "keep",
            }
        )
        loaded, config_path = self.write_config(r2_config)

        with redirect_stdout(StringIO()):
            run_generate_chunks_job(
                self.context,
                loaded,
                overwrite=True,
                config_path=config_path,
                segmenter=FakeSegmenter(),
                r2_client=client,
                progress=lambda message: None,
            )

        uploaded_keys = [key for _, _, key in client.uploads]
        self.assertIn(
            (
                "gurubodh-library-dev",
                "cms_library/123_spand_rahasya/chapters/semantic_chunks_and_embeddings/",
            ),
            client.deleted_prefixes,
        )
        self.assertIn("cms_library/123_spand_rahasya/full_subject/keep.txt", client.objects)
        self.assertTrue(any(key.endswith(".chunks.json") for key in uploaded_keys))
        self.assertTrue(any("/run_reports/" in key and key.endswith(".json") for key in uploaded_keys))
        self.assertTrue(any("/run_reports/" in key and key.endswith(".md") for key in uploaded_keys))


if __name__ == "__main__":
    unittest.main()
