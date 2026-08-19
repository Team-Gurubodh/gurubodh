import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from botocore.exceptions import ClientError

from gurubodh.config import load_generate_chunks_job, load_prep_subject_job
from gurubodh.metadata import build_chapter_metadata, text_artifact_integrity
from gurubodh.storage import (
    R2StorageClient,
    ensure_local_destination,
    ensure_r2_destination_available,
    materialize_source,
    publish_r2_destination,
)


BASE_CONFIG = {
    "schema_version": "1.2.0",
    "pipeline": "unicode-docx-ingest",
    "source": {
        "root_dir": "/tmp/source",
        "relative_path": "subject/source.docx",
        "font_encoding": "unicode",
        "file_format": "docx",
    },
    "destination": {
        "root_dir": "/tmp/destination",
        "subject_dir": "129_spand_rahasya",
    },
    "naming": {
        "category_code": "CAT020",
        "subject_code": "SUB129",
        "title_slug": "spand-rahasya",
        "version": "01",
        "subversion": "01",
    },
    "chapter_split": {
        "enabled": False,
    },
}


class FakeR2Client:
    def __init__(self, existing_keys=None):
        self.existing_keys = set(existing_keys or [])
        self.uploads = []

    def exists(self, bucket, key):
        return key in self.existing_keys

    def prefix_has_objects(self, bucket, prefix):
        self.prefix_check = (bucket, prefix)
        return any(key.startswith(prefix) for key in self.existing_keys)

    def upload_file(self, path, bucket, key):
        self.uploads.append((Path(path).name, bucket, key))
        self.existing_keys.add(key)

    def delete_prefix(self, bucket, prefix):
        deleted = sorted(key for key in self.existing_keys if key.startswith(prefix))
        self.existing_keys.difference_update(deleted)
        self.deleted_prefix = (bucket, prefix)
        self.deleted_keys = deleted
        return deleted

    def download_file(self, bucket, key, path):
        self.download = (bucket, key, Path(path).name)
        Path(path).write_bytes(b"docx bytes")


class FakeMissingR2ObjectClient:
    def download_file(self, bucket, key, path):
        raise ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "HeadObject",
        )


