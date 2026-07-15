import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from gurubodh_utils.paths import destination_paths_for_job
from gurubodh_utils.docx.chapter_split import format_chapter_artifacts, split_docx_into_chapters
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
    "formatting": FORMATTING_CONFIG,
    "destination": {
        "backend": "r2",
        "bucket": "gurubodh-library-dev",
        "prefix": "cms_library",
        "subject_dir": "129_spand_rahasya",
        "url_base": None,
    }
}


LOCAL_CONFIG = {
    "formatting": FORMATTING_CONFIG,
    "destination": {
        "backend": "local",
        "root_dir": "",
        "subject_dir": "129_spand_rahasya",
    },
}


class FakeFormatter:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def format_text(self, text, progress_label=None):
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
    def write_minimal_docx(self, path):
        document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>विषय स्पंद रहस्य</w:t></w:r></w:p>
    <w:p><w:r><w:t>प्रबोधन क्र. 1</w:t></w:r></w:p>
    <w:p><w:r><w:t>पहला पाठ</w:t></w:r></w:p>
    <w:p><w:r><w:t>प्रबोधन क्र. 2</w:t></w:r></w:p>
    <w:p><w:r><w:t>दूसरा पाठ</w:t></w:r></w:p>
  </w:body>
</w:document>"""
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as docx:
            docx.writestr("word/document.xml", document_xml)

    def test_chapter_split_reports_per_chapter_write_progress(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_docx = root / "source.docx"
            self.write_minimal_docx(source_docx)
            output = StringIO()

            with redirect_stdout(output):
                outputs = split_docx_into_chapters(
                    source_docx,
                    {"pattern": "प्रबोधन", "enabled": True},
                    root / "chapters" / "msword",
                    root / "chapters" / "text_and_metadata",
                )

        progress = output.getvalue()
        self.assertIn("[1/2] writing chapter 001-प्रबोधन-क्र-1", progress)
        self.assertIn("[2/2] writing chapter 002-प्रबोधन-क्र-2", progress)
        self.assertEqual(len(outputs), 2)

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
                chapter_total=3,
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

    def test_formatting_progress_reports_start_attempt_and_success(self):
        text = "पहला वाक्य दूसरा वाक्य"
        formatter = FakeFormatter(
            result={
                "schema_version": "1.0.0",
                "provider": "sarvam",
                "model": "sarvam-30b",
                "fallback_model_used": None,
                "source_text_sha256": source_text_sha256(text),
                "status": "formatted",
                "paragraphs": ["पहला वाक्य।", "दूसरा वाक्य।"],
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output = StringIO()
            with redirect_stdout(output):
                format_chapter_artifacts(
                    Path(temp_dir),
                    "chapter.txt",
                    12,
                    text,
                    dict(FORMATTING_CONFIG, max_tokens=4096),
                    formatter,
                    chapter_total=39,
                )

        progress = output.getvalue()
        self.assertIn("[12/39] formatting with sarvam-30b chars=", progress)
        self.assertIn("max_tokens=4096", progress)
        self.assertIn("[12/39] formatted paragraphs=2", progress)

    def test_valid_matching_formatted_artifacts_are_reused_without_formatter_call(self):
        text = "पहला वाक्य दूसरा वाक्य"
        formatter = FakeFormatter(error=AssertionError("formatter should not be called"))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            json_path = output_dir / "chapter.formatted.json"
            markdown_path = output_dir / "chapter.formatted.md"
            json_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "provider": "sarvam",
                        "model": "sarvam-30b",
                        "fallback_model_used": None,
                        "source_text_sha256": source_text_sha256(text),
                        "status": "formatted",
                        "paragraphs": ["पहला वाक्य।", "दूसरा वाक्य।"],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            markdown_path.write_text("पहला वाक्य।\n\nदूसरा वाक्य।\n", encoding="utf-8")

            result = format_chapter_artifacts(
                output_dir,
                "chapter.txt",
                1,
                text,
                FORMATTING_CONFIG,
                formatter,
                chapter_total=39,
            )

            self.assertEqual(result["status"], "skipped-unchanged")
            self.assertEqual(result["artifacts"], {"json": json_path, "markdown": markdown_path})
            self.assertEqual(formatter.calls, [])

    def test_formatting_reuse_progress_reports_skip_reason(self):
        text = "पहला वाक्य दूसरा वाक्य"
        formatter = FakeFormatter(error=AssertionError("formatter should not be called"))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "chapter.formatted.json").write_text(
                json.dumps(
                    {
                        "source_text_sha256": source_text_sha256(text),
                        "status": "formatted",
                        "paragraphs": ["पहला वाक्य।"],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (output_dir / "chapter.formatted.md").write_text("पहला वाक्य।\n", encoding="utf-8")

            output = StringIO()
            with redirect_stdout(output):
                format_chapter_artifacts(
                    output_dir,
                    "chapter.txt",
                    12,
                    text,
                    FORMATTING_CONFIG,
                    formatter,
                    chapter_total=39,
                )

        self.assertIn("[12/39] skipped formatting: unchanged source checksum", output.getvalue())


    def test_checksum_mismatch_regenerates_formatted_artifacts(self):
        old_text = "पुराना पाठ"
        new_text = "नया पाठ"
        formatter = FakeFormatter(
            result={
                "schema_version": "1.0.0",
                "provider": "sarvam",
                "model": "sarvam-30b",
                "fallback_model_used": None,
                "source_text_sha256": source_text_sha256(new_text),
                "status": "formatted",
                "paragraphs": ["नया पाठ।"],
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "chapter.formatted.json").write_text(
                json.dumps(
                    {
                        "source_text_sha256": source_text_sha256(old_text),
                        "status": "formatted",
                        "paragraphs": ["पुराना पाठ।"],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (output_dir / "chapter.formatted.md").write_text("पुराना पाठ।\n", encoding="utf-8")

            result = format_chapter_artifacts(
                output_dir,
                "chapter.txt",
                1,
                new_text,
                FORMATTING_CONFIG,
                formatter,
            )

            self.assertEqual(result["status"], "formatted")
            self.assertEqual(formatter.calls, [new_text])
            self.assertEqual(
                (output_dir / "chapter.formatted.md").read_text(encoding="utf-8"),
                "नया पाठ।\n",
            )

    def test_invalid_existing_formatted_json_regenerates(self):
        text = "प्रबोधन"
        formatter = FakeFormatter(
            result={
                "schema_version": "1.0.0",
                "provider": "sarvam",
                "model": "sarvam-30b",
                "fallback_model_used": None,
                "source_text_sha256": source_text_sha256(text),
                "status": "formatted",
                "paragraphs": ["प्रबोधन।"],
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "chapter.formatted.json").write_text("not-json\n", encoding="utf-8")
            (output_dir / "chapter.formatted.md").write_text("old\n", encoding="utf-8")

            result = format_chapter_artifacts(
                output_dir,
                "chapter.txt",
                1,
                text,
                FORMATTING_CONFIG,
                formatter,
            )

            self.assertEqual(result["status"], "formatted")
            self.assertEqual(formatter.calls, [text])

    def test_local_overwrite_preserves_only_existing_formatted_artifacts_for_reuse(self):
        config = json.loads(json.dumps(LOCAL_CONFIG))

        with tempfile.TemporaryDirectory() as temp_dir:
            config["destination"]["root_dir"] = temp_dir
            subject_dir = Path(temp_dir) / "129_spand_rahasya"
            artifact_dir = subject_dir / "chapters" / "text_and_metadata"
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "chapter.formatted.json").write_text("{}\n", encoding="utf-8")
            (artifact_dir / "chapter.formatted.md").write_text("formatted\n", encoding="utf-8")
            (artifact_dir / "chapter.txt").write_text("raw\n", encoding="utf-8")

            paths, temp_destination = destination_paths_for_job(config, overwrite=True)

            self.assertIsNone(temp_destination)
            self.assertEqual(paths["subject"], subject_dir)
            self.assertTrue((artifact_dir / "chapter.formatted.json").exists())
            self.assertTrue((artifact_dir / "chapter.formatted.md").exists())
            self.assertFalse((artifact_dir / "chapter.txt").exists())

    def test_r2_reuse_strategy_starts_from_current_temp_artifact_tree_only(self):
        paths, temp_destination = destination_paths_for_job(R2_CONFIG, overwrite=True)
        self.addCleanup(temp_destination.cleanup)

        self.assertIsNotNone(temp_destination)
        self.assertIn("gurubodh-content-prep-", str(paths["subject"]))
        self.assertFalse((paths["text_and_metadata"] / "chapter.formatted.json").exists())

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
