import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from botocore.exceptions import ClientError

from gurubodh_utils.cli import main as cli_main
from gurubodh_utils.config import load_conversion_job
from gurubodh_utils.constants import DEFAULT_FORMATTING_CONFIG
from gurubodh_utils.metadata import (
    build_chapter_metadata,
    source_text_sha256,
    text_artifact_integrity,
)
from gurubodh_utils.storage import (
    R2StorageClient,
    ensure_r2_destination_available,
    materialize_source,
    publish_r2_destination,
)


BASE_CONFIG = {
    "schema_version": "1.3.0",
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
        config = load_conversion_job(self.write_config(BASE_CONFIG))

        self.assertEqual(config["source"]["relative_path"], "subject/source.docx")
        self.assertEqual(config["destination"]["subject_dir"], "129_spand_rahasya")

    def test_omitted_formatting_defaults_to_disabled(self):
        config = load_conversion_job(self.write_config(BASE_CONFIG))

        self.assertEqual(config["formatting"], DEFAULT_FORMATTING_CONFIG)
        self.assertFalse(config["formatting"]["enabled"])

    def test_disabled_formatting_block_receives_defaults(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["formatting"] = {"enabled": False}

        loaded = load_conversion_job(self.write_config(config))

        self.assertEqual(loaded["formatting"], DEFAULT_FORMATTING_CONFIG)

    def test_enabled_sarvam_formatting_shape_loads(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["formatting"] = {
            "enabled": True,
            "provider": "sarvam",
            "model": "sarvam-30b",
            "fallback_model": "sarvam-105b",
            "output_formats": ["json", "markdown"],
            "continue_on_error": True,
            "delay_seconds": 5,
            "max_retries": 3,
            "regenerate": "when-source-checksum-changes",
        }

        loaded = load_conversion_job(self.write_config(config))

        self.assertTrue(loaded["formatting"]["enabled"])
        self.assertEqual(loaded["formatting"]["model"], "sarvam-30b")
        self.assertEqual(loaded["formatting"]["fallback_model"], "sarvam-105b")

    def test_formatting_rejects_invalid_provider(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["formatting"] = {"enabled": True, "provider": "other"}

        with self.assertRaises(SystemExit) as exc:
            load_conversion_job(self.write_config(config))

        self.assertIn("formatting.provider", str(exc.exception))

    def test_formatting_rejects_non_boolean_enabled(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["formatting"] = {"enabled": "yes"}

        with self.assertRaises(SystemExit) as exc:
            load_conversion_job(self.write_config(config))

        self.assertIn("formatting.enabled", str(exc.exception))

    def test_formatting_rejects_invalid_model_name(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["formatting"] = {"enabled": True, "model": "not-a-sarvam-model"}

        with self.assertRaises(SystemExit) as exc:
            load_conversion_job(self.write_config(config))

        self.assertIn("formatting.model", str(exc.exception))

    def test_formatting_rejects_invalid_output_format(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["formatting"] = {"enabled": True, "output_formats": ["json", "html"]}

        with self.assertRaises(SystemExit) as exc:
            load_conversion_job(self.write_config(config))

        self.assertIn("formatting.output_formats", str(exc.exception))

    def test_formatting_rejects_invalid_retry_values(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["formatting"] = {"enabled": True, "max_retries": 99}

        with self.assertRaises(SystemExit) as exc:
            load_conversion_job(self.write_config(config))

        self.assertIn("formatting.max_retries", str(exc.exception))

    def test_formatting_rejects_invalid_regeneration_mode(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["formatting"] = {"enabled": True, "regenerate": "always"}

        with self.assertRaises(SystemExit) as exc:
            load_conversion_job(self.write_config(config))

        self.assertIn("formatting.regenerate", str(exc.exception))

    def test_conversion_job_schema_declares_formatting_contract(self):
        schema_path = Path(__file__).parents[1] / "config" / "conversion_job.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        formatting = schema["properties"]["formatting"]["properties"]

        self.assertEqual(schema["properties"]["schema_version"]["const"], "1.3.0")
        self.assertEqual(formatting["provider"]["const"], "sarvam")
        self.assertEqual(formatting["model"]["default"], "sarvam-30b")
        self.assertEqual(formatting["fallback_model"]["default"], "sarvam-105b")
        self.assertEqual(formatting["output_formats"]["items"]["enum"], ["json", "markdown"])
        self.assertEqual(formatting["continue_on_error"]["default"], True)
        self.assertEqual(formatting["delay_seconds"]["default"], 5)
        self.assertEqual(formatting["max_retries"]["default"], 3)
        self.assertEqual(formatting["regenerate"]["const"], "when-source-checksum-changes")

    def test_migrate_configs_preview_reports_without_writing(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "job.json"
        original = '{\n  "schema_version": "1.2.0",\n  "pipeline": "unicode-docx-ingest"\n}\n'
        path.write_text(original, encoding="utf-8")
        stdout = StringIO()

        with redirect_stdout(stdout):
            cli_main([
                "migrate-configs",
                "--project-root",
                str(Path(__file__).parents[1]),
                str(path),
            ])

        self.assertIn("would-migrate", stdout.getvalue())
        self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_migrate_configs_apply_updates_only_schema_version(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "job.json"
        path.write_text(
            '{\n'
            '  "schema_version": "1.2.0",\n'
            '  "pipeline": "unicode-docx-ingest",\n'
            '  "description": "spacing is preserved"\n'
            '}\n',
            encoding="utf-8",
        )
        stdout = StringIO()

        with redirect_stdout(stdout):
            cli_main([
                "migrate-configs",
                "--project-root",
                str(Path(__file__).parents[1]),
                "--apply",
                str(path),
            ])

        self.assertIn("migrated", stdout.getvalue())
        self.assertEqual(
            path.read_text(encoding="utf-8"),
            '{\n'
            '  "schema_version": "1.3.0",\n'
            '  "pipeline": "unicode-docx-ingest",\n'
            '  "description": "spacing is preserved"\n'
            '}\n',
        )

    def test_migrate_configs_refuses_unsupported_schema_version(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "job.json"
        path.write_text('{"schema_version": "0.9.0"}', encoding="utf-8")

        with self.assertRaises(SystemExit) as exc:
            cli_main([
                "migrate-configs",
                "--project-root",
                str(Path(__file__).parents[1]),
                str(path),
            ])

        self.assertIn("unsupported schema_version", str(exc.exception))

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

        loaded = load_conversion_job(self.write_config(config))

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
            "python3 -m gurubodh_utils run",
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
            "python3 -m gurubodh_utils run",
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

    def test_chapter_metadata_records_disabled_formatting_without_formatted_artifacts(self):
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
            "प्रबोधन",
            {},
            "2026-07-08T00:00:00Z",
            "python3 -m gurubodh_utils run",
        )

        self.assertEqual(metadata["schema_version"], "1.3.0")
        self.assertEqual(
            metadata["formatting"],
            {
                "enabled": False,
                "provider": "sarvam",
                "model": "sarvam-30b",
                "fallback_model": "sarvam-105b",
                "model_used": None,
                "status": "disabled",
                "warning": None,
                "source_text_sha256": None,
            },
        )
        self.assertNotIn("formatted_json_filename", metadata["files"])
        self.assertNotIn("formatted_json", metadata["storage"]["artifacts"])
        self.assertNotIn("formatted_json", metadata["integrity"]["artifacts"])

    def test_chapter_metadata_records_successful_formatted_artifacts(self):
        text = "पहला वाक्य दूसरा वाक्य"
        config = json.loads(json.dumps(BASE_CONFIG))
        config["formatting"] = {
            "enabled": True,
            "provider": "sarvam",
            "model": "sarvam-30b",
            "fallback_model": "sarvam-105b",
            "output_formats": ["json", "markdown"],
            "continue_on_error": True,
            "delay_seconds": 0,
            "max_retries": 0,
            "regenerate": "when-source-checksum-changes",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            subject_dir = Path(temp_dir) / "129_spand_rahasya"
            artifact_dir = subject_dir / "chapters" / "text_and_metadata"
            artifact_dir.mkdir(parents=True)
            formatted_json_path = artifact_dir / "chapter.formatted.json"
            formatted_markdown_path = artifact_dir / "chapter.formatted.md"
            formatted_json = '{"paragraphs": ["पहला।"]}\n'
            formatted_markdown = "पहला।\n"
            formatted_json_path.write_text(formatted_json, encoding="utf-8")
            formatted_markdown_path.write_text(formatted_markdown, encoding="utf-8")
            expected_json_digest = hashlib.sha256(formatted_json.encode("utf-8")).hexdigest()
            expected_markdown_digest = hashlib.sha256(
                formatted_markdown.encode("utf-8")
            ).hexdigest()

            metadata = build_chapter_metadata(
                config,
                1,
                {
                    "metadata": "chapter.json",
                    "text": "chapter.txt",
                    "msword": "chapter.docx",
                    "formatted_json": "chapter.formatted.json",
                    "formatted_markdown": "chapter.formatted.md",
                    "metadata_relative_path": Path("chapters/text_and_metadata/chapter.json"),
                    "text_relative_path": Path("chapters/text_and_metadata/chapter.txt"),
                    "msword_relative_path": Path("chapters/msword/chapter.docx"),
                    "full_msword_relative_path": Path("full_subject/full.docx"),
                    "full_text_relative_path": Path("full_subject/full.txt"),
                    "formatted_json_relative_path": Path(
                        "chapters/text_and_metadata/chapter.formatted.json"
                    ),
                    "formatted_markdown_relative_path": Path(
                        "chapters/text_and_metadata/chapter.formatted.md"
                    ),
                    "formatted_json_path": formatted_json_path,
                    "formatted_markdown_path": formatted_markdown_path,
                },
                text,
                {},
                "2026-07-08T00:00:00Z",
                "python3 -m gurubodh_utils run",
                {"status": "formatted", "warning": None, "artifacts": {}},
            )

        self.assertEqual(metadata["files"]["formatted_json_filename"], "chapter.formatted.json")
        self.assertEqual(metadata["files"]["formatted_markdown_filename"], "chapter.formatted.md")
        self.assertEqual(
            metadata["storage"]["artifacts"]["formatted_json"]["path"],
            "chapters/text_and_metadata/chapter.formatted.json",
        )
        self.assertEqual(
            metadata["storage"]["artifacts"]["formatted_markdown"]["path"],
            "chapters/text_and_metadata/chapter.formatted.md",
        )
        self.assertEqual(
            metadata["integrity"]["artifacts"]["formatted_json"]["value"],
            expected_json_digest,
        )
        self.assertEqual(
            metadata["integrity"]["artifacts"]["formatted_markdown"]["value"],
            expected_markdown_digest,
        )
        self.assertEqual(
            metadata["formatting"],
            {
                "enabled": True,
                "provider": "sarvam",
                "model": "sarvam-30b",
                "fallback_model": "sarvam-105b",
                "model_used": "sarvam-30b",
                "status": "formatted",
                "warning": None,
                "source_text_sha256": source_text_sha256(text),
            },
        )

    def test_chapter_metadata_records_failed_formatting_without_display_artifacts(self):
        text = "प्रबोधन"
        config = json.loads(json.dumps(BASE_CONFIG))
        config["formatting"] = {"enabled": True}

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
            text,
            {},
            "2026-07-08T00:00:00Z",
            "python3 -m gurubodh_utils run",
            {
                "status": "failed",
                "warning": "formatting failed for chapter 001 chapter: rate limit",
                "artifacts": {},
            },
        )

        self.assertEqual(metadata["formatting"]["status"], "failed")
        self.assertEqual(metadata["formatting"]["source_text_sha256"], source_text_sha256(text))
        self.assertNotIn("formatted_markdown_filename", metadata["files"])
        self.assertNotIn("formatted_markdown", metadata["storage"]["artifacts"])
        self.assertNotIn("formatted_markdown", metadata["integrity"]["artifacts"])

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
            "python3 -m gurubodh_utils run",
        )
        r2_metadata = build_chapter_metadata(
            r2_config,
            1,
            file_names,
            text,
            {},
            "2026-07-08T00:00:00Z",
            "python3 -m gurubodh_utils run",
        )

        self.assertEqual(local_metadata["integrity"], r2_metadata["integrity"])

    def test_chapter_metadata_schema_requires_text_integrity_shape(self):
        schema_path = Path(__file__).parents[1] / "config" / "chapter_metadata.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        self.assertEqual(schema["properties"]["schema_version"]["const"], "1.3.0")
        self.assertIn("integrity", schema["required"])
        self.assertIn("formatting", schema["required"])
        files = schema["properties"]["files"]["properties"]
        storage_artifacts = schema["properties"]["storage"]["properties"]["artifacts"]["properties"]
        integrity_artifacts = schema["properties"]["integrity"]["properties"]["artifacts"]["properties"]
        formatting = schema["properties"]["formatting"]["properties"]
        text_schema = schema["$defs"]["artifact_integrity"]

        self.assertIn("formatted_json_filename", files)
        self.assertIn("formatted_markdown_filename", files)
        self.assertIn("formatted_json", storage_artifacts)
        self.assertIn("formatted_markdown", storage_artifacts)
        self.assertEqual(integrity_artifacts["text"]["$ref"], "#/$defs/artifact_integrity")
        self.assertEqual(
            integrity_artifacts["formatted_json"]["$ref"],
            "#/$defs/artifact_integrity",
        )
        self.assertEqual(
            formatting["status"]["enum"],
            ["disabled", "formatted", "skipped-unchanged", "failed"],
        )
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
            with self.assertRaises(SystemExit):
                ensure_r2_destination_available(config, overwrite=False, r2_client=client)

        self.assertEqual(
            client.prefix_check,
            ("gurubodh-library-dev", "cms_library/129_spand_rahasya/"),
        )

    def test_r2_preflight_skips_prefix_check_with_overwrite(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["destination"] = {
            "backend": "r2",
            "bucket": "gurubodh-library-dev",
            "prefix": "cms_library",
            "subject_dir": "129_spand_rahasya",
        }
        client = FakeR2Client({"cms_library/129_spand_rahasya/full_subject/full.txt"})

        ensure_r2_destination_available(config, overwrite=True, r2_client=client)

        self.assertFalse(hasattr(client, "prefix_check"))

    def test_r2_publish_uploads_with_overwrite(self):
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

            output = StringIO()
            with redirect_stdout(output):
                publish_r2_destination(config, subject_dir, overwrite=True, r2_client=client)

            progress = output.getvalue()
            self.assertIn("prepared 1 artifact file(s) for R2 upload", progress)
            self.assertIn("[1/1] checking cms_library/129_spand_rahasya/full_subject/full.txt", progress)
            self.assertIn("[1/1] uploading cms_library/129_spand_rahasya/full_subject/full.txt", progress)
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


if __name__ == "__main__":
    unittest.main()
