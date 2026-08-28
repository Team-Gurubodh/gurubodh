from datetime import datetime, timezone
from pathlib import Path

from gurubodh.audit import AuditReportBuilder, print_report_locations, report_paths, write_report
from gurubodh.constants import SEMANTIC_CHUNKS_OUTPUT_DIR
from gurubodh.naming import version_label
from gurubodh.storage import (
    CHUNKS_REPORT_DIR,
    destination_artifact_reference,
    is_r2,
    subject_artifact_prefix,
)


COMMAND_NAME = "generate-chunks"


def job_identity(config, candidate_manifest, destination_subject):
    destination = config["destination"]
    source = config["source"]
    identity = {
        "category_code": config["naming"]["category_code"],
        "subject_code": config["naming"]["subject_code"],
        "title_slug": config["naming"]["title_slug"],
        "language": config["naming"]["language"],
        "version": config["naming"]["version"],
        "subversion": config["naming"]["subversion"],
        "version_label": version_label(config),
        "source_subject": source_subject_reference(source),
        "chunking_model": {
            "provider": config["chunking"]["provider"],
            "model": config["chunking"]["model"],
            "model_revision": config["chunking"]["model_revision"],
        },
        "source_candidate_manifest": {
            "reference": (candidate_manifest or {}).get("reference"),
            "sha256": (candidate_manifest or {}).get("sha256"),
        },
    }
    if is_r2(destination):
        identity["destination_output"] = {
            "backend": "r2",
            "bucket": destination["bucket"],
            "prefix": f"{subject_artifact_prefix(destination)}chapters/{SEMANTIC_CHUNKS_OUTPUT_DIR}/",
        }
    else:
        identity["destination_output"] = {
            "backend": "local",
            "path": str(Path(destination_subject) / "chapters" / SEMANTIC_CHUNKS_OUTPUT_DIR),
        }
    return identity


def source_subject_reference(source):
    if is_r2(source):
        return {
            "backend": "r2",
            "bucket": source["bucket"],
            "prefix": subject_artifact_prefix(source),
        }
    return {
        "backend": "local",
        "path": str(Path(source["root_dir"]).expanduser() / source["subject_dir"]),
    }


def report_references(config, paths):
    return {
        "json": destination_artifact_reference(config, CHUNKS_REPORT_DIR / paths["json"].name),
        "markdown": destination_artifact_reference(config, CHUNKS_REPORT_DIR / paths["markdown"].name),
    }


def processing_summary(result, publication):
    return {
        "source_chapter_count": result["source_chapter_count"],
        "processed_chapter_count": result["processed_chapter_count"],
        "skipped_chapter_count": result["skipped_chapter_count"],
        "failed_chapter_count": result["failed_chapter_count"],
        "chunk_artifacts_written": result["chunk_artifacts_written"],
        "semantic_chunks_manifest_written": result["chunk_manifest_written"],
        "total_chunk_count": result["total_chunk_count"],
        "total_estimated_token_count": result["total_estimated_token_count"],
        "output_directory_name": SEMANTIC_CHUNKS_OUTPUT_DIR,
        "publish_status": publication["status"],
    }


