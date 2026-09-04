"""Command-specific audit content for candidate-bound DOCX generation."""

from pathlib import Path

from gurubodh.audit import (
    AuditContext,
    AuditWriter,
    destination_report_references,
    print_report_locations,
    report_basename,
    report_paths,
)
from gurubodh.constants import (
    DOCX_FORMATTING_CONTRACT_VERSION,
    DOCX_TITLE_TEMPLATE_ID,
    DOCX_TITLE_TEMPLATE_VERSION,
)
from gurubodh.storage import (
    DOCX_REPORT_DIR,
    is_r2,
    optional_url,
    subject_artifact_prefix,
)


COMMAND_NAME = "generate-docx"


def render_markdown(report):
    run = report["run_identity"]
    summary = report["processing_summary"]
    details = report["command_details"]
    lines = [
        "# Gurubodh generate-docx Audit Report",
        "",
        f"- Status: `{run['status']}`",
        f"- Started at: `{run['started_at']}`",
        f"- Completed at: `{run['completed_at']}`",
        f"- Source backend: `{run['source_backend']}`",
        f"- Destination backend: `{run['destination_backend']}`",
        f"- Overwrite: `{run['overwrite']}`",
        f"- Category: `{report['job_identity']['category_code']}`",
        f"- Subject: `{report['job_identity']['subject_code']}`",
        f"- Language: `{report['job_identity']['language']}`",
        f"- Candidate manifest SHA-256: `{details['source_candidate_manifest'].get('sha256') or 'unavailable'}`",
        f"- Formatting contract: `{details['contracts']['formatting']}`",
        f"- Title contract: `{details['contracts']['title_template_id']}` v{details['contracts']['title_template_version']}",
        "",
        "## Processing Summary",
        "",
        f"- Source chapters: {summary['source_chapter_count']}",
        f"- Generated DOCX files: {summary['generated_docx_count']}",
        f"- Validated DOCX files: {summary['validated_docx_count']}",
        f"- Failed chapters: {summary['failed_chapter_count']}",
        f"- Publication: `{report['publication']['status']}`",
        "",
        "## Per-Chapter Audit",
        "",
    ]
    if details["chapters"]:
        lines.extend(
            [
                "| Chapter | Content key | Generated title | DOCX file | Status |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for chapter in details["chapters"]:
            lines.append(
                f"| {chapter['chapter_number']} | `{chapter['content_key']}` | "
                f"{chapter['generated_title']} | {chapter['docx_filename']} | {chapter['status']} |"
            )
    else:
        lines.append("No chapter DOCX files were generated.")
    if report["failure"]:
        lines.extend(
            [
                "",
                "## Failure",
                "",
                f"- Stage: `{report['failure']['stage']}`",
                f"- Code: `{report['failure']['code']}`",
                f"- Message: {report['failure']['message']}",
            ]
        )
    return "\n".join(lines)


class GenerateDocxAuditWriter:
    """Assemble DOCX-specific content and delegate all writes to AuditWriter."""

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
                config, DOCX_REPORT_DIR, audit_paths
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
        chapters,
        publication,
        failure=None,
        lifecycle=None,
        announce=True,
    ):
        naming = self.config["naming"]
        manifest = candidate_manifest or {}
        result = self.writer.write(
            status=status,
            job_identity={
                **naming,
                "source_subject": self._subject_reference(self.config["source"]),
                "destination_subject": self._subject_reference(
                    self.config["destination"]
                ),
            },
            processing_summary={
                "source_chapter_count": len(manifest.get("chapters", [])),
                "generated_docx_count": len(
                    [chapter for chapter in chapters if chapter.get("docx_sha256")]
                ),
                "validated_docx_count": len(
                    [
                        chapter
                        for chapter in chapters
                        if chapter.get("status") == "succeeded"
                    ]
                ),
                "failed_chapter_count": len(
                    [
                        chapter
                        for chapter in chapters
                        if chapter.get("status") == "failed"
                    ]
                ),
            },
            lifecycle=lifecycle,
            publication=publication,
            failure=failure,
            command_details={
                "source_candidate_manifest": {
                    "reference": manifest.get("reference"),
                    "sha256": manifest.get("sha256"),
                },
                "contracts": {
                    "formatting": DOCX_FORMATTING_CONTRACT_VERSION,
                    "title_template_id": DOCX_TITLE_TEMPLATE_ID,
                    "title_template_version": DOCX_TITLE_TEMPLATE_VERSION,
                },
                "chapters": chapters,
            },
            renderer=render_markdown,
        )
        if announce:
            print_report_locations(COMMAND_NAME, result.paths)
        return result

    @staticmethod
    def _subject_reference(section):
        if is_r2(section):
            prefix = subject_artifact_prefix(section)
            return {
                "backend": "r2",
                "bucket": section["bucket"],
                "prefix": prefix,
                "url": optional_url(section.get("url_base"), prefix.rstrip("/")),
            }
        return {
            "backend": "local",
            "path": str(
                Path(section["root_dir"]).expanduser() / section["subject_dir"]
            ),
            "url": None,
        }
