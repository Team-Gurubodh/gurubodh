import argparse
import sys

from gurubodh_seed_data.category import get_category_source, list_category_sources
from gurubodh_seed_data.category_artifacts import write_category_artifact
from gurubodh_seed_data.glossary import get_glossary_source, list_glossary_sources
from gurubodh_seed_data.glossary_artifacts import write_glossary_artifact
from gurubodh_seed_data.ingestion_mode import IngestionMode
from gurubodh_seed_data.ingestion_report import (
    build_target_plan_report,
    render_target_plan_report,
)
from gurubodh_seed_data.paths import category_paths, glossary_paths, subject_paths
from gurubodh_seed_data.strapi_client import StrapiClient
from gurubodh_seed_data.strapi_config import load_strapi_config
from gurubodh_seed_data.target_ingestion import (
    INGEST_TARGET_REGISTRY,
    TargetIngestionPlan,
    apply_target_ingestion,
    load_target_artifact,
    plan_target_ingestion,
    run_target_preflight,
)
from gurubodh_seed_data.subject import get_subject_source, list_subject_sources
from gurubodh_seed_data.subject_artifacts import write_subject_artifact
from gurubodh_seed_data.validation import (
    validate_category_csv,
    validate_glossary_csv,
    validate_subject_csv,
)
from gurubodh_seed_data.workflows import list_workflows


def _print_table(headers, rows):
    widths = [
        max(len(str(value)) for value in column)
        for column in zip(headers, *rows)
    ]
    header_line = "  ".join(
        str(header).ljust(width) for header, width in zip(headers, widths)
    )
    separator_line = "  ".join("-" * width for width in widths)

    print(header_line)
    print(separator_line)
    for row in rows:
        print("  ".join(str(value).ljust(width) for value, width in zip(row, widths)))


def _print_glossary_sources():
    rows = [
        (source.key, source.label)
        for source in list_glossary_sources()
    ]
    _print_table(("Key", "Name"), rows)


def _print_category_sources():
    rows = [
        (source.key, source.label)
        for source in list_category_sources()
    ]
    _print_table(("Key", "Name"), rows)


def _print_subject_sources():
    rows = [
        (source.key, source.label)
        for source in list_subject_sources()
    ]
    _print_table(("Key", "Name"), rows)


def _print_glossary_paths(source_key=None):
    sources = (
        (get_glossary_source(source_key),)
        if source_key
        else list_glossary_sources()
    )
    rows = []
    for source in sources:
        paths = glossary_paths(source)
        rows.append((paths.source_key, paths.csv_input, paths.json_output))
    _print_table(("Source", "CSV Input", "JSON Output"), rows)


def _print_category_paths(source_key=None):
    sources = (
        (get_category_source(source_key),)
        if source_key
        else list_category_sources()
    )
    rows = []
    for source in sources:
        paths = category_paths(source)
        rows.append((paths.source_key, paths.csv_input, paths.json_output))
    _print_table(("Source", "CSV Input", "JSON Output"), rows)


def _print_subject_paths(source_key=None):
    sources = (
        (get_subject_source(source_key),)
        if source_key
        else list_subject_sources()
    )
    rows = []
    for source in sources:
        paths = subject_paths(source)
        rows.append((paths.source_key, paths.csv_input, paths.json_output))
    _print_table(("Source", "CSV Input", "JSON Output"), rows)


def _print_workflows():
    rows = [
        (workflow.key, workflow.status, workflow.description)
        for workflow in list_workflows()
    ]
    _print_table(("Key", "Status", "Description"), rows)


def _load_strapi_config_from_args(args):
    return load_strapi_config(
        base_url=args.strapi_url,
        api_token=args.strapi_token,
        default_locale=args.default_locale,
        localized_locale=args.localized_locale,
        timeout_seconds=args.timeout_seconds,
    )


def _print_preflight_result(result):
    rows = [
        (check.name, "pass" if check.passed else "fail", check.message)
        for check in result.checks
    ]
    _print_table(("Check", "Result", "Message"), rows)


def _print_validation_issues(title, issues):
    if not issues:
        return

    print()
    print(title)
    rows = [
        (issue.row_number, issue.column, issue.message)
        for issue in issues
    ]
    _print_table(("Row", "Column", "Message"), rows)


def _validate_glossary_source(source_key):
    source = get_glossary_source(source_key)
    result = validate_glossary_csv(source)

    print(f"Source: {result.source_key}")
    print(f"CSV Input: {result.csv_path}")
    print(f"Rows Checked: {result.data_row_count}")
    print(f"Errors: {len(result.errors)}")
    print(f"Warnings: {len(result.warnings)}")

    _print_validation_issues("Errors", result.errors)
    _print_validation_issues("Warnings", result.warnings)

    if result.is_valid:
        print()
        print("Validation passed.")
        return 0

    print()
    print("Validation failed.")
    return 1


