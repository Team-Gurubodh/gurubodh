import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

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
        "schema_version": "1.3.0",
        "pipeline": "unicode-docx-ingest",
        "source": {
            "backend": "local", "root_dir": str(root), "relative_path": "source.docx",
            "font_encoding": "unicode", "file_format": "docx",
        },
        "destination": {"backend": "local", "root_dir": str(root), "subject_dir": "subject"},
        "naming": {"category_code": "CAT001", "subject_code": "SUB123", "title_slug": "checkpoint-test", "version": "01", "subversion": "01"},
        "chapter_split": {"enabled": True, "pattern_type": "literal", "pattern": "CHAPTER"},
        "metadata_defaults": {"language": "hi-Deva"},
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

            subject = root / "subject"
            state_path = subject / JOB_STATE_RELATIVE_PATH
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["state"], "incomplete")
            self.assertEqual(state["counts"], {"succeeded": 1, "failed": 1, "pending": 0})
            self.assertNotIn("पहला गलत पाठ", state_path.read_text(encoding="utf-8"))
            report = next((subject / "run_reports" / "prep-subject").glob("*.json"))
            self.assertNotIn("पहला गलत पाठ", report.read_text(encoding="utf-8"))
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
                "backend": "r2", "bucket": "test-bucket", "prefix": "cms_library", "subject_dir": "subject", "url_base": None,
            }
            client = FakeR2Client()
            first = FakeProofreader([
                "CHAPTER 1\nपहला सही पाठ।",
                ProofreadingError("api_error", "temporary provider failure", retryable=True),
            ])
            with patch("gurubodh.prep_subject_checkpoints.GeminiProofreader", return_value=first):
                with self.assertRaisesRegex(SystemExit, "incomplete"):
                    run_resumable_prep_job(None, job_config, "python3 -m gurubodh prep-subject", False, False, None, prepare_unicode, r2_client=client)

            state_key = "cms_library/subject/run_state/prep-subject/job-state.json"
            state = json.loads(client.objects[state_key].decode("utf-8"))
            workspace_prefix = f"cms_library/subject/.work/prep-subject/{state['job_id']}/"
            self.assertEqual(state["state"], "incomplete")
            self.assertTrue(any(key.startswith(workspace_prefix) for key in client.objects))

            second = FakeProofreader(["CHAPTER 2\nदूसरा सही पाठ।"])
            with patch("gurubodh.prep_subject_checkpoints.GeminiProofreader", return_value=second):
                run_resumable_prep_job(None, job_config, "python3 -m gurubodh prep-subject", False, True, None, prepare_unicode, r2_client=client)

            state = json.loads(client.objects[state_key].decode("utf-8"))
            self.assertEqual(state["state"], "succeeded")
            self.assertIn("cms_library/subject/chapters/chapter_content_manifest.json", client.objects)
            self.assertFalse(any(key.startswith(workspace_prefix) for key in client.objects))
            self.assertEqual(len(second.calls), 1)


if __name__ == "__main__":
    unittest.main()
