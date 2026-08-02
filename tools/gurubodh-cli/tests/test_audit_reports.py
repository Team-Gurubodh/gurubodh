import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from gurubodh.metadata import build_chapter_metadata
from gurubodh.prep_subject_audit import PrepSubjectAuditWriter
from gurubodh.pipelines.common import staging_progress
from gurubodh.project import ProjectContext


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
        "enabled": True,
        "pattern_type": "literal",
        "pattern": "Chapter",
    },
    "metadata_defaults": {
        "language": "hi-IN",
        "source_script": "Devanagari",
        "output_text_encoding": "UTF-8",
        "summary_chapter_markers": ["उपसंहार"],
    },
}


class PrepSubjectAuditReportTests(unittest.TestCase):
    def test_staging_progress_announces_root_once_and_uses_relative_artifact_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            subject_dir = Path(temp_dir) / "123_spand_rahasya"
            output = StringIO()
            with redirect_stdout(output):
                progress = staging_progress(subject_dir)
                progress(
                    "split 01/02",
                    subject_dir / "chapters" / "msword" / "chapter-001.docx",
                    subject_dir / "chapters" / "text_and_metadata" / "chapter-001.txt",
                )

            report = output.getvalue()
            self.assertEqual(report.count(str(subject_dir)), 1)
            self.assertIn("Outputs: full_subject/, chapters/msword/, and chapters/text_and_metadata/", report)
            self.assertIn("[split 01/02] chapter-001 (DOCX, text)", report)

    def make_job(self, temp_dir, config):
        subject_dir = Path(temp_dir) / config["destination"]["subject_dir"]
        paths = {
            "subject": subject_dir,
            "full_subject": subject_dir / "full_subject",
            "chapter_msword": subject_dir / "chapters" / "msword",
            "text_and_metadata": subject_dir / "chapters" / "text_and_metadata",
        }
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
        (paths["full_subject"] / "full.docx").write_bytes(b"docx")
        (paths["full_subject"] / "full.txt").write_text("full text\n", encoding="utf-8")
        return {
            "paths": paths,
            "local_destination": {
                "path": str(subject_dir),
                "existed_before_run": True,
                "removed_for_overwrite": True,
            },
            "r2_preflight": {
                "status": "passed",
                "bucket": "gurubodh-library-dev",
                "prefix": "cms_library/129_spand_rahasya/",
            },
        }

    def write_chapter_metadata(self, config, job, chapter_number=1, text="प्रबोधन\n\nउपसंहार"):
        docx_name = f"chapter-{chapter_number:03d}.docx"
        text_name = f"chapter-{chapter_number:03d}.txt"
        metadata_name = f"chapter-{chapter_number:03d}.json"
        metadata = build_chapter_metadata(
            config,
            chapter_number,
            {
                "metadata": metadata_name,
                "text": text_name,
                "msword": docx_name,
                "metadata_relative_path": Path("chapters/text_and_metadata") / metadata_name,
                "text_relative_path": Path("chapters/text_and_metadata") / text_name,
                "msword_relative_path": Path("chapters/msword") / docx_name,
                "full_msword_relative_path": Path("full_subject/full.docx"),
                "full_text_relative_path": Path("full_subject/full.txt"),
            },
            text,
            {},
            "2026-07-23T00:00:00Z",
            "python3 -m gurubodh prep-subject",
        )
        (job["paths"]["chapter_msword"] / docx_name).write_bytes(b"chapter docx")
        (job["paths"]["text_and_metadata"] / text_name).write_text(text + "\n", encoding="utf-8")
        metadata_path = job["paths"]["text_and_metadata"] / metadata_name
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return metadata_path

    def make_writer(self, temp_dir, config, job, result=None):
        context = ProjectContext(root=Path(temp_dir), legacy_converter=Path(temp_dir) / "converter.js")
        return PrepSubjectAuditWriter(
            context,
            Path(temp_dir) / "job.json",
            config,
            "python3 -m gurubodh prep-subject",
            True,
            job,
            result or {"converter_counts": {}, "total_nodes": 0, "total_chars": 18},
            [job["paths"]["chapter_msword"] / "chapter-001.docx"],
        )

    def test_local_audit_report_writes_json_markdown_and_redacts_safe_snapshot(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["source"]["api_key"] = "do-not-write"
        config["destination"]["secret_access_key"] = "do-not-write"

        with tempfile.TemporaryDirectory() as temp_dir:
            job = self.make_job(temp_dir, config)
            self.write_chapter_metadata(config, job)
            writer = self.make_writer(temp_dir, config, job)

            output = StringIO()
            with redirect_stdout(output):
                report = writer.write_local_success()

            json_path = writer.paths["json"]
            markdown_path = writer.paths["markdown"]
            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")
            payload_text = json.dumps(payload, ensure_ascii=False)

            self.assertEqual(report["publish_audit"]["backend"], "local")
            self.assertEqual(payload["processing_summary"]["chapters_detected"], 1)
            self.assertEqual(payload["processing_summary"]["summary_chapter_count"], 1)
            self.assertEqual(payload["final_outcome"]["generated_artifact_counts"]["run_report_json"], 1)
            self.assertEqual(payload["final_outcome"]["generated_artifact_counts"]["run_report_markdown"], 1)
            self.assertIn("# Gurubodh prep-subject Audit Report", markdown)
            self.assertIn("| Chapter | Content key | Text artifact | SHA-256 |", markdown)
            self.assertIn("prep-subject audit reports:", output.getvalue())
            self.assertIn(f"directory: {writer.paths['directory']}", output.getvalue())
            self.assertIn(f"  {writer.paths['json'].name}", output.getvalue())
            self.assertIn(f"  {writer.paths['markdown'].name}", output.getvalue())
            self.assertNotIn("do-not-write", payload_text)
            self.assertIn("[redacted]", payload_text)

    def test_legacy_audit_report_includes_converter_counts(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["pipeline"] = "legacy-docx-to-unicode"
        config["source"]["font_encoding"] = "aps"

        with tempfile.TemporaryDirectory() as temp_dir:
            job = self.make_job(temp_dir, config)
            self.write_chapter_metadata(config, job, text="प्रबोधन\n\nपाठ")
            writer = self.make_writer(
                temp_dir,
                config,
                job,
                result={"converter_counts": {"aps": 3}, "total_nodes": 7, "total_chars": 42},
            )

            with redirect_stdout(StringIO()):
                report = writer.write_local_success()

            self.assertEqual(report["processing_summary"]["legacy_converter_counts"], {"aps": 3})
            self.assertEqual(report["processing_summary"]["converted_text_nodes"], 7)

    def test_local_audit_relocates_from_staging_to_published_subject(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = self.make_job(temp_dir, json.loads(json.dumps(BASE_CONFIG)))
            self.write_chapter_metadata(BASE_CONFIG, job)
            staging_subject = job["paths"]["subject"]
            published_subject = Path(temp_dir) / "published" / BASE_CONFIG["destination"]["subject_dir"]
            published_subject.parent.mkdir(parents=True)
            staging_subject.rename(published_subject)
            job["paths"] = {
                key: published_subject / value.relative_to(staging_subject)
                for key, value in job["paths"].items()
            }
            writer = self.make_writer(temp_dir, BASE_CONFIG, job)
            # Simulate construction before the local staging tree was promoted.
            writer.paths = writer.paths | {
                "directory": staging_subject / "run_reports" / "prep-subject",
                "json": staging_subject / "run_reports" / "prep-subject" / writer.paths["json"].name,
                "markdown": staging_subject / "run_reports" / "prep-subject" / writer.paths["markdown"].name,
            }
            with redirect_stdout(StringIO()):
                writer.write_local_success()
            self.assertTrue(writer.paths["json"].is_file())
            self.assertTrue(str(writer.paths["json"]).startswith(str(published_subject)))

    def test_r2_audit_report_updates_publish_counts_before_upload(self):
        config = json.loads(json.dumps(BASE_CONFIG))
        config["destination"] = {
            "backend": "r2",
            "bucket": "gurubodh-library-dev",
            "prefix": "cms_library",
            "subject_dir": "129_spand_rahasya",
            "url_base": None,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            job = self.make_job(temp_dir, config)
            self.write_chapter_metadata(config, job)
            writer = self.make_writer(temp_dir, config, job)

            with redirect_stdout(StringIO()):
                writer.write_r2_pending()
            uploads = [
                (path, f"key/{index}")
                for index, path in enumerate(job["paths"]["subject"].rglob("*"))
                if path.is_file()
            ]
            with redirect_stdout(StringIO()):
                report = writer.before_r2_upload(uploads, ["cms_library/129_spand_rahasya/chapters/stale.txt"])

            payload = json.loads(writer.paths["json"].read_text(encoding="utf-8"))
            self.assertEqual(report["publish_audit"]["backend"], "r2")
            self.assertEqual(report["publish_audit"]["status"], "succeeded")
            self.assertTrue(report["publish_audit"]["destructive_replacement"])
            self.assertEqual(report["publish_audit"]["deleted_object_count"], 1)
            self.assertEqual(report["publish_audit"]["artifact_files_prepared_for_upload"], len(uploads))
            self.assertEqual(payload["publish_audit"]["uploaded_artifact_count"], len(uploads))
            self.assertEqual(
                payload["final_outcome"]["report_files"]["json"]["key"],
                "cms_library/129_spand_rahasya/run_reports/prep-subject/" + writer.paths["json"].name,
            )


if __name__ == "__main__":
    unittest.main()