def _validate_category_source(source_key):
    source = get_category_source(source_key)
    result = validate_category_csv(source)
    return _print_csv_validation_result(result)


def _validate_subject_source(source_key):
    source = get_subject_source(source_key)
    category_source = get_category_source("categories")
    result = validate_subject_csv(source, category_source)
    return _print_csv_validation_result(result)


def _print_csv_validation_result(result):
    print(f"Source: {result.source_key}")
    print(f"CSV Input: {result.csv_path}")
    print(f"Rows Checked: {result.data_row_count}")
    print(f"Errors: {len(result.errors)}")
    print(f"Warnings: {len(result.warnings)}")

    _print_validation_issues("Errors", result.errors)
    _print_validation_issues("Warnings", result.warnings)

    if result.is_valid:
        print()
        print("Validation passed.")
        return 0

    print()
    print("Validation failed.")
    return 1


def _generate_glossary_artifact(source_key):
    source = get_glossary_source(source_key)
    result = write_glossary_artifact(source)

    print(f"Source: {result.source_key}")
    print(f"CSV Input: {result.csv_path}")
    print(f"JSON Output: {result.json_path}")
    print(f"Rows Checked: {result.csv_validation_result.data_row_count}")
    print(f"Records Written: {result.record_count}")
    print(f"CSV Errors: {len(result.csv_validation_result.errors)}")
    print(f"Artifact Errors: {len(result.artifact_validation_result.errors)}")

    _print_validation_issues("CSV Errors", result.csv_validation_result.errors)

    if result.artifact_validation_result.errors:
        print()
        print("Artifact Errors")
        rows = [
            ("Artifact", error)
            for error in result.artifact_validation_result.errors
        ]
        _print_table(("Location", "Message"), rows)

    if (
        result.csv_validation_result.is_valid
        and result.artifact_validation_result.is_valid
    ):
        print()
        print("Generation passed.")
        return 0

    print()
    print("Generation failed.")
    return 1


def _generate_category_artifact(source_key):
    source = get_category_source(source_key)
    result = write_category_artifact(source)
    return _print_generation_result(result)


def _generate_subject_artifact(source_key):
    source = get_subject_source(source_key)
    result = write_subject_artifact(source)
    return _print_generation_result(result)


def _print_generation_result(result):
    print(f"Source: {result.source_key}")
    print(f"CSV Input: {result.csv_path}")
    print(f"JSON Output: {result.json_path}")
    print(f"Rows Checked: {result.csv_validation_result.data_row_count}")
    print(f"Records Written: {result.record_count}")
    print(f"CSV Errors: {len(result.csv_validation_result.errors)}")
    print(f"Artifact Errors: {len(result.artifact_validation_result.errors)}")

    _print_validation_issues("CSV Errors", result.csv_validation_result.errors)

    if result.artifact_validation_result.errors:
        print()
        print("Artifact Errors")
        rows = [
            ("Artifact", error)
            for error in result.artifact_validation_result.errors
        ]
        _print_table(("Location", "Message"), rows)

    if (
        result.csv_validation_result.is_valid
        and result.artifact_validation_result.is_valid
    ):
        print()
        print("Generation passed.")
        return 0

    print()
    print("Generation failed.")
    return 1


