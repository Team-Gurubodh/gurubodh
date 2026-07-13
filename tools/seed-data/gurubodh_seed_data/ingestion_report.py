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


@dataclass(frozen=True)
class GlossaryStage2Report:
    mode: str
    sanatan_records: int = 0
    prabodhan_records: int = 0
    targets: tuple[str, ...] = ()
    preflight_passed: int = 0
    preflight_failed: int = 0
    conflicts: int = 0
    blocked_records: int = 0
    messages: tuple[str, ...] = ()


@dataclass(frozen=True)
class GlossaryStage3Report:
    mode: str
    sanatan_records: int = 0
    prabodhan_records: int = 0
    targets: tuple[str, ...] = ()
    to_create: int = 0
    to_update: int = 0
    already_matching: int = 0
    conflicts: int = 0
    blocked_records: int = 0
    skipped_fields: tuple[str, ...] = ()
    publish_actions: int = 0
    messages: tuple[str, ...] = ()


@dataclass(frozen=True)
class TargetPlanReport:
    mode: str
    target: str
    display_name: str
    workflow: str
    collection_type: str
    plural_api_id: str
    artifact_path: str = "not loaded"
    record_count: int = 0
    preflight_passed: int = 0
    preflight_failed: int = 0
    to_create: int = 0
    to_update: int = 0
    already_matching: int = 0
    conflicts: int = 0
    blocked_records: int = 0
    skipped_fields: tuple[str, ...] = ()
    publish_actions: int = 0
    messages: tuple[str, ...] = ()


def build_target_plan_report(
    mode,
    artifact_result,
    preflight_result,
    target_plan,
    applied=False,
):
    target = artifact_result.target
    artifact = artifact_result.artifact
    messages = [
        (
            f"Task 13 Stage 4 applied {target.display_name} ingestion."
            if applied
            else f"Task 13 Stage 3 planned {target.display_name} ingestion."
        ),
    ]
    has_blockers = bool(
        artifact_result.errors
        or preflight_result.errors
        or target_plan.errors
        or target_plan.conflicts
        or target_plan.blocked_records
    )
    if applied:
        messages.append("Apply completed; this report shows the post-apply plan.")
        if target_plan.to_create or target_plan.to_update or target_plan.publish_actions:
            messages.append("Post-apply verification still has pending write or publish actions.")
    elif mode.can_write and has_blockers:
        messages.append("Apply mode requested; writes are blocked by the reported issues.")
    elif mode.can_write:
        messages.append("Apply mode requested; writes are ready to run.")
    else:
        messages.append("Dry-run only; no Strapi writes were performed.")
    messages.extend(artifact_result.errors)
    messages.extend(preflight_result.errors)
    messages.extend(target_plan.errors)
    messages.extend(target_plan.messages)
    if target.key == "subject" and target_plan.blocked_records:
        messages.append(
            "Subject planning is blocked by Category dependencies; run the Category workflow first."
        )

    return TargetPlanReport(
        mode=mode.name,
        target=target.key,
        display_name=target.display_name,
        workflow=target.workflow,
        collection_type=target.collection_type,
        plural_api_id=target.plural_api_id,
        artifact_path=artifact.path if artifact else "not loaded",
        record_count=artifact.record_count if artifact else 0,
        preflight_passed=sum(1 for check in preflight_result.checks if check.passed),
        preflight_failed=sum(1 for check in preflight_result.checks if not check.passed),
        to_create=target_plan.to_create,
        to_update=target_plan.to_update,
        already_matching=target_plan.already_matching,
        conflicts=(
            len(artifact_result.errors)
            + len(preflight_result.errors)
            + len(target_plan.errors)
            + target_plan.conflicts
        ),
        blocked_records=target_plan.blocked_records,
        skipped_fields=_target_skipped_fields(target.key),
        publish_actions=target_plan.publish_actions,
        messages=tuple(messages),
    )


def _target_skipped_fields(target_key):
    if target_key in ("category", "subject"):
        return ("desired_status",)
    return ("source.key", "strapi.collection_type")


