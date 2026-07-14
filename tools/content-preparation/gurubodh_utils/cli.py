import argparse

from gurubodh_utils.config import migrate_conversion_job_paths
from gurubodh_utils.docx.namespaces import register_namespaces
from gurubodh_utils.pipelines.dispatcher import run_configured_job, run_legacy_job, run_unicode_job
from gurubodh_utils.project import resolve_project_context, resolve_project_path


def add_project_root_option(parser):
    parser.add_argument(
        "--project-root",
        help=(
            "Project root containing config/ and jobs/. If omitted, uses GURUBODH_UTILS_ROOT "
            "or walks upward from the current directory."
        ),
    )


def add_common_options(parser):
    parser.add_argument("--config", required=True, help="Path to a Gurubodh CMS conversion job JSON file.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing local output or R2 objects instead of failing.",
    )
    add_project_root_option(parser)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="gurubodh_utils",
        description="Run Gurubodh CMS DOCX processing pipelines.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Run the pipeline declared by the job config.",
        description="Read the job config and dispatch to its declared pipeline.",
    )
    add_common_options(run_parser)

    unicode_parser = subparsers.add_parser(
        "unicode-ingest",
        help="Run only the Unicode DOCX ingest pipeline.",
        description="Copy Unicode DOCX input, extract text, split chapters, and reject non-Unicode jobs.",
    )
    add_common_options(unicode_parser)

    legacy_parser = subparsers.add_parser(
        "legacy-convert",
        help="Run only the legacy DOCX to Unicode pipeline.",
        description="Convert supported legacy-font DOCX input to Unicode, then split chapters.",
    )
    add_common_options(legacy_parser)

    migrate_parser = subparsers.add_parser(
        "migrate-configs",
        help="Migrate conversion job configs to the current schema version.",
        description=(
            "Preview or apply conversion job schema migrations. By default this command "
            "only reports files that would change."
        ),
    )
    add_project_root_option(migrate_parser)
    migrate_parser.add_argument(
        "--apply",
        action="store_true",
        help="Write migrated config files. Without this flag, only preview changes.",
    )
    migrate_parser.add_argument(
        "configs",
        nargs="+",
        help="Conversion job JSON files to migrate.",
    )

    return parser


def run_migration(context, args):
    config_paths = [resolve_project_path(context, config) for config in args.configs]
    results = migrate_conversion_job_paths(config_paths, apply=args.apply)
    for result in results:
        print(f"{result['status']}: {result['path']}")
        if result.get("formatting_block"):
            if result["status"] == "migrated":
                print("  migrated to 1.3.0 and added default formatting configuration with formatting disabled:")
            elif result["status"] == "added-formatting-defaults":
                print("  added default formatting configuration with formatting disabled:")
            else:
                print("  this command will add the default formatting configuration with formatting disabled:")
            print(result["formatting_block"])
            print('  Set "enabled": true before running the job when Sarvam chapter formatting is desired.')


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    context = resolve_project_context(args.project_root)
    register_namespaces()

    if args.command == "run":
        config_path = resolve_project_path(context, args.config)
        run_configured_job(context, config_path, overwrite=args.overwrite)
    elif args.command == "unicode-ingest":
        config_path = resolve_project_path(context, args.config)
        run_unicode_job(context, config_path, overwrite=args.overwrite)
    elif args.command == "legacy-convert":
        config_path = resolve_project_path(context, args.config)
        run_legacy_job(context, config_path, overwrite=args.overwrite)
    elif args.command == "migrate-configs":
        run_migration(context, args)
    else:
        parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