def operator_notes(report):
    notes = []
    if report["processing_summary"]["processed_chapter_count"] == 0:
        notes.append("No chapters were processed; review the chapter filter and source artifacts.")
    if report["publication"]["backend"] == "r2":
        notes.append("If R2 publishing fails, check Cloudflare R2 credentials, bucket, prefix, and object permissions.")
    if report["run_identity"]["overwrite"]:
        notes.append("Overwrite was enabled only for semantic chunk outputs.")
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
        f"- Provenance source: `{report['run_identity']['build_provenance']['source']}`",
        f"- Image revision: `{report['run_identity']['build_provenance']['image_revision'] or 'not an image run'}`",
        f"- Model revision: `{report['job_identity']['chunking_model']['model_revision']}`",
        f"- Language: `{report['job_identity']['language']}`",
        f"- Candidate manifest SHA-256: `{report['job_identity']['source_candidate_manifest']['sha256'] or 'unavailable'}`",
        "",
        "## Processing Summary",
        "",
        f"- Source chapters: {report['processing_summary']['source_chapter_count']}",
        f"- Processed chapters: {report['processing_summary']['processed_chapter_count']}",
        f"- Skipped chapters: {report['processing_summary']['skipped_chapter_count']}",
        f"- Failed chapters: {report['processing_summary']['failed_chapter_count']}",
        f"- Chunk artifacts: {report['processing_summary']['chunk_artifacts_written']}",
        f"- Total chunks: {report['processing_summary']['total_chunk_count']}",
        f"- Estimated tokens: {report['processing_summary']['total_estimated_token_count']}",
        f"- Publish status: {report['processing_summary']['publish_status']}",
        "",
        "## Per-Chapter Audit",
        "",
    ]
    if report["chapters"]:
        lines.append("| Chapter | Content key | Source text | Chunk artifact | Chunks | Tokens | Status |")
        lines.append("| --- | --- | --- | --- | ---: | ---: | --- |")
        for chapter in report["chapters"]:
            lines.append(
                "| "
                f"{chapter['chapter_number']} | "
                f"`{chapter['content_key']}` | "
                f"{chapter['source_text_filename']} | "
                f"{chapter.get('chunk_filename') or '-'} | "
                f"{chapter['chunk_count']} | "
                f"{chapter['estimated_token_count']} | "
                f"{chapter['status']} |"
            )
    else:
        lines.append("No chapter chunk artifacts were generated.")
    if report.get("failure"):
        lines.extend(
            [
                "",
                "## Failure",
                "",
                f"- State: `{report['failure']['state']}`",
                f"- Error type: `{report['failure']['error_type']}`",
                f"- Message: {report['failure']['message']}",
            ]
        )
    lines.extend(["", "## Publish Audit", ""])
    for key, value in report["publication"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Operator Notes", ""])
    for note in report["final_outcome"]["operator_notes"]:
        lines.append(f"- {note}")
    return "\n".join(lines)


class GenerateChunksAuditWriter:
    def __init__(self, context, config_path, config, entry_point, overwrite, destination_subject):
        self.config = config
        self.builder = AuditReportBuilder(COMMAND_NAME, entry_point, context, config_path, config, overwrite)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        naming = config["naming"]
        basename = (
            f"{naming['category_code']}_{naming['subject_code']}_{naming['title_slug']}_"
            f"{COMMAND_NAME}_{timestamp}"
        )
        self.paths = report_paths(destination_subject, basename, COMMAND_NAME)
        self.report = None

    def build(
        self,
        status,
        candidate_manifest,
        result,
        publication,
        failure,
        lifecycle,
        destination_subject,
    ):
        report = {
            "schema_version": "1.0.0",
            "run_identity": self.builder.run_identity(status, error=failure),
            "job_identity": job_identity(self.config, candidate_manifest, destination_subject),
            "configuration_snapshot": self.builder.safe_config_snapshot(),
            "processing_summary": processing_summary(result, publication),
            "chapters": result["chapters"],
            "publication": publication,
            "publish_audit": publication,
            "lifecycle": lifecycle,
            "failure": failure,
            "final_outcome": {
                "status": status,
                "output_location": str(
                    Path(destination_subject) / "chapters" / SEMANTIC_CHUNKS_OUTPUT_DIR
                ),
                "report_files": report_references(self.config, self.paths),
                "failed_stage": failure.get("state") if failure else None,
                "operator_notes": [],
            },
        }
        report["final_outcome"]["operator_notes"] = operator_notes(report)
        return report

    def write(
        self,
        status,
        candidate_manifest,
        result,
        publication,
        failure=None,
        lifecycle=None,
        destination_subject=None,
        announce=True,
    ):
        self.report = self.build(
            status,
            candidate_manifest,
            result,
            publication,
            failure,
            lifecycle,
            destination_subject,
        )
        write_report(self.paths, self.report, render_markdown(self.report))
        if announce:
            print_report_locations(COMMAND_NAME, self.paths)
        return self.report