def build_glossary_stage2_report(mode, artifact_result, preflight_result):
    sanatan_records = 0
    prabodhan_records = 0
    targets = []
    for artifact in artifact_result.artifacts:
        if artifact.source_key == "sanatan-glossary":
            sanatan_records = artifact.record_count
        elif artifact.source_key == "prabodhan-glossary":
            prabodhan_records = artifact.record_count
        targets.append(
            f"{artifact.collection_type} -> {artifact.plural_api_id}"
        )

    messages = [
        "Stage 2 glossary preflight loaded artifacts and ran read-only endpoint checks.",
        "Glossary create, update, and publish planning is intentionally deferred until Stage 3.",
        "No Strapi writes were performed.",
    ]

    return GlossaryStage2Report(
        mode=mode.name,
        sanatan_records=sanatan_records,
        prabodhan_records=prabodhan_records,
        targets=tuple(targets),
        preflight_passed=sum(1 for check in preflight_result.checks if check.passed),
        preflight_failed=sum(1 for check in preflight_result.checks if not check.passed),
        conflicts=len(artifact_result.errors) + len(preflight_result.errors),
        blocked_records=sanatan_records + prabodhan_records,
        messages=tuple(messages),
    )


def build_glossary_stage3_report(
    mode,
    artifact_result,
    preflight_result,
    glossary_plan,
    applied=False,
):
    sanatan_records = 0
    prabodhan_records = 0
    targets = []
    for artifact in artifact_result.artifacts:
        if artifact.source_key == "sanatan-glossary":
            sanatan_records = artifact.record_count
        elif artifact.source_key == "prabodhan-glossary":
            prabodhan_records = artifact.record_count
        targets.append(
            f"{artifact.collection_type} -> {artifact.plural_api_id}"
        )

    messages = [
        "Stage 4 glossary adapter planned Sanatan Glossary and Prabodhan Glossary ingestion.",
    ]
    if applied:
        messages.append("Glossary apply completed; this report shows the post-apply plan.")
    elif mode.can_write:
        messages.append("Apply mode requested; writes are ready to run.")
    else:
        messages.append("Dry-run only; no Strapi writes were performed.")
    messages.extend(artifact_result.errors)
    messages.extend(preflight_result.errors)
    messages.extend(glossary_plan.messages)

    return GlossaryStage3Report(
        mode=mode.name,
        sanatan_records=sanatan_records,
        prabodhan_records=prabodhan_records,
        targets=tuple(targets),
        to_create=glossary_plan.to_create,
        to_update=glossary_plan.to_update,
        already_matching=glossary_plan.already_matching,
        conflicts=(
            len(artifact_result.errors)
            + len(preflight_result.errors)
            + glossary_plan.conflicts
        ),
        blocked_records=glossary_plan.blocked_records,
        skipped_fields=("source.key", "strapi.collection_type"),
        publish_actions=glossary_plan.publish_actions,
        messages=tuple(messages),
    )


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


def render_target_plan_report(report):
    lines = [
        "Seed-Data Target Plan Report",
        f"Mode: {report.mode}",
        "",
        "Target",
        f"Key: {report.target}",
        f"Display name: {report.display_name}",
        f"Workflow: {report.workflow}",
        f"Collection: {report.collection_type}",
        f"Plural API ID: {report.plural_api_id}",
        "",
        "Artifact",
        f"Path: {report.artifact_path}",
        f"Records: {report.record_count}",
        "",
        "Preflight Summary",
        f"Checks passed: {report.preflight_passed}",
        f"Checks failed: {report.preflight_failed}",
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


def render_glossary_report(report):
    lines = [
        "Glossary Seed-Data Preflight Report",
        f"Mode: {report.mode}",
        "",
        "Artifacts",
        f"Sanatan Glossary records: {report.sanatan_records}",
        f"Prabodhan Glossary records: {report.prabodhan_records}",
        "",
        "Targets",
    ]
    if report.targets:
        lines.extend(f"- {target}" for target in report.targets)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "Preflight Summary",
            f"Checks passed: {report.preflight_passed}",
            f"Checks failed: {report.preflight_failed}",
            f"Conflicts: {report.conflicts}",
            f"Blocked records: {report.blocked_records}",
        ]
    )
    if report.messages:
        lines.append("")
        lines.append("Messages")
        lines.extend(f"- {message}" for message in report.messages)
    return "\n".join(lines)


def render_glossary_plan_report(report):
    lines = [
        "Glossary Seed-Data Ingestion Report",
        f"Mode: {report.mode}",
        "",
        "Artifacts",
        f"Sanatan Glossary records: {report.sanatan_records}",
        f"Prabodhan Glossary records: {report.prabodhan_records}",
        "",
        "Targets",
    ]
    if report.targets:
        lines.extend(f"- {target}" for target in report.targets)
    else:
        lines.append("- none")
    lines.extend(
        [
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
    )
    if report.messages:
        lines.append("")
        lines.append("Messages")
        lines.extend(f"- {message}" for message in report.messages)
    return "\n".join(lines)
