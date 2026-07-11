from dataclasses import dataclass


@dataclass(frozen=True)
class IngestionReport:
    mode: str
    category_records: int = 0
    subject_records: int = 0
    to_create: int = 0
    to_update: int = 0
    already_matching: int = 0
    conflicts: int = 0
    blocked_records: int = 0
    skipped_fields: tuple[str, ...] = ()
    publish_actions: int = 0
    messages: tuple[str, ...] = ()


def build_stage2_report(mode, artifact_result, preflight_result):
    category_records = 0
    subject_records = 0
    for artifact in artifact_result.artifacts:
        if artifact.workflow == "category":
            category_records = artifact.record_count
        elif artifact.workflow == "subject":
            subject_records = artifact.record_count

    messages = [
        "Stage 2 foundation loaded artifacts and ran read-only preflight.",
        "Category and Subject adapters are intentionally not implemented until later stages.",
    ]
    if mode.can_write:
        messages.append("Apply mode was requested, but Stage 2 has no write planner.")

    return IngestionReport(
        mode=mode.name,
        category_records=category_records,
        subject_records=subject_records,
        conflicts=len(artifact_result.errors) + len(preflight_result.errors),
        blocked_records=category_records + subject_records,
        skipped_fields=("desired_status",),
        messages=tuple(messages),
    )


def render_report(report):
    lines = [
        "Seed-Data Ingestion Report",
        f"Mode: {report.mode}",
        "",
        "Artifacts",
        f"Category records: {report.category_records}",
        f"Subject records: {report.subject_records}",
        "",
        "Plan Summary",
        f"Records to create: {report.to_create}",
        f"Records to update: {report.to_update}",
        f"Records already matching: {report.already_matching}",
        f"Conflicts: {report.conflicts}",
        f"Blocked records: {report.blocked_records}",
        f"Skipped fields: {', '.join(report.skipped_fields) if report.skipped_fields else 'none'}",
        f"Publish actions: {report.publish_actions}",
    ]
    if report.messages:
        lines.append("")
        lines.append("Messages")
        lines.extend(f"- {message}" for message in report.messages)
    return "\n".join(lines)