class StorageConfigTests(unittest.TestCase):
    def write_config(self, config):
        temp_dir = tempfile.TemporaryDirectory()
        path = Path(temp_dir.name) / "job.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        self.addCleanup(temp_dir.cleanup)
        return path

    def test_legacy_local_shape_still_loads(self):
        config = load_prep_subject_job(self.write_config(BASE_CONFIG))

        self.assertEqual(config["source"]["relative_path"], "subject/source.docx")
        self.assertEqual(config["destination"]["subject_dir"], "129_spand_rahasya")

    def test_local_destination_ignores_unowned_files_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            subject_dir = Path(temp_dir) / "129_spand_rahasya"
            subject_dir.mkdir()
            (subject_dir / "stale.txt").write_text("stale", encoding="utf-8")

            ensure_local_destination(subject_dir, overwrite=False)
            self.assertTrue((subject_dir / "stale.txt").exists())

    def test_local_destination_overwrite_removes_only_canonical_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            subject_dir = Path(temp_dir) / "129_spand_rahasya"
            canonical_file = subject_dir / "chapters" / "text_and_metadata" / "stale.txt"
            semantic_file = subject_dir / "chapters" / "semantic_chunks_and_embeddings" / "keep.json"
            canonical_file.parent.mkdir(parents=True)
            semantic_file.parent.mkdir(parents=True)
            canonical_file.write_text("stale", encoding="utf-8")
            semantic_file.write_text("keep", encoding="utf-8")

            audit = ensure_local_destination(subject_dir, overwrite=True)

            self.assertFalse(audit["removed_for_overwrite"])
            self.assertTrue(subject_dir.is_dir())
            self.assertTrue(canonical_file.exists())
            self.assertTrue(semantic_file.exists())

    def test_r2_source_and_destination_shape_loads(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["source"] = {
            "backend": "r2",
            "bucket": "gurubodh-library-dev",
            "key": "source_library/129_spand_rahasya/source.docx",
            "font_encoding": "unicode",
            "file_format": "docx",
        }
        config["destination"] = {
            "backend": "r2",
            "bucket": "gurubodh-library-dev",
            "prefix": "cms_library",
            "subject_dir": "129_spand_rahasya",
            "url_base": None,
        }

        loaded = load_prep_subject_job(self.write_config(config))

        self.assertEqual(loaded["source"]["key"], "source_library/129_spand_rahasya/source.docx")
        self.assertEqual(loaded["destination"]["prefix"], "cms_library")

    def test_r2_metadata_uses_bucket_keys_and_nullable_urls(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["source"] = {
            "backend": "r2",
            "bucket": "gurubodh-library-dev",
            "key": "source_library/129_spand_rahasya/source.docx",
            "font_encoding": "unicode",
            "file_format": "docx",
        }
        config["destination"] = {
            "backend": "r2",
            "bucket": "gurubodh-library-dev",
            "prefix": "cms_library",
            "subject_dir": "129_spand_rahasya",
            "url_base": None,
        }

        metadata = build_chapter_metadata(
            config,
            1,
            {
                "metadata": "chapter.json",
                "text": "chapter.txt",
                "msword": "chapter.docx",
                "metadata_relative_path": Path("chapters/text_and_metadata/chapter.json"),
                "text_relative_path": Path("chapters/text_and_metadata/chapter.txt"),
                "msword_relative_path": Path("chapters/msword/chapter.docx"),
                "full_msword_relative_path": Path("full_subject/full.docx"),
                "full_text_relative_path": Path("full_subject/full.txt"),
            },
            "श्री स्वामी समर्थ",
            {},
            "2026-07-08T00:00:00Z",
            "python3 -m gurubodh prep-subject",
        )

        self.assertNotIn("root_dir", json.dumps(metadata))
        self.assertEqual(
            metadata["files"],
            {
                "metadata_filename": "chapter.json",
                "text_filename": "chapter.txt",
                "msword_filename": "chapter.docx",
            },
        )
        self.assertEqual(metadata["storage"]["source"]["key"], "source_library/129_spand_rahasya/source.docx")
        self.assertEqual(
            metadata["storage"]["artifacts"]["metadata"]["key"],
            "cms_library/129_spand_rahasya/chapters/text_and_metadata/chapter.json",
        )
        self.assertIsNone(metadata["storage"]["artifacts"]["metadata"]["url"])

    def test_chapter_metadata_includes_text_artifact_integrity(self):
        text = "श्री स्वामी समर्थ\n\nUnicode chapter text: ज्ञान"

        metadata = build_chapter_metadata(
            BASE_CONFIG,
            1,
            {
                "metadata": "chapter.json",
                "text": "chapter.txt",
                "msword": "chapter.docx",
                "metadata_relative_path": Path("chapters/text_and_metadata/chapter.json"),
                "text_relative_path": Path("chapters/text_and_metadata/chapter.txt"),
                "msword_relative_path": Path("chapters/msword/chapter.docx"),
                "full_msword_relative_path": Path("full_subject/full.docx"),
                "full_text_relative_path": Path("full_subject/full.txt"),
            },
            text,
            {},
            "2026-07-08T00:00:00Z",
            "python3 -m gurubodh prep-subject",
        )

        expected_digest = hashlib.sha256((text + "\n").encode("utf-8")).hexdigest()
        self.assertEqual(
            metadata["integrity"],
            {
                "artifacts": {
                    "text": {
                        "algorithm": "sha256",
                        "encoding": "UTF-8",
                        "line_endings": "LF",
                        "scope": "artifact-bytes",
                        "value": expected_digest,
                    }
                }
            },
        )
        self.assertNotIn("metadata", metadata["integrity"]["artifacts"])

    def test_chapter_metadata_tags_summary_markers(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["metadata_defaults"] = {
            "summary_chapter_markers": [
                "उपसंहार",
                "उपसंहारात्मक",
                "उपसंभारात्मक",
                "उपसंभारात्त्मक",
                "उपसंभार",
            ],
        }

        for marker in [
            "उपसंहार",
            "उपसंहारात्मक",
            "उपसंभारात्मक",
            "उपसंभारात्त्मक",
            "उपसंभार",
        ]:
            with self.subTest(marker=marker):
                metadata = build_chapter_metadata(
                    config,
                    9,
                    {
                        "metadata": "chapter.json",
                        "text": "chapter.txt",
                        "msword": "chapter.docx",
                        "metadata_relative_path": Path("chapters/text_and_metadata/chapter.json"),
                        "text_relative_path": Path("chapters/text_and_metadata/chapter.txt"),
                        "msword_relative_path": Path("chapters/msword/chapter.docx"),
                        "full_msword_relative_path": Path("full_subject/full.docx"),
                        "full_text_relative_path": Path("full_subject/full.txt"),
                    },
                    f"।।{marker}।।\n\nया प्रकरणाचा सारांश येथे आहे.",
                    {},
                    "2026-07-08T00:00:00Z",
                    "python3 -m gurubodh prep-subject",
                )

                self.assertEqual(
                    metadata["content"]["automated_tags"],
                    ["summary_chapter", "उपसंहार"],
                )

    def test_chapter_metadata_keeps_automated_tags_empty_without_summary_marker(self):
        metadata = build_chapter_metadata(
            BASE_CONFIG,
            1,
            {
                "metadata": "chapter.json",
                "text": "chapter.txt",
                "msword": "chapter.docx",
                "metadata_relative_path": Path("chapters/text_and_metadata/chapter.json"),
                "text_relative_path": Path("chapters/text_and_metadata/chapter.txt"),
                "msword_relative_path": Path("chapters/msword/chapter.docx"),
                "full_msword_relative_path": Path("full_subject/full.docx"),
                "full_text_relative_path": Path("full_subject/full.txt"),
            },
            "श्री स्वामी समर्थ\n\nया प्रकरणात आचरणाचे विवेचन आहे.",
            {},
            "2026-07-08T00:00:00Z",
            "python3 -m gurubodh prep-subject",
        )

        self.assertEqual(metadata["content"]["automated_tags"], [])

    def test_chapter_metadata_uses_configured_summary_markers(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["metadata_defaults"] = {
            "summary_chapter_markers": ["समाप्ति-सूत्र"],
        }

        metadata = build_chapter_metadata(
            config,
            1,
            {
                "metadata": "chapter.json",
                "text": "chapter.txt",
                "msword": "chapter.docx",
                "metadata_relative_path": Path("chapters/text_and_metadata/chapter.json"),
                "text_relative_path": Path("chapters/text_and_metadata/chapter.txt"),
                "msword_relative_path": Path("chapters/msword/chapter.docx"),
                "full_msword_relative_path": Path("full_subject/full.docx"),
                "full_text_relative_path": Path("full_subject/full.txt"),
            },
            "यह समाप्ति-सूत्र प्रकरण का सारांश बताता है.",
            {},
            "2026-07-08T00:00:00Z",
            "python3 -m gurubodh prep-subject",
        )

        self.assertEqual(
            metadata["content"]["automated_tags"],
            ["summary_chapter", "उपसंहार"],
        )

    def test_chapter_metadata_omitted_summary_markers_disable_detection(self):
        metadata = build_chapter_metadata(
            BASE_CONFIG,
            1,
            {
                "metadata": "chapter.json",
                "text": "chapter.txt",
                "msword": "chapter.docx",
                "metadata_relative_path": Path("chapters/text_and_metadata/chapter.json"),
                "text_relative_path": Path("chapters/text_and_metadata/chapter.txt"),
                "msword_relative_path": Path("chapters/msword/chapter.docx"),
                "full_msword_relative_path": Path("full_subject/full.docx"),
                "full_text_relative_path": Path("full_subject/full.txt"),
            },
            "यह उपसंहार प्रकरण का सारांश बताता है.",
            {},
            "2026-07-08T00:00:00Z",
            "python3 -m gurubodh prep-subject",
        )

        self.assertEqual(metadata["content"]["automated_tags"], [])

    def test_chapter_metadata_configured_summary_markers_use_only_configured_terms(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["metadata_defaults"] = {
            "summary_chapter_markers": ["समाप्ति-सूत्र"],
        }

        metadata = build_chapter_metadata(
            config,
            1,
            {
                "metadata": "chapter.json",
                "text": "chapter.txt",
                "msword": "chapter.docx",
                "metadata_relative_path": Path("chapters/text_and_metadata/chapter.json"),
                "text_relative_path": Path("chapters/text_and_metadata/chapter.txt"),
                "msword_relative_path": Path("chapters/msword/chapter.docx"),
                "full_msword_relative_path": Path("full_subject/full.docx"),
                "full_text_relative_path": Path("full_subject/full.txt"),
            },
            "यह उपसंहार प्रकरण का सारांश बताता है.",
            {},
            "2026-07-08T00:00:00Z",
            "python3 -m gurubodh prep-subject",
        )

        self.assertEqual(metadata["content"]["automated_tags"], [])

    def test_chapter_metadata_honors_empty_summary_markers(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["metadata_defaults"] = {
            "summary_chapter_markers": [],
        }

        metadata = build_chapter_metadata(
            config,
            1,
            {
                "metadata": "chapter.json",
                "text": "chapter.txt",
                "msword": "chapter.docx",
                "metadata_relative_path": Path("chapters/text_and_metadata/chapter.json"),
                "text_relative_path": Path("chapters/text_and_metadata/chapter.txt"),
                "msword_relative_path": Path("chapters/msword/chapter.docx"),
                "full_msword_relative_path": Path("full_subject/full.docx"),
                "full_text_relative_path": Path("full_subject/full.txt"),
            },
            "यह उपसंहार प्रकरण का सारांश बताता है.",
            {},
            "2026-07-08T00:00:00Z",
            "python3 -m gurubodh prep-subject",
        )

        self.assertEqual(metadata["content"]["automated_tags"], [])

    def test_prep_subject_job_schema_defines_summary_chapter_markers(self):
        schema_path = Path(__file__).parents[1] / "config" / "jobs" / "prep_subject_job.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        markers_schema = schema["properties"]["metadata_defaults"]["properties"]["summary_chapter_markers"]

        self.assertEqual(markers_schema["type"], "array")
        self.assertEqual(markers_schema["items"]["type"], "string")
        self.assertNotIn("default", markers_schema)

    def test_load_prep_subject_job_accepts_summary_chapter_markers(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["metadata_defaults"] = {
            "summary_chapter_markers": ["समाप्ति-सूत्र"],
        }

        loaded = load_prep_subject_job(self.write_config(config))

        self.assertEqual(
            loaded["metadata_defaults"]["summary_chapter_markers"],
            ["समाप्ति-सूत्र"],
        )

    def test_sample_jobs_declare_summary_chapter_markers(self):
        jobs_dir = Path(__file__).parents[1] / "jobs" / "subjects"

        for job_path in jobs_dir.glob("*/prep-subject*.json"):
            with self.subTest(job=str(job_path.relative_to(jobs_dir))):
                config = load_prep_subject_job(job_path)

                self.assertIn("summary_chapter_markers", config["metadata_defaults"])

    def test_sample_generate_chunks_jobs_load(self):
        jobs_dir = Path(__file__).parents[1] / "jobs" / "subjects"

        for job_path in jobs_dir.glob("*/generate-chunks*.json"):
            with self.subTest(job=str(job_path.relative_to(jobs_dir))):
                config = load_generate_chunks_job(job_path)

                self.assertEqual(config["pipeline"], "generate-chunks")
                self.assertEqual(config["_semantic_chunk_config"].model_name, "BAAI/bge-m3")
                self.assertRegex(config["_semantic_chunk_config"].model_revision, r"^[0-9a-f]{40}$")
                self.assertGreaterEqual(config["_semantic_chunk_config"].threshold_percentile, 0.0)
                self.assertLessEqual(config["_semantic_chunk_config"].threshold_percentile, 100.0)
                self.assertGreaterEqual(config["_semantic_chunk_config"].min_chars, 0)

    def test_generate_chunks_job_rejects_unpinned_model_revision(self):
        config = {
            "schema_version": "1.0.0",
            "pipeline": "generate-chunks",
            "source": {"backend": "r2", "bucket": "source", "prefix": "cms_library", "subject_dir": "123_spand_rahasya", "url_base": None},
            "destination": {"backend": "r2", "bucket": "destination", "prefix": "cms_library", "subject_dir": "123_spand_rahasya", "url_base": None},
            "naming": {"category_code": "CAT001", "subject_code": "SUB123", "title_slug": "spand-rahasya", "version": "01", "subversion": "01"},
            "chunking": {"provider": "semantic-chunking", "model": "BAAI/bge-m3", "model_revision": None, "embedding_mode": "dense", "embedding_dimension": 1024, "threshold_percentile": 80.0, "min_chars": 600, "window_size": 3, "batch_size": 16, "normalize_embeddings": True, "device": None, "local_files_only": False},
        }

        with self.assertRaisesRegex(SystemExit, "chunking.model_revision must be a non-empty string"):
            load_generate_chunks_job(self.write_config(config))

    def test_load_prep_subject_job_rejects_invalid_summary_chapter_markers(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["metadata_defaults"] = {
            "summary_chapter_markers": "उपसंहार",
        }

        with self.assertRaises(SystemExit) as exc:
            load_prep_subject_job(self.write_config(config))

        self.assertIn(
            "metadata_defaults.summary_chapter_markers must be an array of strings",
            str(exc.exception),
        )

    def test_text_artifact_integrity_changes_when_text_changes(self):
        original = text_artifact_integrity("प्रबोधन")
        changed = text_artifact_integrity("प्रबोधन बदलले")

        self.assertNotEqual(
            original["artifacts"]["text"]["value"],
            changed["artifacts"]["text"]["value"],
        )

    def test_text_artifact_integrity_is_stable_across_storage_backends(self):
        text = "एकच मजकूर"
        local_config = json.loads(json.dumps(BASE_CONFIG))
        r2_config = json.loads(json.dumps(BASE_CONFIG))
        r2_config["destination"] = {
            "backend": "r2",
            "bucket": "gurubodh-library-dev",
            "prefix": "cms_library",
            "subject_dir": "129_spand_rahasya",
            "url_base": None,
        }
        file_names = {
            "metadata": "chapter.json",
            "text": "chapter.txt",
            "msword": "chapter.docx",
            "metadata_relative_path": Path("chapters/text_and_metadata/chapter.json"),
            "text_relative_path": Path("chapters/text_and_metadata/chapter.txt"),
            "msword_relative_path": Path("chapters/msword/chapter.docx"),
            "full_msword_relative_path": Path("full_subject/full.docx"),
            "full_text_relative_path": Path("full_subject/full.txt"),
        }

        local_metadata = build_chapter_metadata(
            local_config,
            1,
            file_names,
            text,
            {},
            "2026-07-08T00:00:00Z",
            "python3 -m gurubodh prep-subject",
        )
        r2_metadata = build_chapter_metadata(
            r2_config,
            1,
            file_names,
            text,
            {},
            "2026-07-08T00:00:00Z",
            "python3 -m gurubodh prep-subject",
        )

        self.assertEqual(local_metadata["integrity"], r2_metadata["integrity"])

    def test_chapter_metadata_schema_requires_text_integrity_shape(self):
        schema_path = Path(__file__).parents[1] / "config" / "artifacts" / "chapter_metadata.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        self.assertIn("integrity", schema["required"])
        text_schema = schema["properties"]["integrity"]["properties"]["artifacts"]["properties"]["text"]
        self.assertEqual(
            text_schema["required"],
            ["algorithm", "encoding", "line_endings", "scope", "value"],
        )
        self.assertEqual(text_schema["properties"]["algorithm"]["const"], "sha256")
        self.assertEqual(text_schema["properties"]["encoding"]["const"], "UTF-8")
        self.assertEqual(text_schema["properties"]["line_endings"]["const"], "LF")
        self.assertEqual(text_schema["properties"]["scope"]["const"], "artifact-bytes")
        self.assertEqual(text_schema["properties"]["value"]["pattern"], "^[a-f0-9]{64}$")

    def test_r2_source_materializes_to_temporary_docx(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["source"] = {
            "backend": "r2",
            "bucket": "gurubodh-library-dev",
            "key": "source_library/129_spand_rahasya/source.docx",
            "font_encoding": "unicode",
            "file_format": "docx",
        }
        client = FakeR2Client()

        with redirect_stdout(StringIO()):
            path, temp_dir = materialize_source(config, r2_client=client)
        self.addCleanup(temp_dir.cleanup)

        self.assertEqual(path.name, "source.docx")
        self.assertTrue(path.exists())
        self.assertEqual(
            client.download,
            (
                "gurubodh-library-dev",
                "source_library/129_spand_rahasya/source.docx",
                "source.docx",
            ),
        )

    def test_r2_source_download_404_has_clear_error(self):
        client = R2StorageClient.__new__(R2StorageClient)
        client._client_error = ClientError
        client.client = FakeMissingR2ObjectClient()

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(SystemExit) as exc:
                client.download_file(
                    "gurubodh-library-dev",
                    "source_library/123_spand_rahasya/source.docx",
                    Path(temp_dir) / "source.docx",
                )

        self.assertIn("R2 source object does not exist", str(exc.exception))
        self.assertIn(
            "r2://gurubodh-library-dev/source_library/123_spand_rahasya/source.docx",
            str(exc.exception),
        )

    def test_r2_publish_fails_existing_object_without_overwrite(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["destination"] = {
            "backend": "r2",
            "bucket": "gurubodh-library-dev",
            "prefix": "cms_library",
            "subject_dir": "129_spand_rahasya",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            subject_dir = Path(temp_dir) / "129_spand_rahasya"
            output_file = subject_dir / "full_subject" / "full.txt"
            output_file.parent.mkdir(parents=True)
            output_file.write_text("content", encoding="utf-8")
            client = FakeR2Client({"cms_library/129_spand_rahasya/full_subject/full.txt"})

            with redirect_stdout(StringIO()):
                with self.assertRaises(SystemExit):
                    publish_r2_destination(config, subject_dir, overwrite=False, r2_client=client)

            self.assertEqual(client.uploads, [])

    def test_r2_preflight_fails_existing_prefix_without_overwrite(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["destination"] = {
            "backend": "r2",
            "bucket": "gurubodh-library-dev",
            "prefix": "cms_library",
            "subject_dir": "129_spand_rahasya",
        }
        client = FakeR2Client({"cms_library/129_spand_rahasya/full_subject/full.txt"})

        with redirect_stdout(StringIO()):
            with self.assertRaises(SystemExit) as error:
                ensure_r2_destination_available(config, overwrite=False, r2_client=client)

        message = str(error.exception)
        self.assertIn("R2 destination already contains prep-subject artifact locations.", message)
        self.assertIn("- r2://gurubodh-library-dev/cms_library/129_spand_rahasya/full_subject/", message)
        self.assertIn("contents of these locations will be replaced and existing semantic chunk artifacts will be invalidated.", message)
        self.assertIn("Audit history will be preserved. Unrelated subject files will be preserved.", message)
        self.assertIn("Run gurubodh generate-chunks --config <generate-chunks-job> before relying on RAG/chunk outputs.", message)
        self.assertEqual(message.count("R2 destination already contains"), 1)
        self.assertEqual(client.prefix_check, ("gurubodh-library-dev", "cms_library/129_spand_rahasya/chapters/chapter_content_manifest.json"))

    def test_r2_preflight_marks_destructive_replacement_pending_with_overwrite(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["destination"] = {
            "backend": "r2",
            "bucket": "gurubodh-library-dev",
            "prefix": "cms_library",
            "subject_dir": "129_spand_rahasya",
        }
        client = FakeR2Client({"cms_library/129_spand_rahasya/full_subject/full.txt"})

        preflight = ensure_r2_destination_available(config, overwrite=True, r2_client=client)

        self.assertFalse(hasattr(client, "prefix_check"))
        self.assertEqual(preflight["status"], "destructive_replacement_pending")

    def test_r2_publish_overwrite_removes_stale_subject_objects_and_preserves_siblings(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["destination"] = {
            "backend": "r2",
            "bucket": "gurubodh-library-dev",
            "prefix": "cms_library",
            "subject_dir": "129_spand_rahasya",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            subject_dir = Path(temp_dir) / "129_spand_rahasya"
            output_file = subject_dir / "full_subject" / "full.txt"
            output_file.parent.mkdir(parents=True)
            output_file.write_text("content", encoding="utf-8")
            client = FakeR2Client(
                {
                    "cms_library/129_spand_rahasya/full_subject/full.txt",
                    "cms_library/129_spand_rahasya/chapters/stale.txt",
                    "cms_library/130_other_subject/full_subject/keep.txt",
                }
            )

            output = StringIO()
            with redirect_stdout(output):
                publish_r2_destination(config, subject_dir, overwrite=True, r2_client=client)

            progress = output.getvalue()
            self.assertIn("prepared 1 artifact file(s) for R2 upload", progress)
            self.assertIn("deleted 1 object(s) from prep-subject-owned R2 paths", progress)
            self.assertIn("[1/1] full subject: full (text)", progress)
            self.assertEqual(client.deleted_prefix, ("gurubodh-library-dev", "cms_library/129_spand_rahasya/chapters/chapter_content_manifest.json"))
            self.assertEqual(
                client.existing_keys,
                {
                    "cms_library/129_spand_rahasya/full_subject/full.txt",
                    "cms_library/129_spand_rahasya/chapters/stale.txt",
                    "cms_library/130_other_subject/full_subject/keep.txt",
                },
            )
            self.assertEqual(
                client.uploads,
                [
                    (
                        "full.txt",
                        "gurubodh-library-dev",
                        "cms_library/129_spand_rahasya/full_subject/full.txt",
                    )
                ],
            )

    def test_r2_prep_upload_reports_chapter_progress_and_keeps_chapter_files_together(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["destination"] = {
            "backend": "r2",
            "bucket": "gurubodh-library-dev",
            "prefix": "cms_library",
            "subject_dir": "129_spand_rahasya",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            subject_dir = Path(temp_dir) / "129_spand_rahasya"
            for chapter in ("001", "002"):
                stem = f"CAT020_SUB129_spand-rahasya_{chapter}_v01.01"
                for directory, suffix in (("chapters/msword", ".docx"), ("chapters/text_and_metadata", ".txt"), ("chapters/text_and_metadata", ".json")):
                    path = subject_dir / directory / f"{stem}{suffix}"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("artifact", encoding="utf-8")
            manifest = subject_dir / "chapters" / "chapter_content_manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            client = FakeR2Client()

            output = StringIO()
            with redirect_stdout(output):
                publish_r2_destination(config, subject_dir, overwrite=False, r2_client=client)

            progress = output.getvalue()
            self.assertIn("[1/2] chapter artifacts: 2 chapters / 6 files", progress)
            self.assertIn("[01/02] CAT020_SUB129_spand-rahasya_001_v01.01 (DOCX, text, metadata)", progress)
            self.assertIn("[02/02] CAT020_SUB129_spand-rahasya_002_v01.01 (DOCX, text, metadata)", progress)
            self.assertIn("[2/2] content manifest: chapters/chapter_content_manifest.json", progress)
            uploaded_names = [name for name, _, _ in client.uploads]
            self.assertEqual(uploaded_names[:3], [
                "CAT020_SUB129_spand-rahasya_001_v01.01.docx",
                "CAT020_SUB129_spand-rahasya_001_v01.01.txt",
                "CAT020_SUB129_spand-rahasya_001_v01.01.json",
            ])


if __name__ == "__main__":
    unittest.main()
