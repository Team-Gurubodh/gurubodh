from pathlib import Path

from gurubodh.audit import AuditReportBuilder, report_basename, report_paths, write_report
from gurubodh.constants import SEMANTIC_CHUNKS_OUTPUT_DIR
from gurubodh.naming import version_label
from gurubodh.storage import (
    destination_artifact_reference,
    is_r2,
    subject_artifact_prefix,
)


COMMAND_NAME = "generate-chunks"


def job_identity(config, job):
    destination = config["destination"]
    source = config["source"]
    identity = {
        "category_code": config["naming"]["category_code"],
        "subject_code": config["naming"]["subject_code"],
        "title_slug": config["naming"]["title_slug"],
        "version": config["naming"]["version"],
        "subversion": config["naming"]["subversion"],
        "version_label": version_label(config),
        "source_subject": source_subject_reference(source, job),
    }
    if is_r2(destination):
        identity["destination_output"] = {
            "backend": "r2",
            "bucket": destination["bucket"],
            "prefix": job["destination_output_prefix"],
        }
    else:
        identity["destination_output"] = {
            "backend": "local",
            "path": str(job["paths"]["semantic_chunks"]),
        }
    return identity


def source_subject_reference(source, job):
    if is_r2(source):
        return {
            "backend": "r2",
            "bucket": source["bucket"],
            "prefix": subject_artifact_prefix(source),
        }
    return {
        "backend": "local",
        "path": str(job["paths"]["source_subject"]),
    }


def local_publish_audit(job):
    return {
        "backend": "local",
        "status": "succeeded",
        "destination_output_path": str(job["paths"]["semantic_chunks"]),
        "existed_before_run": job["destination_preflight"]["existed_before_run"],
        "removed_for_overwrite": job["destination_preflight"]["removed_for_overwrite"],
    }


def r2_publish_audit(config, job, status="pending", uploads=None):
    uploads = uploads or []
    destination = config["destination"]
    return {
        "backend": "r2",
        "status": status,
        "bucket": destination["bucket"],
        "destination_output_prefix": job["destination_output_prefix"],
        "existing_prefix_check_status": job["destination_preflight"]["status"],
        "deleted_for_overwrite_count": len(job["destination_preflight"].get("deleted_keys", [])),
        "artifact_files_prepared_for_upload": len(uploads) if uploads else None,
        "uploaded_artifact_count": len(uploads) if status == "succeeded" else None,
        "failure_message": None,
    }


def report_references(config, paths):
    return {
        "json": destination_artifact_reference(config, Path("run_reports") / paths["json"].name),
        "markdown": destination_artifact_reference(config, Path("run_reports") / paths["markdown"].name),
    }


def processing_summary(result, publish_audit):
    return {
        "source_chapter_count": result["source_chapter_count"],
        "processed_chapter_count": result["processed_chapter_count"],
        "skipped_chapter_count": result["skipped_chapter_count"],
        "failed_chapter_count": result["failed_chapter_count"],
        "chunk_artifacts_written": result["chunk_artifacts_written"],
        "summary_written": result["summary_written"],
        "total_chunk_count": result["total_chunk_count"],
        "total_estimated_embedding_token_count": result["total_estimated_embedding_token_count"],
        "output_directory_name": SEMANTIC_CHUNKS_OUTPUT_DIR,
        "publish_status": publish_audit["status"],
    }


def operator_notes(report):
    notes = []
    if report["processing_summary"]["processed_chapter_count"] == 0:
        notes.append("No chapters were processed; review the chapter filter and source artifacts.")
    if report["publish_audit"]["backend"] == "r2":
        notes.append("If R2 publishing fails, check Cloudflare R2 credentials, bucket, prefix, and object permissions.")
    if report["run_identity"]["overwrite"]:
        notes.append("Overwrite was enabled only for semantic chunk and embedding outputs.")
    else:
        notes.append("If semantic chunk outputs already exist, rerun with --overwrite only when replacing them is intentional.")
    return notes


