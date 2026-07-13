import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from gurubodh_utils.docx.chapter_split import format_chapter_artifacts
from gurubodh_utils.formatting import source_text_sha256
from gurubodh_utils.storage import publish_r2_destination


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
}


R2_CONFIG = {
    "destination": {
        "backend": "r2",
        "bucket": "gurubodh-library-dev",
        "prefix": "cms_library",
        "subject_dir": "129_spand_rahasya",
        "url_base": None,
    }
}


class FakeFormatter:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def format_text(self, text):
        self.calls.append(text)
        if self.error:
            raise self.error
        return self.result


class FakeR2Client:
    def __init__(self):
        self.uploads = []

    def exists(self, bucket, key):
        return False

    def upload_file(self, path, bucket, key):
        self.uploads.append((Path(path).name, bucket, key))


class ChapterFormattingArtifactTests(unittest.TestCase):
    def test_successful_formatting_writes_json_and_markdown_artifacts(self):
        text = "पहला वाक्य दूसरा वाक्य"
        result = {
            "schema_version": "1.0.0",
            "provider": "sarvam",
            "model": "sarvam-30b",
            "fallback_model_used": None,
            "source_text_sha256": source_text_sha256(text),
            "status": "formatted",
            "paragraphs": ["पहला वाक्य।", "दूसरा वाक्य।"],
        }
        formatter = FakeFormatter(result=result)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            formatting_result = format_chapter_artifacts(
                output_dir,
                "CAT020_SUB129_spand-rahasya_001_v01.01.txt",
                1,
                text,
                FORMATTING_CONFIG,
                formatter,
            )

            json_path = output_dir / "CAT020_SUB129_spand-rahasya_001_v01.01.formatted.json"
            markdown_path = output_dir / "CAT020_SUB129_spand-rahasya_001_v01.01.formatted.md"

            self.assertEqual(formatting_result["status"], "formatted")
            self.assertEqual(formatter.calls, [text])
            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), result)
            self.assertEqual(
                markdown_path.read_text(encoding="utf-8"),
                "पहला वाक्य।\n\nदूसरा वाक्य।\n",
            )

    def test_disabled_formatting_does_not_call_formatter_or_write_artifacts(self):
        formatter = FakeFormatter(error=AssertionError("formatter should not be called"))
        config = dict(FORMATTING_CONFIG)
        config["enabled"] = False

        with tempfile.TemporaryDirectory() as temp_dir:
            result = format_chapter_artifacts(
                Path(temp_dir),
                "chapter.txt",
                1,
                "प्रबोधन",
                config,
                formatter,
            )

            self.assertEqual(result, {"status": "disabled", "warning": None, "artifacts": {}})
            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    def test_formatting_failure_warns_and_continues_when_configured(self):
        formatter = FakeFormatter(error=RuntimeError("rate limit"))
        stdout = StringIO()

        with tempfile.TemporaryDirectory() as temp_dir:
            with redirect_stdout(stdout):
                result = format_chapter_artifacts(
                    Path(temp_dir),
                    "chapter.txt",
                    2,
                    "प्रबोधन",
                    FORMATTING_CONFIG,
                    formatter,
                )

            self.assertEqual(result["status"], "failed")
            self.assertIn("chapter 002 chapter", result["warning"])
            self.assertIn("rate limit", result["warning"])
            self.assertIn("warning: formatting failed", stdout.getvalue())
            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    def test_formatting_failure_raises_when_continue_on_error_is_false(self):
        formatter = FakeFormatter(error=RuntimeError("bad credentials"))
        config = dict(FORMATTING_CONFIG)
        config["continue_on_error"] = False

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(SystemExit) as exc:
                format_chapter_artifacts(
                    Path(temp_dir),
                    "chapter.txt",
                    3,
                    "प्रबोधन",
                    config,
                    formatter,
                )

        self.assertIn("chapter 003 chapter", str(exc.exception))
        self.assertIn("bad credentials", str(exc.exception))

    def test_r2_publish_all_artifacts_flow_includes_formatted_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            subject_dir = Path(temp_dir) / "129_spand_rahasya"
            artifact_dir = subject_dir / "chapters" / "text_and_metadata"
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "chapter.txt").write_text("raw\n", encoding="utf-8")
            (artifact_dir / "chapter.formatted.json").write_text("{}\n", encoding="utf-8")
            (artifact_dir / "chapter.formatted.md").write_text("formatted\n", encoding="utf-8")
            client = FakeR2Client()

            with redirect_stdout(StringIO()):
                publish_r2_destination(R2_CONFIG, subject_dir, overwrite=True, r2_client=client)

        uploaded_keys = {upload[2] for upload in client.uploads}
        self.assertIn(
            "cms_library/129_spand_rahasya/chapters/text_and_metadata/chapter.formatted.json",
            uploaded_keys,
        )
        self.assertIn(
            "cms_library/129_spand_rahasya/chapters/text_and_metadata/chapter.formatted.md",
            uploaded_keys,
        )


if __name__ == "__main__":
    unittest.main()