def _add_reference_workflow_parser(subparsers, workflow, source_example):
    workflow_parser = subparsers.add_parser(
        workflow,
        help=f"Work with {workflow} seed data.",
        description=f"Commands for {workflow} seed-data sources and artifacts.",
    )
    workflow_subparsers = workflow_parser.add_subparsers(
        dest=f"{workflow}_command",
        required=True,
    )

    sources_parser = workflow_subparsers.add_parser(
        "sources",
        help=f"List supported {workflow} sources.",
        description=f"List {workflow} sources accepted by the seed-data workflow.",
    )
    if workflow == "category":
        sources_parser.set_defaults(handler=lambda _args: _print_category_sources())
    else:
        sources_parser.set_defaults(handler=lambda _args: _print_subject_sources())

    paths_parser = workflow_subparsers.add_parser(
        "paths",
        help=f"List expected {workflow} input and output paths.",
        description=f"List canonical CSV input and JSON artifact paths for {workflow} sources.",
    )
    paths_parser.add_argument(
        "--source",
        help=f"Optional {workflow} source key to show. Example: {source_example}.",
    )
    if workflow == "category":
        paths_parser.set_defaults(handler=lambda args: _print_category_paths(args.source))
    else:
        paths_parser.set_defaults(handler=lambda args: _print_subject_paths(args.source))

    validate_parser = workflow_subparsers.add_parser(
        "validate",
        help=f"Validate a {workflow} CSV source file.",
        description=f"Validate required headers, values, stable keys, duplicates, and malformed rows for {workflow} seed data.",
    )
    validate_parser.add_argument(
        "--source",
        required=True,
        help=f"{workflow.title()} source key to validate. Example: {source_example}.",
    )
    if workflow == "category":
        validate_parser.set_defaults(
            handler=lambda args: _validate_category_source(args.source)
        )
    else:
        validate_parser.set_defaults(
            handler=lambda args: _validate_subject_source(args.source)
        )

    generate_parser = workflow_subparsers.add_parser(
        "generate",
        help=f"Generate a {workflow} JSON artifact.",
        description=f"Validate a {workflow} CSV source and generate its JSON artifact.",
    )
    generate_parser.add_argument(
        "--source",
        required=True,
        help=f"{workflow.title()} source key to generate. Example: {source_example}.",
    )
    if workflow == "category":
        generate_parser.set_defaults(
            handler=lambda args: _generate_category_artifact(args.source)
        )
    else:
        generate_parser.set_defaults(
            handler=lambda args: _generate_subject_artifact(args.source)
        )


def _add_strapi_options(parser):
    parser.add_argument(
        "--strapi-url",
        help="Strapi base URL. Defaults to GURUBODH_STRAPI_URL.",
    )
    parser.add_argument(
        "--strapi-token",
        help="Strapi API token. Defaults to GURUBODH_STRAPI_API_TOKEN.",
    )
    parser.add_argument(
        "--default-locale",
        default="en",
        help="Expected Strapi default locale for English fields. Default: en.",
    )
    parser.add_argument(
        "--localized-locale",
        default="hi-IN",
        help="Expected Hindi localization locale. Default: hi-IN.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="Strapi request timeout in seconds. Default: 10.",
    )


INGEST_OPERATIONS = ("preflight", "plan", "apply")
INGEST_TARGETS = tuple(INGEST_TARGET_REGISTRY)


def _run_target_ingestion_command(args):
    if args.operation == "preflight":
        return _run_target_ingestion_preflight(args)
    if args.operation == "plan":
        return _run_target_ingestion_plan(args)
    if args.operation == "apply":
        return _run_target_ingestion_apply(args)
    raise ValueError(f"Unsupported target-specific ingest operation: {args.operation}")


def _run_target_ingestion_preflight(args):
    artifact_result = load_target_artifact(args.target)
    if artifact_result.errors:
        for error in artifact_result.errors:
            print(f"Artifact error: {error}")

    config = _load_strapi_config_from_args(args)
    preflight_result = run_target_preflight(StrapiClient(config), config, args.target)
    _print_preflight_result(preflight_result)
    print()
    _print_target_preflight_summary(artifact_result, preflight_result)
    return 0 if artifact_result.is_valid and preflight_result.is_valid else 1


def _run_target_ingestion_plan(args):
    mode = IngestionMode()
    artifact_result = load_target_artifact(args.target)
    if artifact_result.errors:
        for error in artifact_result.errors:
            print(f"Artifact error: {error}")

    config = _load_strapi_config_from_args(args)
    client = StrapiClient(config)
    preflight_result = run_target_preflight(client, config, args.target)
    _print_preflight_result(preflight_result)

    target_plan = (
        plan_target_ingestion(client, config, artifact_result)
        if artifact_result.is_valid and preflight_result.is_valid
        else TargetIngestionPlan(target=artifact_result.target)
    )
    report = build_target_plan_report(
        mode,
        artifact_result,
        preflight_result,
        target_plan,
    )

    print()
    print(render_target_plan_report(report))
    return 0 if report.conflicts == 0 and report.blocked_records == 0 else 1


def _run_target_ingestion_apply(args):
    mode = IngestionMode(apply=True)
    artifact_result = load_target_artifact(args.target)
    if artifact_result.errors:
        for error in artifact_result.errors:
            print(f"Artifact error: {error}")

    config = _load_strapi_config_from_args(args)
    client = StrapiClient(config)
    preflight_result = run_target_preflight(client, config, args.target)
    _print_preflight_result(preflight_result)

    target_plan = (
        plan_target_ingestion(client, config, artifact_result)
        if artifact_result.is_valid and preflight_result.is_valid
        else TargetIngestionPlan(target=artifact_result.target)
    )
    report = build_target_plan_report(
        mode,
        artifact_result,
        preflight_result,
        target_plan,
    )
    if report.conflicts or report.blocked_records:
        print()
        print(render_target_plan_report(report))
        return 1

    apply_target_ingestion(client, config, mode, target_plan)
    target_plan = plan_target_ingestion(client, config, artifact_result)
    report = build_target_plan_report(
        mode,
        artifact_result,
        preflight_result,
        target_plan,
        applied=True,
    )

    print()
    print(render_target_plan_report(report))
    return 0 if not _target_report_has_pending_apply_work(report) else 1


