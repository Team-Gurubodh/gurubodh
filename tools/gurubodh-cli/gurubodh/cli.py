import argparse

from gurubodh.docx.namespaces import register_namespaces
from gurubodh.ml.semantic_chunking.cli import add_generate_chunks_options, run_generate_chunks
from gurubodh.pipelines.dispatcher import run_configured_job, run_legacy_job, run_unicode_job
from gurubodh.project import resolve_project_context, resolve_project_path


PLANNED_COMMANDS = {
    "download-subject": "Download subject source files and existing artifacts from configured storage.",
    "delete-subject": "Delete a subject and its generated artifacts from configured storage.",
    "generate-embeddings": "Generate vector embeddings for prepared semantic chunks.",
    "update-metadata": "Update subject and chapter metadata from the configured metadata source.",
}


def add_common_options(parser):
    parser.add_argument("--config", required=True, help="Path to a Gurubodh CMS conversion job JSON file.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing local output or R2 objects instead of failing.",
    )
    parser.add_argument(
        "--project-root",
        help=(
            "Project root containing config/ and jobs/. If omitted, uses GURUBODH_CLI_ROOT "
            "or walks upward from the current directory."
        ),
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="gurubodh",
        description="Run Gurubodh CMS DOCX processing pipelines.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prep_subject_parser = subparsers.add_parser(
        "prep-subject",
        help="Prepare subject artifacts using the pipeline declared by the job config.",
        description="Read the job config and dispatch to its declared pipeline.",
    )
    add_common_options(prep_subject_parser)

    unicode_parser = subparsers.add_parser(
        "unicode-ingest",
        help="[deprecated] Run only the Unicode DOCX ingest pipeline.",
        description="[deprecated] Copy Unicode DOCX input, extract text, split chapters, and reject non-Unicode jobs.",
    )
    add_common_options(unicode_parser)

    legacy_parser = subparsers.add_parser(
        "legacy-convert",
        help="[deprecated] Run only the legacy DOCX to Unicode pipeline.",
        description="[deprecated] Convert supported legacy-font DOCX input to Unicode, then split chapters.",
    )
    add_common_options(legacy_parser)

    generate_chunks_parser = subparsers.add_parser(
        "generate-chunks",
        help="Generate semantic text chunks from prepared chapter text files.",
        description="Generate standalone semantic chunk JSON and Markdown outputs from prepared chapter .txt files.",
    )
    add_generate_chunks_options(generate_chunks_parser)

    for command, help_text in PLANNED_COMMANDS.items():
        subparsers.add_parser(
            command,
            help=f"[planned] {help_text}",
            description=f"[planned] {help_text}",
        )

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in PLANNED_COMMANDS:
        parser.error(f"{args.command} is planned but not implemented yet.")

    if args.command == "generate-chunks":
        try:
            documents = run_generate_chunks(args, progress=print)
        except Exception as exc:
            parser.error(str(exc))
        for document in documents:
            print(f"{document.source_name}: {document.chunk_count} chunks")
        return

    context = resolve_project_context(args.project_root)
    config_path = resolve_project_path(context, args.config)
    register_namespaces()

    if args.command == "prep-subject":
        run_configured_job(context, config_path, overwrite=args.overwrite)
    elif args.command == "unicode-ingest":
        run_unicode_job(context, config_path, overwrite=args.overwrite)
    elif args.command == "legacy-convert":
        run_legacy_job(context, config_path, overwrite=args.overwrite)
    else:
        parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
