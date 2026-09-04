"""Command-specific audit content for resumable subject preparation."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from gurubodh.audit import (
    AuditContext,
    AuditWriter,
    destination_report_references,
    report_basename,
    report_paths,
)
from gurubodh.storage import (
    is_r2,
    subject_artifact_prefix,
)


COMMAND_NAME = "prep-subject"
PREP_REPORT_RELATIVE_DIR = Path("run_reports") / COMMAND_NAME


def render_markdown(report: dict[str, Any]) -> str:
    run = report["run_identity"]
    identity = report["job_identity"]
    subject = identity["subject"]
    details = report["command_details"]
    summary = report["processing_summary"]
    lines = [
        "# Gurubodh prep-subject Run Report",
        "",
        f"- Status: `{run['status']}`",
        f"- Job: `{identity['job_id']}`",
        f"- Run: `{run['run_id']}`",
        f"- Category: `{subject['category_code']}`",
        f"- Subject: `{subject['subject_code']}`",
        f"- Language: `{subject['language']}`",
        f"- Language-specific artifact root: `{subject['artifact_root']}`",
        f"- Proofreading template: `{details['proofreading_locale']['instruction_template']['id']}` "
        f"v{details['proofreading_locale']['instruction_template']['version']} "
        f"(`{details['proofreading_locale']['instruction_template']['sha256']}`)",
        f"- Overwrite: `{run['overwrite']}`",
        f"- Checkpoint artifact contract: `{details['checkpoint_contract_version']}` (five files per chapter)",
        f"- Counts: succeeded `{details['counts']['succeeded']}`, failed `{details['counts']['failed']}`, "
        f"pending `{details['counts']['pending']}`",
        "",
        "## Processing",
        "",
        f"- Source materialization: `{summary['source_materialization_status']}`",
        f"- Source DOCX validation: `{summary['source_docx_validation_status']}`",
        f"- Legacy converter counts: `{json.dumps(summary['legacy_converter_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Converted text nodes: `{summary['converted_text_nodes']}`",
        f"- Converted or extracted characters: `{summary['converted_or_extracted_character_count']}`",
        f"- Chapters detected: `{summary['chapters_detected']}`",
        f"- Unmodified-source snapshots: `{summary['unmodified_source_snapshots']}`",
        f"- Canonical chapters succeeded: `{summary['canonical_chapters_succeeded']}`",
        f"- Proofreading manifest: `{summary['proofreading_manifest_status']}`",
        f"- Chapter content manifest: `{summary['chapter_content_manifest_status']}`",
        "",
        "## Run metrics",
        "",
    ]
    gemini = details["run_metrics"]["gemini_generate_content_requests"]
    lines.append(
        "- Gemini `generate_content` request attempts: "
        f"`{gemini['attempts_total']}` total, `{gemini['attempts_succeeded']}` succeeded, "
        f"`{gemini['attempts_failed']}` failed. {gemini['definition']}"
    )
    r2 = details["run_metrics"]["r2_object_upload_requests"]
    if r2 is not None:
        lines.append(
            "- R2 object-upload request attempts: "
            f"`{r2['attempts_total']}` total, `{r2['attempts_succeeded']}` succeeded, "
            f"`{r2['attempts_failed']}` failed. {r2['definition']}"
        )
        lines.extend(
            [
                "",
                "### R2 upload breakdown",
                "",
                "| Category | Total | Succeeded | Failed |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        lines.extend(
            f"| {category} — {counters['definition']} | {counters['attempts_total']} | "
            f"{counters['attempts_succeeded']} | {counters['attempts_failed']} |"
            for category, counters in r2["breakdown"].items()
        )
    if report["failure"]:
        lines.extend(
            [
                "",
                "## Failure",
                "",
                f"- Stage: `{report['failure']['stage']}`",
                f"- {report['failure']['code']}: {report['failure']['message']}",
            ]
        )
    lines.extend(
        [
            "",
            "## Chapters",
            "",
            "| Chapter | State | Attempts | Outcome |",
            "| --- | --- | ---: | --- |",
        ]
    )
    lines.extend(
        f"| {chapter['chapter_number']} | {chapter['state']} | {chapter['attempt_count']} | {chapter['outcome']} |"
        for chapter in details["chapters"]
    )
    publication = report["publication"]
    lines.extend(
        ["", "## Publication", "", f"- Status: `{publication['status']}`"]
    )
    cleanup = publication.get("obsolete_artifact_cleanup") or {}
    if cleanup:
        docx = cleanup.get("chapter_docx_invalidation") or {}
        full_subject = cleanup.get("legacy_full_subject_cleanup") or {}
        lines.extend(
            [
                f"- Derived chapter DOCX invalidated: `{docx.get('invalidated', False)}`",
                f"- Legacy full_subject removed: `{full_subject.get('invalidated', False)}`",
            ]
        )
    semantic = publication.get("semantic_invalidation")
    if semantic:
        lines.append(
            f"- Semantic chunks invalidated: `{semantic.get('invalidated', False)}`"
        )
    return "\n".join(lines)


class PrepSubjectAuditWriter:
    """Assemble prep-specific content and delegate all writes to AuditWriter."""

    def __init__(
        self,
        project_root: str | Path,
        config,
        config_path,
        entry_point: str,
        overwrite: bool,
        state: dict[str, Any],
        subject_dir: Path,
    ):
        self.config = config
        self.state = deepcopy(state)
        self.subject_dir = Path(subject_dir)
        run = self.state["run"]
        audit_context = AuditContext.create(
            COMMAND_NAME,
            entry_point,
            project_root,
            config_path=config_path,
            config=config,
            overwrite=overwrite,
            run_id=run["run_id"],
            started_at=run.get("last_started_at") or run.get("started_at"),
        )
        paths = report_paths(
            self.subject_dir,
            report_basename(audit_context),
            COMMAND_NAME,
        )
        self.writer = AuditWriter(
            audit_context,
            paths,
            lambda audit_paths: destination_report_references(
                config, PREP_REPORT_RELATIVE_DIR, audit_paths
            ),
        )

    def write(
        self,
        status: str,
        failure: dict[str, Any] | None,
        reused: list[str],
        attempted: list[str],
        run_metrics: dict[str, Any],
        checkpoint_contract_version: int,
    ):
        locale = self.config.locale
        destination = self.config["destination"]
        artifact_root = (
            subject_artifact_prefix(destination)
            if is_r2(destination)
            else str(self.subject_dir)
        )
        publication_details = deepcopy(self.state.get("publication") or {})
        checkpoint_publication_state = publication_details.pop("state", "not_ready")
        publication_status = (
            "failed"
            if failure is not None and failure["stage"] == "publication"
            else checkpoint_publication_state
        )
        publication = {
            "backend": destination.get("backend", "local"),
            "status": publication_status,
            "checkpoint_state": checkpoint_publication_state,
            **publication_details,
        }
        processing_summary = {
            "source_materialization_status": "succeeded",
            "source_docx_validation_status": (
                "succeeded"
                if self.state.get("preparation")
                else "failed_or_not_completed"
            ),
            "legacy_converter_counts": (
                self.state.get("preparation") or {}
            ).get("converter_counts", {}),
            "converted_text_nodes": (self.state.get("preparation") or {}).get(
                "total_nodes", 0
            ),
            "converted_or_extracted_character_count": (
                self.state.get("preparation") or {}
            ).get("total_chars", 0),
            "chapters_detected": (self.state.get("preparation") or {}).get(
                "chapters_detected", 0
            ),
            "unmodified_source_snapshots": len(self.state.get("chapters", [])),
            "canonical_chapters_succeeded": self.state["counts"]["succeeded"],
            "proofreading_manifest_status": (
                "published" if status == "succeeded" else "not_published"
            ),
            "chapter_content_manifest_status": (
                "published_last" if status == "succeeded" else "not_published"
            ),
        }
        details = {
            "proofreading_locale": locale.proofreading_provenance(),
            "counts": deepcopy(self.state["counts"]),
            "run_metrics": deepcopy(run_metrics),
            "chapters": [
                {
                    "chapter_number": chapter["chapter_number"],
                    "state": chapter["state"],
                    "attempt_count": chapter["attempt_count"],
                    "latest_error": chapter.get("latest_error"),
                    "outcome": (
                        "reused_checkpoint"
                        if chapter["chapter_number"] in reused
                        else (
                            "attempted"
                            if chapter["chapter_number"] in attempted
                            else "pending"
                        )
                    ),
                }
                for chapter in self.state.get("chapters", [])
            ],
            "preparation": deepcopy(self.state.get("preparation")),
            "checkpoint_contract_version": checkpoint_contract_version,
            "non_canonical": False,
        }
        return self.writer.write(
            status=status,
            job_identity={
                "job_id": self.state["job_id"],
                "subject": {
                    "category_code": self.config["naming"]["category_code"],
                    "subject_code": self.config["naming"]["subject_code"],
                    "language": locale.language,
                    "artifact_root": artifact_root,
                },
            },
            processing_summary=processing_summary,
            lifecycle={
                "current_state": self.state["state"],
                "transitions": [],
            },
            publication=publication,
            failure=failure,
            command_details=details,
            renderer=render_markdown,
        )