def render_markdown(report):
    lines = [
        "# Gurubodh generate-chunks Audit Report",
        "",
        "## Run Identity",
        "",
        f"- Status: {report['run_identity']['status']}",
        f"- Run timestamp: {report['run_identity']['run_timestamp']}",
        f"- Entry point: `{report['run_identity']['entry_point']}`",
        f"- Config path: `{report['run_identity']['config_path']}`",
        f"- Source backend: `{report['run_identity']['source_backend']}`",
        f"- Destination backend: `{report['run_identity']['destination_backend']}`",
        f"- Overwrite: `{report['run_identity']['overwrite']}`",
        f"- Git commit SHA: `{report['run_identity']['git_commit_sha'] or 'unavailable'}`",
        "",
        "## Processing Summary",
        "",
        f"- Source chapters: {report['processing_summary']['source_chapter_count']}",
        f"- Processed chapters: {report['processing_summary']['processed_chapter_count']}",
        f"- Skipped chapters: {report['processing_summary']['skipped_chapter_count']}",
        f"- Failed chapters: {report['processing_summary']['failed_chapter_count']}",
        f"- Chunk artifacts: {report['processing_summary']['chunk_artifacts_written']}",
        f"- Total chunks: {report['processing_summary']['total_chunk_count']}",
        f"- Estimated embedding tokens: {report['processing_summary']['total_estimated_embedding_token_count']}",
        f"- Publish status: {report['processing_summary']['publish_status']}",
        "",
        "## Per-Chapter Audit",
        "",
    ]
    if report["chapters"]:
        lines.append("| Chapter | Source text | Chunk artifact | Chunks | Tokens | Status |")
        lines.append("| --- | --- | --- | ---: | ---: | --- |")
        for chapter in report["chapters"]:
            lines.append(
                "| "
                f"{chapter['chapter_number']} | "
                f"{chapter['source_text_filename']} | "
                f"{chapter.get('chunk_filename') or '-'} | "
                f"{chapter['chunk_count']} | "
                f"{chapter['estimated_embedding_token_count']} | "
                f"{chapter['status']} |"
            )
    else:
        lines.append("No chapter chunk artifacts were generated.")
    lines.extend(["", "## Publish Audit", ""])
    for key, value in report["publish_audit"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Operator Notes", ""])
    for note in report["final_outcome"]["operator_notes"]:
        lines.append(f"- {note}")
    return "\n".join(lines)


class GenerateChunksAuditWriter:
    def __init__(self, context, config_path, config, entry_point, overwrite, job, result):
        self.context = context
        self.config_path = config_path
        self.config = config
        self.entry_point = entry_point
        self.overwrite = overwrite
        self.job = job
        self.result = result
        self.builder = AuditReportBuilder(COMMAND_NAME, entry_point, context, config_path, config, overwrite)
        basename = report_basename(config, COMMAND_NAME, self.builder.filename_timestamp)
        self.paths = report_paths(job["paths"]["destination_subject"], basename)
        self.report = None

    def build(self, publish_audit):
        report = {
            "schema_version": "1.0.0",
            "run_identity": self.builder.run_identity("succeeded"),
            "job_identity": job_identity(self.config, self.job),
            "configuration_snapshot": self.builder.safe_config_snapshot(),
            "processing_summary": processing_summary(self.result, publish_audit),
            "chapters": self.result["chapters"],
            "publish_audit": publish_audit,
            "final_outcome": {
                "status": "succeeded",
                "output_location": str(self.job["paths"]["semantic_chunks"]),
                "report_files": report_references(self.config, self.paths),
                "failed_stage": None,
                "operator_notes": [],
            },
        }
        report["final_outcome"]["operator_notes"] = operator_notes(report)
        return report

    def write(self, publish_audit):
        self.report = self.build(publish_audit)
        write_report(self.paths, self.report, render_markdown(self.report))
        print(f"wrote generate-chunks audit report {self.paths['json']}")
        print(f"wrote generate-chunks audit report {self.paths['markdown']}")
        return self.report

    def write_local_success(self):
        return self.write(local_publish_audit(self.job))

    def write_r2_pending(self):
        return self.write(r2_publish_audit(self.config, self.job))

    def before_r2_upload(self, uploads):
        return self.write(r2_publish_audit(self.config, self.job, status="succeeded", uploads=uploads))
