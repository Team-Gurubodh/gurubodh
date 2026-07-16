import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from gurubodh_utils.retry_formatting import retry_formatting
from gurubodh_utils.formatting import source_text_sha256


FORMATTING_CONFIG = {
    "enabled": True,
    "provider": "sarvam",
    "model": "sarvam-30b",
    "fallback_model": "sarvam-105b",
    "output_formats": ["json", "markdown"],
    "continue_on_error": True,
    "delay_seconds": 0,
    "max_retries": 0,
    "regenerate": "when-source-checksum-changes",
    "reasoning_effort": None,
    "max_tokens": 4096,
}


R2_CONFIG = {
    "schema_version": "1.3.0",
    "pipeline": "unicode-docx-ingest",
    "source": {
        "root_dir": "/tmp/source",
        "relative_path": "subject/source.docx",
        "font_encoding": "unicode",
        "file_format": "docx",
    },
    "destination": {
        "backend": "r2",
        "bucket": "gurubodh-library-dev",
        "prefix": "cms_library",
        "subject_dir": "129_spand_rahasya",
        "url_base": None,
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
    "formatting": FORMATTING_CONFIG,
}


PREFIX = "cms_library/129_spand_rahasya/chapters/text_and_metadata"


class FakeR2Client:
    def __init__(self, objects):
        self.objects = dict(objects)
        self.puts = []

    def list_keys(self, bucket, prefix):
        return sorted(key for key in self.objects if key.startswith(prefix))

    def get_object_bytes(self, bucket, key):
        if key not in self.objects:
            raise FileNotFoundError(key)
        return self.objects[key]

    def put_object_bytes(self, bucket, key, data):
        self.puts.append((bucket, key, data))
        self.objects[key] = data


class FakeFormatter:
    def __init__(self, result=None, error=None, token_usage=None):
        self.result = result
        self.error = error
        self.request_attempt_count = 0
        self.retry_count = 0
        self.throttle_sleep_seconds = 0
        self.last_token_usage = token_usage
        self.calls = []

    def format_text(self, text, progress_label=None):
        self.calls.append((text, progress_label))
        self.request_attempt_count += 1
        if self.error:
            raise self.error
        return self.result


class RecordingReporter:
    def __init__(self):
        self.messages = []

    def report(self, message):
        self.messages.append(message)


def object_key(chapter, suffix):
    base = f"CAT020_SUB129_spand-rahasya_{chapter}_v01.01"
    return f"{PREFIX}/{base}{suffix}"


def metadata_for(chapter, status="failed", retry_attempts=0, enabled=True, warning="failed"):
    text_key = object_key(chapter, ".txt")
    text_name = text_key.rsplit("/", 1)[1]
    metadata_key = object_key(chapter, ".json")
    return {
        "schema_version": "1.3.0",
        "document": {
            "category_code": "CAT020",
            "subject_code": "SUB129",
            "title_slug": "spand-rahasya",
            "chapter_number": chapter,
            "version": "v01.01",
            "language": "hi-Deva",
        },
        "files": {
            "metadata_filename": metadata_key.rsplit("/", 1)[1],
            "text_filename": text_name,
            "msword_filename": text_name.replace(".txt", ".docx"),
        },
        "storage": {
            "source": {"backend": "local", "path": "source.docx", "url": None},
            "artifacts": {
                "metadata": {
                    "backend": "r2",
                    "bucket": "gurubodh-library-dev",
                    "key": metadata_key,
                    "url": None,
                },
                "text": {
                    "backend": "r2",
                    "bucket": "gurubodh-library-dev",
                    "key": text_key,
                    "url": None,
                },
            },
        },
        "integrity": {"artifacts": {}},
        "formatting": {
            "enabled": enabled,
            "provider": "sarvam",
            "model": "sarvam-30b",
            "fallback_model": "sarvam-105b",
            "model_used": None,
            "status": status,
            "warning": warning,
            "attempt_count": 1,
            "retry_count": 0,
            "retry_attempts": retry_attempts,
            "throttle_sleep_seconds": 0,
            "source_text_sha256": None,
            "token_usage": {
                "completion_tokens": None,
                "prompt_tokens": None,
                "total_tokens": None,
            },
        },
    }


def json_object(data):
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def r2_objects(*chapters):
    objects = {}
    for chapter, metadata, text in chapters:
        objects[object_key(chapter, ".json")] = json_object(metadata)
        objects[object_key(chapter, ".txt")] = (text + "\n").encode("utf-8")
    return objects


class RetryFormattingTests(unittest.TestCase):
    def test_dry_run_selects_failed_below_cap_and_reports_exhausted(self):
        objects = r2_objects(
            ("001", metadata_for("001", retry_attempts=0), "पहला पाठ"),
            ("002", metadata_for("002", retry_attempts=3), "दूसरा पाठ"),
            ("003", metadata_for("003", status="formatted", warning=None), "तीसरा पाठ"),
            ("004", metadata_for("004", enabled=False, status="disabled", warning=None), "चौथा पाठ"),
        )
        client = FakeR2Client(objects)
        output = StringIO()

        with redirect_stdout(output):
            result = retry_formatting(R2_CONFIG, dry_run=True, r2_client=client)

        self.assertEqual([record["status"] for record in result["records"]], [
            "selected",
            "retry-exhausted",
            "skipped",
            "skipped",
        ])
        self.assertIn("selected=1 skipped=2 retry_exhausted=1", output.getvalue())
        self.assertEqual(client.puts, [])

    def test_successful_retry_uploads_formatted_artifacts_and_metadata(self):
        text = "पहला पाठ"
        objects = r2_objects(("001", metadata_for("001", retry_attempts=0), text))
        client = FakeR2Client(objects)
        reporter = RecordingReporter()
        formatter = FakeFormatter(
            result={
                "schema_version": "1.0.0",
                "provider": "sarvam",
                "model": "sarvam-30b",
                "fallback_model_used": None,
                "source_text_sha256": source_text_sha256(text),
                "status": "formatted",
                "paragraphs": ["पहला पाठ।"],
                "token_usage": {
                    "completion_tokens": 5,
                    "prompt_tokens": 7,
                    "total_tokens": 12,
                },
            }
        )

        with redirect_stdout(StringIO()):
            retry_formatting(
                R2_CONFIG,
                r2_client=client,
                formatter=formatter,
                reporter=reporter,
            )

        metadata = json.loads(client.objects[object_key("001", ".json")].decode("utf-8"))
        self.assertIn(
            "listing R2 chapter metadata under r2://gurubodh-library-dev/cms_library/129_spand_rahasya/chapters/text_and_metadata/",
            reporter.messages,
        )
        self.assertIn("retry-formatting selection: selected=1 skipped=0 retry_exhausted=0", reporter.messages)
        self.assertIn("[1/1] processing chapter 001", reporter.messages)
        self.assertIn("[001] downloading raw text artifact", reporter.messages)
        self.assertIn("[001] retrying formatting attempt 1", reporter.messages)
        self.assertTrue(
            any(message.startswith("[001] uploading formatted json bytes=") for message in reporter.messages)
        )
        self.assertIn("[001] uploading updated metadata", reporter.messages)
        self.assertIn("[001] retry formatting succeeded", reporter.messages)
        self.assertEqual(formatter.calls, [(text, "[001]")])
        self.assertEqual(metadata["formatting"]["status"], "formatted")
        self.assertEqual(metadata["formatting"]["retry_attempts"], 1)
        self.assertEqual(metadata["formatting"]["attempt_count"], 1)
        self.assertIsNone(metadata["formatting"]["warning"])
        self.assertEqual(metadata["formatting"]["token_usage"]["total_tokens"], 12)
        self.assertIn("formatted_json_filename", metadata["files"])
        self.assertIn("formatted_markdown_filename", metadata["files"])
        self.assertIn(object_key("001", ".formatted.json"), client.objects)
        self.assertIn(object_key("001", ".formatted.md"), client.objects)
        self.assertNotIn(
            "token_usage",
            json.loads(client.objects[object_key("001", ".formatted.json")].decode("utf-8")),
        )

    def test_failed_retry_increments_retry_attempts_and_writes_only_metadata(self):
        objects = r2_objects(("002", metadata_for("002", retry_attempts=2), "दूसरा पाठ"))
        client = FakeR2Client(objects)
        formatter = FakeFormatter(
            error=RuntimeError("Sarvam response stopped with finish_reason='length'"),
            token_usage={
                "completion_tokens": 4096,
                "prompt_tokens": 10,
                "total_tokens": 4106,
            },
        )

        with redirect_stdout(StringIO()):
            retry_formatting(R2_CONFIG, r2_client=client, formatter=formatter)

        metadata = json.loads(client.objects[object_key("002", ".json")].decode("utf-8"))
        self.assertEqual(metadata["formatting"]["status"], "failed")
        self.assertEqual(metadata["formatting"]["retry_attempts"], 3)
        self.assertIn("finish_reason='length'", metadata["formatting"]["warning"])
        self.assertEqual(metadata["formatting"]["token_usage"]["completion_tokens"], 4096)
        self.assertNotIn(object_key("002", ".formatted.json"), client.objects)
        self.assertNotIn(object_key("002", ".formatted.md"), client.objects)

    def test_retry_exhausted_chapter_is_not_retried(self):
        objects = r2_objects(("003", metadata_for("003", retry_attempts=3), "तीसरा पाठ"))
        client = FakeR2Client(objects)
        formatter = FakeFormatter(error=AssertionError("formatter should not be called"))

        with redirect_stdout(StringIO()):
            retry_formatting(R2_CONFIG, r2_client=client, formatter=formatter)

        metadata = json.loads(client.objects[object_key("003", ".json")].decode("utf-8"))
        self.assertEqual(formatter.calls, [])
        self.assertEqual(metadata["formatting"]["status"], "failed")
        self.assertEqual(metadata["formatting"]["retry_attempts"], 3)
        self.assertEqual(client.puts, [])

    def test_missing_retry_attempts_is_treated_as_zero(self):
        metadata = metadata_for("004")
        metadata["formatting"].pop("retry_attempts")
        text = "चौथा पाठ"
        objects = r2_objects(("004", metadata, text))
        client = FakeR2Client(objects)
        formatter = FakeFormatter(
            result={
                "schema_version": "1.0.0",
                "provider": "sarvam",
                "model": "sarvam-30b",
                "fallback_model_used": None,
                "source_text_sha256": source_text_sha256(text),
                "status": "formatted",
                "paragraphs": ["चौथा पाठ।"],
                "token_usage": {},
            }
        )

        with redirect_stdout(StringIO()):
            retry_formatting(R2_CONFIG, r2_client=client, formatter=formatter)

        metadata = json.loads(client.objects[object_key("004", ".json")].decode("utf-8"))
        self.assertEqual(metadata["formatting"]["retry_attempts"], 1)

    def test_existing_valid_formatted_artifacts_update_metadata_without_sarvam_call(self):
        text = "पांचवा पाठ"
        metadata = metadata_for("005", retry_attempts=1)
        objects = r2_objects(("005", metadata, text))
        objects[object_key("005", ".formatted.json")] = json_object(
            {
                "schema_version": "1.0.0",
                "provider": "sarvam",
                "model": "sarvam-30b",
                "fallback_model_used": None,
                "source_text_sha256": source_text_sha256(text),
                "status": "formatted",
                "paragraphs": ["पांचवा पाठ।"],
            }
        )
        objects[object_key("005", ".formatted.md")] = "पांचवा पाठ।\n".encode("utf-8")
        client = FakeR2Client(objects)
        formatter = FakeFormatter(error=AssertionError("formatter should not be called"))
        reporter = RecordingReporter()

        output = StringIO()
        with redirect_stdout(output):
            retry_formatting(
                R2_CONFIG,
                r2_client=client,
                formatter=formatter,
                reporter=reporter,
            )

        metadata = json.loads(client.objects[object_key("005", ".json")].decode("utf-8"))
        self.assertIn(
            "retry-formatting summary: formatted=0 metadata_updated=1 failed=0 skipped=0 retry_exhausted=0",
            output.getvalue(),
        )
        self.assertIn("metadata updated:", output.getvalue())
        self.assertIn("005 existing formatted artifacts were valid; no Sarvam call made", output.getvalue())
        self.assertIn(
            "[005] existing formatted artifacts are valid; updating metadata only",
            reporter.messages,
        )
        self.assertIn("[005] metadata updated without Sarvam call", reporter.messages)
        self.assertEqual(formatter.calls, [])
        self.assertEqual(metadata["formatting"]["status"], "formatted")
        self.assertEqual(metadata["formatting"]["retry_attempts"], 1)
        self.assertIn("formatted_json", metadata["storage"]["artifacts"])


if __name__ == "__main__":
    unittest.main()
