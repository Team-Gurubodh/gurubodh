"""Command-specific audit content for semantic chunk generation."""

from pathlib import Path

from gurubodh.audit import (
    AuditContext,
    AuditWriter,
    destination_report_references,
    print_report_locations,
    report_basename,
    report_paths,
)
from gurubodh.constants import SEMANTIC_CHUNKS_OUTPUT_DIR
from gurubodh.naming import version_label
from gurubodh.storage import (
    CHUNKS_REPORT_DIR,
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
            "path": str(
                Path(destination_subject) / "chapters" / SEMANTIC_CHUNKS_OUTPUT_DIR
            ),
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
        "publication_status": publication["status"],
    }


def operator_notes(report):
    notes = []
    if report["processing_summary"]["processed_chapter_count"] == 0:
        notes.append(
            "No chapters were processed; review the chapter filter and source artifacts."
        )
    if report["publication"]["backend"] == "r2":
        notes.append(
            "If R2 publishing fails, check Cloudflare R2 credentials, bucket, prefix, and object permissions."
        )
    if report["run_identity"]["overwrite"]:
        notes.append("Overwrite was enabled only for semantic chunk outputs.")
    else:
        notes.append(
            "If semantic chunk outputs already exist, rerun with --overwrite only when replacing them is intentional."
        )
    return notes


def render_markdown(report):
    run = report["run_identity"]
    details = report["command_details"]
    identity = report["job_identity"]
    summary = report["processing_summary"]
    lines = [
        "# Gurubodh generate-chunks Audit Report",
        "",
        "## Run Identity",
        "",
        f"- Status: {run['status']}",
        f"- Started at: {run['started_at']}",
        f"- Completed at: {run['completed_at']}",
        f"- Entry point: `{run['entry_point']}`",
        f"- Config path: `{run['config_path']}`",
        f"- Source backend: `{run['source_backend']}`",
        f"- Destination backend: `{run['destination_backend']}`",
        f"- Overwrite: `{run['overwrite']}`",
        f"- Source revision: `{run['build_provenance']['source_revision'] or 'unavailable'}`",
        f"- Provenance source: `{run['build_provenance']['source']}`",
        f"- Image revision: `{run['build_provenance']['image_revision'] or 'not an image run'}`",
        f"- Model revision: `{identity['chunking_model']['model_revision']}`",
        f"- Language: `{identity['language']}`",
        f"- Candidate manifest SHA-256: `{identity['source_candidate_manifest']['sha256'] or 'unavailable'}`",
        "",
        "## Processing Summary",
        "",
        f"- Source chapters: {summary['source_chapter_count']}",
        f"- Processed chapters: {summary['processed_chapter_count']}",
        f"- Skipped chapters: {summary['skipped_chapter_count']}",
        f"- Failed chapters: {summary['failed_chapter_count']}",
        f"- Chunk artifacts: {summary['chunk_artifacts_written']}",
        f"- Total chunks: {summary['total_chunk_count']}",
        f"- Estimated tokens: {summary['total_estimated_token_count']}",
        f"- Publication status: {summary['publication_status']}",
        "",
        "## Per-Chapter Audit",
        "",
    ]
    if details["chapters"]:
        lines.append(
            "| Chapter | Content key | Source text | Chunk artifact | Chunks | Tokens | Status |"
        )
        lines.append("| --- | --- | --- | --- | ---: | ---: | --- |")
        for chapter in details["chapters"]:
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
    if report["failure"]:
        lines.extend(
            [
                "",
                "## Failure",
                "",
                f"- Stage: `{report['failure']['stage']}`",
                f"- Error type: `{report['failure']['error_type']}`",
                f"- Code: `{report['failure']['code']}`",
                f"- Message: {report['failure']['message']}",
            ]
        )
    lines.extend(["", "## Publish Audit", ""])
    for key, value in report["publication"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Operator Notes", ""])
    for note in details["operator_notes"]:
        lines.append(f"- {note}")
    return "\n".join(lines)


class GenerateChunksAuditWriter:
    """Assemble chunk-specific content and delegate all writes to AuditWriter."""

    def __init__(
        self,
        context,
        config_path,
        config,
        entry_point,
        overwrite,
        destination_subject,
    ):
        self.config = config
        self.destination_subject = Path(destination_subject)
        audit_context = AuditContext.create(
            COMMAND_NAME,
            entry_point,
            context.root,
            config_path=config_path,
            config=config,
            overwrite=overwrite,
        )
        paths = report_paths(
            self.destination_subject,
            report_basename(audit_context),
            COMMAND_NAME,
        )
        self.writer = AuditWriter(
            audit_context,
            paths,
            lambda audit_paths: destination_report_references(
                config, CHUNKS_REPORT_DIR, audit_paths
            ),
        )

    @property
    def paths(self):
        return self.writer.paths

    @property
    def references(self):
        return self.writer.references

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
        destination = Path(destination_subject or self.destination_subject)
        details = {
            "chapters": result["chapters"],
            "output_location": str(
                destination / "chapters" / SEMANTIC_CHUNKS_OUTPUT_DIR
            ),
            "operator_notes": [],
        }
        report = self.writer.build_envelope(
            status=status,
            job_identity=job_identity(self.config, candidate_manifest, destination),
            processing_summary=processing_summary(result, publication),
            lifecycle=lifecycle,
            publication=publication,
            failure=failure,
            command_details=details,
        )
        details["operator_notes"] = operator_notes(report)
        result = self.writer.write(
            status=status,
            job_identity=report["job_identity"],
            processing_summary=report["processing_summary"],
            lifecycle=lifecycle,
            publication=publication,
            failure=failure,
            command_details=details,
            renderer=render_markdown,
        )
        if announce:
            print_report_locations(COMMAND_NAME, result.paths)
        return result
