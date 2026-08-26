import io
import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from gurubodh.pipelines import legacy_docx_to_unicode, unicode_docx_ingest
from gurubodh.prep_subject_checkpoints import JOB_STATE_RELATIVE_PATH, run_resumable_prep_job
from gurubodh.proofreading import ProofreadingError, ProofreadingSettings


DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>विषय परीक्षण</w:t></w:r></w:p>
    <w:p><w:r><w:t>CHAPTER 1</w:t></w:r></w:p>
    <w:p><w:r><w:t>पहला गलत पाठ।</w:t></w:r></w:p>
    <w:p><w:r><w:t>CHAPTER 2</w:t></w:r></w:p>
    <w:p><w:r><w:t>दूसरा गलत पाठ।</w:t></w:r></w:p>
    <w:sectPr />
  </w:body>
</w:document>
"""


def write_docx(path):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", DOCUMENT_XML)


def config(root):
    values = {
        "schema_version": "1.4.0",
        "pipeline": "unicode-docx-ingest",
        "source": {
            "backend": "local", "root_dir": str(root), "relative_path": "source.docx",
            "font_encoding": "unicode", "file_format": "docx",
        },
        "destination": {"backend": "local", "root_dir": str(root), "subject_dir": "subject/hi-IN"},
        "naming": {"category_code": "CAT001", "subject_code": "SUB123", "title_slug": "checkpoint-test", "version": "01", "subversion": "01"},
        "chapter_split": {"enabled": True, "pattern_type": "literal", "pattern": "CHAPTER"},
        "metadata_defaults": {"language": "hi-IN", "source_script": "Devanagari", "output_text_encoding": "UTF-8"},
    }
    values["_proofreading_config"] = ProofreadingSettings(min_request_interval_seconds=0)
    return values


class FakeR2Client:
    def __init__(self):
        self.objects = {}

    def exists(self, bucket, key):
        return key in self.objects

    def list_keys(self, bucket, prefix):
        return sorted(key for key in self.objects if key.startswith(prefix))

    def download_file(self, bucket, key, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(self.objects[key])

    def upload_file(self, path, bucket, key):
        self.objects[key] = Path(path).read_bytes()

    def delete_prefix(self, bucket, prefix):
        deleted = [key for key in self.objects if key.startswith(prefix)]
        for key in deleted:
            del self.objects[key]
        return deleted


class FakeProofreader:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = []

    def proofread(self, text, progress=None):
        self.calls.append(text)
        if progress:
            progress("fake Gemini request")
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return {
            "corrected_text": outcome,
            "edits": [{"original": "गलत", "corrected": "सही", "category": "spelling", "reason": "वर्तनी"}],
            "estimated_input_tokens": 1,
            "attempts": 1,
            "throttle_seconds": 0,
            "usage": {"input_tokens": 1},
        }


def prepare_unicode(source_path, output_path, text_path, progress):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(source_path.read_bytes())
    text_path.write_text("source text\n", encoding="utf-8")
    progress("prepare", output_path, text_path)
    return {"output_path": output_path, "text_path": text_path, "converter_counts": {}, "total_nodes": 0, "total_chars": 11}


class PrepSubjectCheckpointTests(unittest.TestCase):
    def test_pipeline_banners_are_emitted_only_when_preparation_callback_runs(self):
        pipeline_config = {"pipeline": "unicode-docx-ingest"}
        unicode_output = io.StringIO()
        with (
            patch.object(unicode_docx_ingest, "validate_pipeline_matches_source"),
            patch.object(unicode_docx_ingest, "run_resumable_prep_job", return_value={}) as unicode_runner,
            redirect_stdout(unicode_output),
        ):
            unicode_docx_ingest.run_unicode_docx_ingest(None, pipeline_config, "prep-subject", resume=True)
        self.assertEqual(unicode_output.getvalue(), "")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.docx"
            write_docx(source)
            output = io.StringIO()
            with redirect_stdout(output):
                unicode_runner.call_args.args[6](source, root / "output.docx", root / "output.txt")
            self.assertIn("[prepare] Copying the Unicode source DOCX", output.getvalue())

        legacy_config = {"pipeline": "legacy-docx-to-unicode"}
        legacy_context = type("LegacyContext", (), {"legacy_converter": object()})()
        legacy_output = io.StringIO()
        with (
            patch.object(legacy_docx_to_unicode, "validate_pipeline_matches_source"),
            patch.object(legacy_docx_to_unicode, "target_devanagari_font", return_value="Nirmala UI"),
            patch.object(legacy_docx_to_unicode, "run_resumable_prep_job", return_value={}) as legacy_runner,
            redirect_stdout(legacy_output),
        ):
            legacy_docx_to_unicode.run_legacy_docx_to_unicode(legacy_context, legacy_config, "prep-subject", resume=True)
        self.assertEqual(legacy_output.getvalue(), "")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = io.StringIO()
            with patch.object(legacy_docx_to_unicode, "convert_docx", return_value={}) as convert:
                with redirect_stdout(output):
                    legacy_runner.call_args.args[6](root / "source.docx", root / "output.docx", root / "output.txt", lambda *_: None)
            self.assertIn("[prepare] Converting the legacy source DOCX", output.getvalue())
            self.assertTrue(convert.called)

    def test_successful_fresh_and_overwrite_runs_report_published_completion(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_docx(root / "source.docx")
            job_config = config(root)

            for overwrite in (False, True):
                proofreader = FakeProofreader([
                    "CHAPTER 1\nपहला सही पाठ。",
                    "CHAPTER 2\nदूसरा सही पाठ。",
                ])
                output = io.StringIO()
                with (
                    patch("gurubodh.prep_subject_checkpoints.GeminiProofreader", return_value=proofreader),
                    redirect_stdout(output),
                ):
                    result = run_resumable_prep_job(
                        None,
                        job_config,
                        "python3 -m gurubodh prep-subject",
                        overwrite,
                        False,
                        None,
                        prepare_unicode,
                    )

                expected = (
                    f"prep-subject complete; canonical artifacts were published successfully to "
                    f"{root / 'subject' / 'hi-IN'}. Chapters: 2 succeeded, 0 failed, 0 pending."
                )
                self.assertEqual(result["status"], "succeeded")
                self.assertEqual(output.getvalue().rstrip().splitlines()[-1], expected)

    def test_compatible_succeeded_resume_reports_already_complete_without_preparation_or_gemini(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_docx(root / "source.docx")
            job_config = config(root)
            first = FakeProofreader([
                "CHAPTER 1\nपहला सही पाठ。",
                "CHAPTER 2\nदूसरा सही पाठ。",
            ])
            with patch("gurubodh.prep_subject_checkpoints.GeminiProofreader", return_value=first):
                run_resumable_prep_job(None, job_config, "python3 -m gurubodh prep-subject", False, False, None, prepare_unicode)

            resumed = FakeProofreader([])
            output = io.StringIO()
            with (
                patch("gurubodh.prep_subject_checkpoints.GeminiProofreader", return_value=resumed),
                redirect_stdout(output),
            ):
                result = run_resumable_prep_job(None, job_config, "python3 -m gurubodh prep-subject", False, True, None, prepare_unicode)

            self.assertTrue(result["already_complete"])
            self.assertEqual(resumed.calls, [])
            self.assertNotIn("[prepare]", output.getvalue())
            self.assertEqual(
                output.getvalue().rstrip(),
                "prep-subject already complete; the compatible checkpoint is succeeded. No Gemini requests were made.",
            )

    def test_resume_reuses_valid_success_and_publishes_only_after_all_chapters_succeed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_docx(root / "source.docx")
            job_config = config(root)
            first = FakeProofreader([
                "CHAPTER 1\nपहला सही पाठ।",
                ProofreadingError("api_error", "temporary provider failure", retryable=True),
            ])
            with patch("gurubodh.prep_subject_checkpoints.GeminiProofreader", return_value=first):
                with self.assertRaisesRegex(SystemExit, "incomplete"):
                    run_resumable_prep_job(None, job_config, "python3 -m gurubodh prep-subject", False, False, None, prepare_unicode)

            subject = root / "subject" / "hi-IN"
            state_path = subject / JOB_STATE_RELATIVE_PATH
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["state"], "incomplete")
            self.assertEqual(state["counts"], {"succeeded": 1, "failed": 1, "pending": 0})
            self.assertEqual(
                state["compatibility"]["output_affecting_inputs"]["proofreading"]["locale"]["language"],
                "hi-IN",
            )
            self.assertNotIn("पहला गलत पाठ", state_path.read_text(encoding="utf-8"))
            report = next((subject / "run_reports" / "prep-subject").glob("*.json"))
            report_payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertNotIn("पहला गलत पाठ", report.read_text(encoding="utf-8"))
            self.assertEqual(report_payload["subject"]["language"], "hi-IN")
            self.assertEqual(report_payload["subject"]["artifact_root"], str(subject))
            self.assertEqual(report_payload["proofreading_locale"]["instruction_template"]["id"], "hi-IN-proofreading")
            self.assertFalse((subject / "chapters" / "chapter_content_manifest.json").exists())
            self.assertEqual(len(first.calls), 2)

            second = FakeProofreader(["CHAPTER 2\nदूसरा सही पाठ।"])
            with patch("gurubodh.prep_subject_checkpoints.GeminiProofreader", return_value=second):
                result = run_resumable_prep_job(None, job_config, "python3 -m gurubodh prep-subject", False, True, None, prepare_unicode)

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(state["state"], "succeeded")
            self.assertEqual(state["counts"], {"succeeded": 2, "failed": 0, "pending": 0})
            self.assertEqual(len(second.calls), 1)
            self.assertTrue((subject / "chapters" / "chapter_content_manifest.json").is_file())
            self.assertFalse((subject / ".work" / "prep-subject" / state["job_id"]).exists())

    def test_fake_r2_retains_checkpoint_workspace_then_publishes_canonical_manifest_last(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_docx(root / "source.docx")
            job_config = config(root)
            job_config["destination"] = {
                "backend": "r2", "bucket": "test-bucket", "prefix": "cms_library", "subject_dir": "subject/hi-IN", "url_base": None,
            }
            client = FakeR2Client()
            first = FakeProofreader([
                "CHAPTER 1\nपहला सही पाठ।",
                ProofreadingError("api_error", "temporary provider failure", retryable=True),
            ])
            with patch("gurubodh.prep_subject_checkpoints.GeminiProofreader", return_value=first):
                with self.assertRaisesRegex(SystemExit, "incomplete"):
                    run_resumable_prep_job(None, job_config, "python3 -m gurubodh prep-subject", False, False, None, prepare_unicode, r2_client=client)

            state_key = "cms_library/subject/hi-IN/run_state/prep-subject/job-state.json"
            state = json.loads(client.objects[state_key].decode("utf-8"))
            workspace_prefix = f"cms_library/subject/hi-IN/.work/prep-subject/{state['job_id']}/"
            self.assertEqual(state["state"], "incomplete")
            self.assertTrue(any(key.startswith(workspace_prefix) for key in client.objects))

            second = FakeProofreader(["CHAPTER 2\nदूसरा सही पाठ।"])
            with patch("gurubodh.prep_subject_checkpoints.GeminiProofreader", return_value=second):
                run_resumable_prep_job(None, job_config, "python3 -m gurubodh prep-subject", False, True, None, prepare_unicode, r2_client=client)

            state = json.loads(client.objects[state_key].decode("utf-8"))
            self.assertEqual(state["state"], "succeeded")
            self.assertIn("cms_library/subject/hi-IN/chapters/chapter_content_manifest.json", client.objects)
            self.assertFalse(any(key.startswith(workspace_prefix) for key in client.objects))
            self.assertEqual(len(second.calls), 1)


if __name__ == "__main__":
    unittest.main()