def _print_target_preflight_summary(artifact_result, preflight_result):
    artifact = artifact_result.artifact
    rows = [
        ("Target", artifact_result.target.key),
        ("Display Name", artifact_result.target.display_name),
        ("Workflow", artifact_result.target.workflow),
        ("Collection", artifact_result.target.collection_type),
        ("Plural API ID", artifact_result.target.plural_api_id),
        ("Artifact Path", artifact.path if artifact else "not loaded"),
        ("Records", artifact.record_count if artifact else 0),
        (
            "Preflight Checks",
            f"{sum(1 for check in preflight_result.checks if check.passed)} passed, "
            f"{sum(1 for check in preflight_result.checks if not check.passed)} failed",
        ),
        ("Writes", "not performed"),
    ]
    _print_table(("Field", "Value"), rows)


def _target_report_has_pending_apply_work(report):
    return bool(
        report.to_create
        or report.to_update
        or report.conflicts
        or report.blocked_records
        or report.publish_actions
    )


def _add_ingestion_parser(subparsers):
    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Inspect and apply seed-data ingestion plans.",
        description="Ingestion commands for individual seed-data targets.",
    )
    ingest_subparsers = ingest_parser.add_subparsers(
        dest="operation",
        required=True,
    )

    for operation in INGEST_OPERATIONS:
        operation_parser = ingest_subparsers.add_parser(
            operation,
            help=f"Run {operation} for one seed-data target.",
            description=f"Run {operation} for category, subject, or one glossary target.",
        )
        _add_strapi_options(operation_parser)
        operation_parser.add_argument(
            "target",
            choices=INGEST_TARGETS,
            help="Seed-data target to process.",
        )
        operation_parser.set_defaults(handler=_run_target_ingestion_command)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="gurubodh-seed-data",
        description="Prepare and ingest Gurubodh CMS seed data.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    workflows_parser = subparsers.add_parser(
        "workflows",
        help="List supported seed-data workflows.",
        description="List scaffolded and planned seed-data workflows.",
    )
    workflows_parser.set_defaults(handler=lambda _args: _print_workflows())

    glossary_parser = subparsers.add_parser(
        "glossary",
        help="Work with glossary seed data.",
        description="Commands for glossary seed-data sources and artifacts.",
    )
    glossary_subparsers = glossary_parser.add_subparsers(
        dest="glossary_command",
        required=True,
    )

    sources_parser = glossary_subparsers.add_parser(
        "sources",
        help="List supported glossary sources.",
        description="List glossary sources accepted by the seed-data workflow.",
    )
    sources_parser.set_defaults(handler=lambda _args: _print_glossary_sources())

    paths_parser = glossary_subparsers.add_parser(
        "paths",
        help="List expected glossary input and output paths.",
        description="List canonical CSV input and JSON artifact paths for glossary sources.",
    )
    paths_parser.add_argument(
        "--source",
        help="Optional glossary source key to show. Example: sanatan-glossary.",
    )
    paths_parser.set_defaults(handler=lambda args: _print_glossary_paths(args.source))

    validate_parser = glossary_subparsers.add_parser(
        "validate",
        help="Validate a glossary CSV source file.",
        description="Validate required headers, required values, term codes, duplicate terms, and malformed rows.",
    )
    validate_parser.add_argument(
        "--source",
        required=True,
        help="Glossary source key to validate. Example: sanatan-glossary.",
    )
    validate_parser.set_defaults(
        handler=lambda args: _validate_glossary_source(args.source)
    )

    generate_parser = glossary_subparsers.add_parser(
        "generate",
        help="Generate a glossary JSON artifact.",
        description="Validate a glossary CSV source and generate its JSON artifact.",
    )
    generate_parser.add_argument(
        "--source",
        required=True,
        help="Glossary source key to generate. Example: sanatan-glossary.",
    )
    generate_parser.set_defaults(
        handler=lambda args: _generate_glossary_artifact(args.source)
    )

    _add_reference_workflow_parser(subparsers, "category", "categories")
    _add_reference_workflow_parser(subparsers, "subject", "subjects")
    _add_ingestion_parser(subparsers)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        exit_code = args.handler(args)
    except ValueError as error:
        parser.exit(2, f"error: {error}\n")
    return exit_code or 0


if __name__ == "__main__":
    sys.exit(main())
