import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from botocore.exceptions import ClientError

from gurubodh_utils.config import load_conversion_job
from gurubodh_utils.metadata import build_chapter_metadata
from gurubodh_utils.storage import (
    R2StorageClient,
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
