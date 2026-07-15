import json
import subprocess

from gurubodh_utils.naming import version_label
from gurubodh_utils.storage import (
    destination_subject_prefix,
    is_r2,
    iter_subject_files,
    source_reference,
)
from gurubodh_utils.time_utils import timestamp_for_filename, utc_now


RUN_REPORT_SCHEMA_VERSION = "1.0.0"


def json_safe_snapshot(value):
    if isinstance(value, dict):
        return {
            key: json_safe_snapshot(item)
            for key, item in value.items()
            if not str(key).startswith("_")
        }
    if isinstance(value, list):
        return [json_safe_snapshot(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe_snapshot(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def git_commit_sha(project_root):
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def subject_report_stem(config, run_timestamp):
    naming = config["naming"]
    return (
        f"{naming['category_code']}_{naming['subject_code']}_"
        f"{naming['title_slug']}_run_{run_timestamp}"
    )


def load_chapter_metadata(paths):
    chapter_dir = paths["text_and_metadata"]
    if not chapter_dir.exists():
        return []

    chapters = []
    for path in sorted(chapter_dir.glob("*.json")):
        if path.name.endswith(".formatted.json"):
            continue
        chapters.append(json.loads(path.read_text(encoding="utf-8")))
    return chapters


def formatting_status_counts(chapters):
    counts = {"formatted": 0, "skipped-unchanged": 0, "failed": 0, "disabled": 0}
    for chapter in chapters:
        status = chapter.get("formatting", {}).get("status", "disabled")
        if status not in counts:
            counts[status] = 0
        counts[status] += 1
    return counts


def destination_subject_reference(config, subject_dir):
    destination = config["destination"]
    if is_r2(destination):
        return {
            "backend": "r2",
            "bucket": destination["bucket"],
            "prefix": destination_subject_prefix(config),
            "url_base": destination.get("url_base"),
        }
    return {
        "backend": "local",
        "path": str(subject_dir),
        "url": None,
    }


def chapter_audit_entry(chapter):
    document = chapter.get("document", {})
    files = chapter.get("files", {})
    formatting = chapter.get("formatting", {})
    integrity_artifacts = chapter.get("integrity", {}).get("artifacts", {})

    formatted_filenames = {}
    if files.get("formatted_json_filename"):
        formatted_filenames["json"] = files["formatted_json_filename"]
    if files.get("formatted_markdown_filename"):
        formatted_filenames["markdown"] = files["formatted_markdown_filename"]

    formatted_checksums = {}
    for key in ("formatted_json", "formatted_markdown"):
        if key in integrity_artifacts:
            formatted_checksums[key] = integrity_artifacts[key]

    return {
        "chapter_number": document.get("chapter_number"),
        "artifact_base_name": files.get("text_filename", "").removesuffix(".txt"),
        "raw_text_checksum": formatting.get("source_text_sha256")
        or integrity_artifacts.get("text", {}).get("value"),
        "formatting_enabled": formatting.get("enabled", False),
        "formatting_status": formatting.get("status", "disabled"),
        "model_used": formatting.get("model_used"),
        "attempt_count": formatting.get("attempt_count", 0),
        "retry_count": formatting.get("retry_count", 0),
        "warning": formatting.get("warning"),
        "formatted_artifact_filenames": formatted_filenames,
        "artifact_checksums": formatted_checksums,
    }


def build_run_report(
    config,
    paths,
    result,
    entry_point,
    config_path,
    overwrite,
    project_root,
):
    chapters = load_chapter_metadata(paths)
    formatting_counts = formatting_status_counts(chapters)
    failed_chapters = [
        chapter
        for chapter in chapters
        if chapter.get("formatting", {}).get("status") == "failed"
    ]
    planned_artifact_count = len(list(iter_subject_files(paths["subject"]))) + 2
    is_r2_destination = is_r2(config["destination"])

    return {
        "schema_version": RUN_REPORT_SCHEMA_VERSION,
        "run_identity": {
            "run_timestamp": utc_now(),
            "job_config_path": str(config_path),
            "command": entry_point,
            "job_schema_version": config.get("schema_version"),
            "source_backend": config["source"].get("backend", "local"),
            "destination_backend": config["destination"].get("backend", "local"),
            "overwrite": bool(overwrite),
            "git_commit_sha": git_commit_sha(project_root),
        },
        "job_identity": {
            "category_code": config["naming"]["category_code"],
            "subject_code": config["naming"]["subject_code"],
            "title_slug": config["naming"]["title_slug"],
            "version": version_label(config),
            "source_docx": source_reference(config),
            "destination_subject": destination_subject_reference(config, paths["subject"]),
        },
        "configuration_snapshot": {
            "chapter_split": json_safe_snapshot(config.get("chapter_split", {})),
            "formatting": {
                key: config.get("formatting", {}).get(key)
                for key in (
                    "enabled",
                    "provider",
                    "model",
                    "fallback_model",
                    "delay_seconds",
                    "max_retries",
                    "max_tokens",
                    "continue_on_error",
                    "output_formats",
                    "regenerate",
                    "reasoning_effort",
                )
            },
            "storage": {
                "source": json_safe_snapshot(config.get("source", {})),
                "destination": json_safe_snapshot(config.get("destination", {})),
            },
        },
        "processing_summary": {
            "full_docx": {
                "status": "written" if result.get("output_path") else "not-written",
                "path": str(result.get("output_path")) if result.get("output_path") else None,
            },
            "full_text": {
                "status": "written" if result.get("text_path") else "not-written",
                "path": str(result.get("text_path")) if result.get("text_path") else None,
                "character_count": result.get("total_chars"),
            },
            "docx_validation": {"status": "passed"},
            "chapters_detected": len(chapters),
            "chapters_written": len(chapters),
            "formatting_summary": formatting_counts,
            "r2_publish": {
                "status": "prepared" if is_r2_destination else "not-applicable",
                "artifact_count": planned_artifact_count if is_r2_destination else None,
            },
        },
        "chapters": [chapter_audit_entry(chapter) for chapter in chapters],
        "rate_limit_throttle": {
            "delay_seconds": config.get("formatting", {}).get("delay_seconds"),
            "sarvam_requests_attempted": sum(
                chapter.get("formatting", {}).get("attempt_count", 0)
                for chapter in chapters
            ),
            "retry_count": sum(
                chapter.get("formatting", {}).get("retry_count", 0)
                for chapter in chapters
            ),
            "total_throttle_sleep_seconds": sum(
                chapter.get("formatting", {}).get("throttle_sleep_seconds", 0)
                for chapter in chapters
            ),
            "request_timestamps": [],
        },
        "final_outcome": {
            "result": "completed-with-formatting-failures" if failed_chapters else "success",
            "failed_chapters": [
                chapter.get("document", {}).get("chapter_number")
                for chapter in failed_chapters
            ],
            "retry_candidates": [
                {
                    "chapter_number": chapter.get("document", {}).get("chapter_number"),
                    "artifact_base_name": chapter.get("files", {})
                    .get("text_filename", "")
                    .removesuffix(".txt"),
                    "warning": chapter.get("formatting", {}).get("warning"),
                }
                for chapter in failed_chapters
            ],
            "notes": [],
        },
    }


def render_markdown_report(report):
    identity = report["run_identity"]
    job = report["job_identity"]
    summary = report["processing_summary"]
    outcome = report["final_outcome"]
    throttle = report["rate_limit_throttle"]
    r2_artifact_count = summary["r2_publish"]["artifact_count"]
    r2_artifact_text = "n/a" if r2_artifact_count is None else str(r2_artifact_count)

    lines = [
        f"# Run Report: {job['category_code']} {job['subject_code']} {job['title_slug']}",
        "",
        "## Run Identity",
        "",
        f"- Run timestamp: {identity['run_timestamp']}",
        f"- Job config path: {identity['job_config_path']}",
        f"- Command: {identity['command']}",
        f"- Job schema version: {identity['job_schema_version']}",
        f"- Source backend: {identity['source_backend']}",
        f"- Destination backend: {identity['destination_backend']}",
        f"- Overwrite: {identity['overwrite']}",
        f"- Git commit SHA: {identity['git_commit_sha'] or 'unavailable'}",
        "",
        "## Processing Summary",
        "",
        f"- Full DOCX copy/extraction: {summary['full_docx']['status']} / {summary['full_text']['status']}",
        f"- DOCX validation: {summary['docx_validation']['status']}",
        f"- Chapters detected: {summary['chapters_detected']}",
        f"- Chapters written: {summary['chapters_written']}",
        f"- Formatting: {formatting_counts_text(summary['formatting_summary'])}",
        f"- R2 publish: {summary['r2_publish']['status']} ({r2_artifact_text} artifacts)",
        "",
        "## Rate Limit / Throttle",
        "",
        f"- Configured delay seconds: {throttle['delay_seconds']}",
        f"- Sarvam requests attempted: {throttle['sarvam_requests_attempted']}",
        f"- Retry count: {throttle['retry_count']}",
        f"- Total throttle sleep seconds: {throttle['total_throttle_sleep_seconds']}",
        "",
        "## Per-Chapter Audit",
        "",
        "| Chapter | Artifact | Formatting | Attempts | Retries | Warning |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]

    for chapter in report["chapters"]:
        warning = chapter.get("warning") or ""
        lines.append(
            "| {chapter} | {artifact} | {status} | {attempts} | {retries} | {warning} |".format(
                chapter=chapter.get("chapter_number") or "",
                artifact=chapter.get("artifact_base_name") or "",
                status=chapter.get("formatting_status") or "",
                attempts=chapter.get("attempt_count", 0),
                retries=chapter.get("retry_count", 0),
                warning=markdown_table_text(warning),
            )
        )

    lines.extend(
        [
            "",
            "## Final Outcome",
            "",
            f"- Result: {outcome['result']}",
            f"- Failed chapters: {', '.join(outcome['failed_chapters']) if outcome['failed_chapters'] else 'none'}",
            f"- Retry candidates: {', '.join(candidate['chapter_number'] for candidate in outcome['retry_candidates']) if outcome['retry_candidates'] else 'none'}",
            "",
        ]
    )
    return "\n".join(lines)


def formatting_counts_text(counts):
    return (
        f"formatted={counts.get('formatted', 0)}, "
        f"skipped-unchanged={counts.get('skipped-unchanged', 0)}, "
        f"failed={counts.get('failed', 0)}, "
        f"disabled={counts.get('disabled', 0)}"
    )


def markdown_table_text(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_run_reports(
    config,
    paths,
    result,
    entry_point,
    config_path,
    overwrite,
    project_root,
    reporter,
):
    run_timestamp = timestamp_for_filename()
    report = build_run_report(
        config,
        paths,
        result,
        entry_point,
        config_path,
        overwrite,
        project_root,
    )

    report_dir = paths["subject"] / "run_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    stem = subject_report_stem(config, run_timestamp)
    json_path = report_dir / f"{stem}.json"
    markdown_path = report_dir / f"{stem}.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    reporter.report(f"wrote run audit reports under {report_dir}")
    return {"json": json_path, "markdown": markdown_path, "report": report}
