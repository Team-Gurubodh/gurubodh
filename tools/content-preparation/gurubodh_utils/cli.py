import argparse

from gurubodh_utils.docx.namespaces import register_namespaces
from gurubodh_utils.pipelines.dispatcher import run_configured_job, run_legacy_job, run_unicode_job
from gurubodh_utils.project import resolve_project_context, resolve_project_path


def add_common_options(parser):
    parser.add_argument("--config", required=True, help="Path to a Gurubodh CMS conversion job JSON file.")
    parser.add_argument(
        "--project-root",
        help=(
            "Project root containing config/ and jobs/. If omitted, uses GURUBODH_UTILS_ROOT "
            "or walks upward from the current directory."
        ),
    )


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

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    context = resolve_project_context(args.project_root)
    config_path = resolve_project_path(context, args.config)
    register_namespaces()

    if args.command == "run":
        run_configured_job(context, config_path)
    elif args.command == "unicode-ingest":
        run_unicode_job(context, config_path)
    elif args.command == "legacy-convert":
        run_legacy_job(context, config_path)
    else:
        parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()

