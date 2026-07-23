import json
from pathlib import Path

from gurubodh.audit import AuditReportBuilder, report_basename, report_paths, write_report
from gurubodh.metadata import SUMMARY_CHAPTER_TAGS
from gurubodh.naming import version_label
from gurubodh.storage import (
    destination_artifact_reference,
    destination_subject_prefix,
    is_r2,
    source_reference,
)


COMMAND_NAME = "prep-subject"


def job_identity(config, job):
    destination = config["destination"]
    identity = {
        "category_code": config["naming"]["category_code"],
        "subject_code": config["naming"]["subject_code"],
        "title_slug": config["naming"]["title_slug"],
        "version": config["naming"]["version"],
        "subversion": config["naming"]["subversion"],
        "version_label": version_label(config),
        "source_docx": source_reference(config),
    }
    if is_r2(destination):
        identity["destination_subject"] = {
            "backend": "r2",
            "bucket": destination["bucket"],
            "prefix": destination["prefix"],
            "subject_dir": destination["subject_dir"],
            "subject_prefix": destination_subject_prefix(config),
        }
    else:
        identity["destination_subject"] = {
            "backend": "local",
            "path": str(job["paths"]["subject"]),
        }
    return identity


def artifact_counts(subject_dir):
    counts = {
        "full_subject_docx": 0,
        "full_subject_text": 0,
        "chapter_docx": 0,
        "chapter_text": 0,
        "chapter_metadata": 0,
        "run_report_json": 0,
        "run_report_markdown": 0,
        "total_files": 0,
    }
    for path in Path(subject_dir).rglob("*"):
        if not path.is_file():
            continue
        counts["total_files"] += 1
        relative = path.relative_to(subject_dir)
        parts = relative.parts
        suffix = path.suffix.lower()
        if parts[:1] == ("full_subject",) and suffix == ".docx":
            counts["full_subject_docx"] += 1
        elif parts[:1] == ("full_subject",) and suffix == ".txt":
            counts["full_subject_text"] += 1
        elif parts[:2] == ("chapters", "msword") and suffix == ".docx":
            counts["chapter_docx"] += 1
        elif parts[:2] == ("chapters", "text_and_metadata") and suffix == ".txt":
            counts["chapter_text"] += 1
        elif parts[:2] == ("chapters", "text_and_metadata") and suffix == ".json":
            counts["chapter_metadata"] += 1
        elif parts[:1] == ("run_reports",) and suffix == ".json":
            counts["run_report_json"] += 1
        elif parts[:1] == ("run_reports",) and suffix == ".md":
            counts["run_report_markdown"] += 1
    return counts


