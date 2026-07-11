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


def build_stage3_category_report(mode, artifact_result, category_plan, applied=False):
    category_records = 0
    subject_records = 0
    for artifact in artifact_result.artifacts:
        if artifact.workflow == "category":
            category_records = artifact.record_count
        elif artifact.workflow == "subject":
            subject_records = artifact.record_count

    messages = [
        "Stage 3 Category adapter planned Category ingestion.",
        "Subject adapter is intentionally deferred until Stage 4.",
    ]
    if applied:
        messages.append("Category apply completed against Strapi.")
    elif mode.can_write:
        messages.append("Apply mode requested; Category writes are ready to run.")
    else:
        messages.append("Dry-run only; no Strapi writes were performed.")
    messages.extend(category_plan.messages)

    return IngestionReport(
        mode=mode.name,
        category_records=category_records,
        subject_records=subject_records,
        to_create=category_plan.to_create,
        to_update=category_plan.to_update,
        already_matching=category_plan.already_matching,
        conflicts=len(artifact_result.errors) + category_plan.conflicts,
        blocked_records=subject_records + category_plan.conflicts,
        skipped_fields=("desired_status",),
        publish_actions=category_plan.publish_actions,
        messages=tuple(messages),
    )


def build_stage4_ingestion_report(
    mode,
    artifact_result,
    category_plan,
    subject_plan,
    applied=False,
):
    category_records = 0
    subject_records = 0
    for artifact in artifact_result.artifacts:
        if artifact.workflow == "category":
            category_records = artifact.record_count
        elif artifact.workflow == "subject":
            subject_records = artifact.record_count

    messages = ["Stage 4 Subject adapter planned Category and Subject ingestion."]
    if applied:
        messages.append("Category and Subject apply completed against Strapi.")
    elif mode.can_write:
        messages.append("Apply mode requested; writes are ready to run.")
    else:
        messages.append("Dry-run only; no Strapi writes were performed.")
    messages.extend(category_plan.messages)
    messages.extend(subject_plan.messages)

    return IngestionReport(
        mode=mode.name,
        category_records=category_records,
        subject_records=subject_records,
        to_create=category_plan.to_create + subject_plan.to_create,
        to_update=category_plan.to_update + subject_plan.to_update,
        already_matching=category_plan.already_matching + subject_plan.already_matching,
        conflicts=len(artifact_result.errors) + category_plan.conflicts + subject_plan.conflicts,
        blocked_records=subject_plan.blocked_records + category_plan.conflicts,
        skipped_fields=("desired_status",),
        publish_actions=category_plan.publish_actions + subject_plan.publish_actions,
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
