"""Audit reports for candidate-manifest-bound DOCX generation."""

from datetime import datetime, timezone
from pathlib import Path

from gurubodh.audit import AuditReportBuilder, print_report_locations, report_paths, write_report
from gurubodh.constants import (
    DOCX_FORMATTING_CONTRACT_VERSION,
    DOCX_TITLE_TEMPLATE_ID,
    DOCX_TITLE_TEMPLATE_VERSION,
)
from gurubodh.storage import DOCX_REPORT_DIR, destination_artifact_reference, is_r2, optional_url, subject_artifact_prefix


COMMAND_NAME = "generate-docx"


def _markdown(report):
    run = report["run_identity"]
    summary = report["processing_summary"]
    lines = [
        "# Gurubodh generate-docx Audit Report",
        "",
        f"- Status: `{run['status']}`",
        f"- Run timestamp: `{run['run_timestamp']}`",
        f"- Source backend: `{run['source_backend']}`",
        f"- Destination backend: `{run['destination_backend']}`",
        f"- Overwrite: `{run['overwrite']}`",
        f"- Category: `{report['job_identity']['category_code']}`",
        f"- Subject: `{report['job_identity']['subject_code']}`",
        f"- Language: `{report['job_identity']['language']}`",
        f"- Candidate manifest SHA-256: `{report['source_candidate_manifest'].get('sha256') or 'unavailable'}`",
        f"- Formatting contract: `{report['contracts']['formatting']}`",
        f"- Title contract: `{report['contracts']['title_template_id']}` v{report['contracts']['title_template_version']}",
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
    if report["chapters"]:
        lines.extend(
            [
                "| Chapter | Content key | Generated title | DOCX file | Status |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for chapter in report["chapters"]:
            lines.append(
                f"| {chapter['chapter_number']} | `{chapter['content_key']}` | "
                f"{chapter['generated_title']} | {chapter['docx_filename']} | {chapter['status']} |"
            )
    else:
        lines.append("No chapter DOCX files were generated.")
    if report.get("failure"):
        lines.extend(
            [
                "",
                "## Failure",
                "",
                f"- Stage: `{report['failure']['stage']}`",
                f"- Message: {report['failure']['message']}",
            ]
        )
    return "\n".join(lines)


class GenerateDocxAuditWriter:
    def __init__(self, context, config_path, config, entry_point, overwrite, destination_subject):
        self.config = config
        self.destination_subject = Path(destination_subject)
        self.builder = AuditReportBuilder(COMMAND_NAME, entry_point, context, config_path, config, overwrite)
        unique_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        basename = f"generate-docx-{unique_timestamp}"
        self.paths = report_paths(self.destination_subject, basename, COMMAND_NAME)

    def references(self):
        return {
            "json": destination_artifact_reference(self.config, DOCX_REPORT_DIR / self.paths["json"].name),
            "markdown": destination_artifact_reference(self.config, DOCX_REPORT_DIR / self.paths["markdown"].name),
        }

    def build(
        self,
        status,
        candidate_manifest,
        chapters,
        publication,
        failure=None,
        lifecycle=None,
    ):
        naming = self.config["naming"]
        manifest = candidate_manifest or {}
        return {
            "schema_version": "1.0.0",
            "run_identity": self.builder.run_identity(status, error=failure),
            "job_identity": {
                **naming,
                "source_subject": self._subject_reference(self.config["source"]),
                "destination_subject": self._subject_reference(self.config["destination"]),
            },
            "configuration_snapshot": self.builder.safe_config_snapshot(),
            "source_candidate_manifest": {
                "reference": manifest.get("reference"),
                "sha256": manifest.get("sha256"),
            },
            "contracts": {
                "formatting": DOCX_FORMATTING_CONTRACT_VERSION,
                "title_template_id": DOCX_TITLE_TEMPLATE_ID,
                "title_template_version": DOCX_TITLE_TEMPLATE_VERSION,
            },
            "processing_summary": {
                "source_chapter_count": len(manifest.get("chapters", [])),
                "generated_docx_count": len([chapter for chapter in chapters if chapter.get("docx_sha256")]),
                "validated_docx_count": len([chapter for chapter in chapters if chapter.get("status") == "succeeded"]),
                "failed_chapter_count": len(
                    [chapter for chapter in chapters if chapter.get("status") == "failed"]
                ),
            },
            "chapters": chapters,
            "publication": publication,
            "lifecycle": lifecycle,
            "failure": failure,
            "report_files": self.references(),
        }

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
        report = self.build(
            status,
            candidate_manifest,
            chapters,
            publication,
            failure,
            lifecycle,
        )
        write_report(self.paths, report, _markdown(report))
        if announce:
            print_report_locations(COMMAND_NAME, self.paths)
        return report

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
            "path": str(Path(section["root_dir"]).expanduser() / section["subject_dir"]),
            "url": None,
        }