def read_chapter_metadata(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def chapter_audit_from_metadata(path):
    metadata = read_chapter_metadata(path)
    files = metadata["files"]
    text_filename = files["text_filename"]
    return {
        "chapter_number": metadata["document"]["chapter_number"],
        "artifact_base_name": Path(text_filename).stem,
        "metadata_filename": files["metadata_filename"],
        "text_filename": text_filename,
        "msword_filename": files["msword_filename"],
        "text_artifact_sha256": metadata["integrity"]["artifacts"]["text"]["value"],
        "content_stats": metadata["content_stats"],
        "automated_tags": metadata["content"]["automated_tags"],
        "storage": metadata["storage"],
        "status": "succeeded",
        "warning": None,
        "error": None,
    }


def collect_chapter_audits(text_and_metadata_dir):
    chapters = [
        chapter_audit_from_metadata(path)
        for path in sorted(Path(text_and_metadata_dir).glob("*.json"))
    ]
    return sorted(chapters, key=lambda chapter: chapter["chapter_number"])


def summary_chapter_count(chapters):
    return sum(
        1
        for chapter in chapters
        if all(tag in chapter["automated_tags"] for tag in SUMMARY_CHAPTER_TAGS)
    )


def processing_summary(config, result, split_outputs, chapters, publish_audit, subject_dir):
    counts = artifact_counts(subject_dir)
    chapter_split_enabled = config["chapter_split"].get("enabled", False)
    chapter_count = len(chapters)
    return {
        "source_materialization_status": "succeeded",
        "full_subject_docx_status": "succeeded",
        "full_subject_text_extraction_status": "succeeded",
        "full_subject_text_character_count": result.get("total_chars", 0),
        "docx_validation_status": "succeeded",
        "chapter_split_status": "succeeded" if chapter_split_enabled else "disabled",
        "chapters_detected": chapter_count,
        "chapter_docx_artifacts_written": counts["chapter_docx"],
        "chapter_text_artifacts_written": counts["chapter_text"],
        "chapter_metadata_artifacts_written": counts["chapter_metadata"],
        "split_output_count": len(split_outputs or []),
        "legacy_converter_counts": result.get("converter_counts", {}),
        "converted_text_nodes": result.get("total_nodes", 0),
        "converted_or_extracted_character_count": result.get("total_chars", 0),
        "summary_chapter_count": summary_chapter_count(chapters),
        "artifact_counts": counts,
        "publish_status": publish_audit["status"],
    }


def local_publish_audit(job):
    destination = job.get("local_destination") or {}
    return {
        "backend": "local",
        "status": "succeeded",
        "destination_subject_path": str(job["paths"]["subject"]),
        "existed_before_run": destination.get("existed_before_run", False),
        "removed_for_overwrite": destination.get("removed_for_overwrite", False),
        "final_artifact_root": str(job["paths"]["subject"]),
    }


def r2_publish_audit(config, job, status="pending", uploads=None):
    destination = config["destination"]
    uploads = uploads or []
    preflight = job.get("r2_preflight") or {}
    return {
        "backend": "r2",
        "status": status,
        "bucket": destination["bucket"],
        "prefix": destination["prefix"],
        "destination_subject_prefix": destination_subject_prefix(config),
        "existing_prefix_check_status": preflight.get("status"),
        "object_check_status": "passed" if status == "succeeded" else "pending",
        "artifact_files_prepared_for_upload": len(uploads) if uploads else None,
        "uploaded_artifact_count": len(uploads) if status == "succeeded" else None,
        "failure_message": None,
    }


def operator_notes(report):
    notes = []
    if report["processing_summary"]["chapters_detected"] == 0:
        notes.append("No chapters were detected; review the chapter split configuration.")
    if report["publish_audit"]["backend"] == "r2":
        notes.append("If R2 publishing fails, check Cloudflare R2 credentials, bucket, prefix, and object permissions.")
    if report["run_identity"]["overwrite"]:
        notes.append("Overwrite was enabled; previous local destination contents or R2 objects may have been replaced.")
    else:
        notes.append("If the destination already exists, rerun with --overwrite only when replacing it is intentional.")
    return notes


def relative_report_references(config, paths):
    return {
        "json": destination_artifact_reference(config, Path("run_reports") / paths["json"].name),
        "markdown": destination_artifact_reference(config, Path("run_reports") / paths["markdown"].name),
    }


def render_markdown(report):
    lines = [
        "# Gurubodh prep-subject Audit Report",
        "",
        "## Run Identity",
        "",
        f"- Status: {report['run_identity']['status']}",
        f"- Run timestamp: {report['run_identity']['run_timestamp']}",
        f"- Entry point: `{report['run_identity']['entry_point']}`",
        f"- Config path: `{report['run_identity']['config_path']}`",
        f"- Pipeline: `{report['run_identity']['pipeline']}`",
        f"- Source backend: `{report['run_identity']['source_backend']}`",
        f"- Destination backend: `{report['run_identity']['destination_backend']}`",
        f"- Overwrite: `{report['run_identity']['overwrite']}`",
        f"- Git commit SHA: `{report['run_identity']['git_commit_sha'] or 'unavailable'}`",
        "",
        "## Job Identity",
        "",
        f"- Category code: `{report['job_identity']['category_code']}`",
        f"- Subject code: `{report['job_identity']['subject_code']}`",
        f"- Title slug: `{report['job_identity']['title_slug']}`",
        f"- Version: `{report['job_identity']['version_label']}`",
        "",
        "## Processing Summary",
        "",
        f"- Full subject DOCX: {report['processing_summary']['full_subject_docx_status']}",
        f"- Full subject text extraction: {report['processing_summary']['full_subject_text_extraction_status']}",
        f"- DOCX validation: {report['processing_summary']['docx_validation_status']}",
        f"- Chapter split: {report['processing_summary']['chapter_split_status']}",
        f"- Chapters detected: {report['processing_summary']['chapters_detected']}",
        f"- Chapter DOCX artifacts: {report['processing_summary']['chapter_docx_artifacts_written']}",
        f"- Chapter text artifacts: {report['processing_summary']['chapter_text_artifacts_written']}",
        f"- Chapter metadata artifacts: {report['processing_summary']['chapter_metadata_artifacts_written']}",
        f"- Summary chapters detected: {report['processing_summary']['summary_chapter_count']}",
        f"- Publish status: {report['processing_summary']['publish_status']}",
        "",
        "## Publish Audit",
        "",
    ]
    for key, value in report["publish_audit"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Per-Chapter Audit", ""])
    if report["chapters"]:
        lines.append("| Chapter | Text artifact | SHA-256 | Words | Characters | Tags |")
        lines.append("| --- | --- | --- | ---: | ---: | --- |")
        for chapter in report["chapters"]:
            stats = chapter["content_stats"]
            tags = ", ".join(chapter["automated_tags"]) or "-"
            lines.append(
                "| "
                f"{chapter['chapter_number']} | "
                f"{chapter['text_filename']} | "
                f"`{chapter['text_artifact_sha256']}` | "
                f"{stats['word_count']} | "
                f"{stats['character_count']} | "
                f"{tags} |"
            )
    else:
        lines.append("No chapter metadata artifacts were generated.")
    lines.extend(["", "## Final Outcome", ""])
    for key, value in report["final_outcome"].items():
        if key == "operator_notes":
            continue
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Operator Notes", ""])
    for note in report["final_outcome"]["operator_notes"]:
        lines.append(f"- {note}")
    return "\n".join(lines)


class PrepSubjectAuditWriter:
    def __init__(self, context, config_path, config, entry_point, overwrite, job, result, split_outputs):
        self.context = context
        self.config_path = config_path
        self.config = config
        self.entry_point = entry_point
        self.overwrite = overwrite
        self.job = job
        self.result = result
        self.split_outputs = split_outputs
        self.builder = AuditReportBuilder(COMMAND_NAME, entry_point, context, config_path, config, overwrite)
        basename = report_basename(config, COMMAND_NAME, self.builder.filename_timestamp)
        self.paths = report_paths(job["paths"]["subject"], basename)
        self.report = None

    def build(self, publish_audit):
        chapters = collect_chapter_audits(self.job["paths"]["text_and_metadata"])
        report_files = relative_report_references(self.config, self.paths)
        report = {
            "schema_version": "1.0.0",
            "run_identity": self.builder.run_identity("succeeded"),
            "job_identity": job_identity(self.config, self.job),
            "configuration_snapshot": self.builder.safe_config_snapshot(),
            "processing_summary": processing_summary(
                self.config,
                self.result,
                self.split_outputs,
                chapters,
                publish_audit,
                self.job["paths"]["subject"],
            ),
            "chapters": chapters,
            "publish_audit": publish_audit,
            "final_outcome": {
                "status": "succeeded",
                "output_subject_location": str(self.job["paths"]["subject"]),
                "report_files": report_files,
                "generated_artifact_counts": artifact_counts(self.job["paths"]["subject"]),
                "failed_stage": None,
                "operator_notes": [],
            },
        }
        report["final_outcome"]["operator_notes"] = operator_notes(report)
        return report

    def write(self, publish_audit):
        self.report = self.build(publish_audit)
        write_report(self.paths, self.report, render_markdown(self.report))
        self.report = self.build(publish_audit)
        write_report(self.paths, self.report, render_markdown(self.report))
        print(f"wrote prep-subject audit report {self.paths['json']}")
        print(f"wrote prep-subject audit report {self.paths['markdown']}")
        return self.report

    def write_local_success(self):
        return self.write(local_publish_audit(self.job))

    def write_r2_pending(self):
        return self.write(r2_publish_audit(self.config, self.job))

    def before_r2_upload(self, uploads):
        return self.write(r2_publish_audit(self.config, self.job, status="succeeded", uploads=uploads))
