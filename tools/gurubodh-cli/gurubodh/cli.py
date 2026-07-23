import argparse
import sys

from gurubodh.docx.namespaces import register_namespaces
from gurubodh.config import load_generate_chunks_job
from gurubodh.ml.tokenization.cli import add_compare_tokenizers_options, format_json, format_text, run_compare_tokenizers
from gurubodh.pipelines.generate_chunks import run_generate_chunks_job
from gurubodh.pipelines.dispatcher import run_configured_job, run_legacy_job, run_unicode_job
from gurubodh.project import resolve_project_context, resolve_project_path


PLANNED_COMMANDS = {
    "generate-embeddings": "Generate vector embeddings for prepared semantic chunks.",
    "update-metadata": "Update subject and chapter metadata from the configured metadata source.",
    "download-subject": "Download subject source files and existing artifacts from configured storage.",
    "delete-subject": "Delete a subject and its generated artifacts from configured storage.",
}


def add_common_options(parser):
    parser.add_argument("--config", required=True, help="Path to a Gurubodh prep-subject job JSON file.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing local output or R2 objects instead of failing.",
    )
    parser.add_argument(
        "--project-root",
        help=(
            "Project root containing config/jobs/ and jobs/subjects/. If omitted, uses GURUBODH_CLI_ROOT "
            "or walks upward from the current directory."
        ),
    )


def add_planned_command(subparsers, command):
    help_text = PLANNED_COMMANDS[command]
    subparsers.add_parser(
        command,
        help=f"[planned] {help_text}",
        description=f"[planned] {help_text}",
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

    generate_chunks_parser = subparsers.add_parser(
        "generate-chunks",
        help="Generate semantic text chunks from prepared chapter text files.",
        description="Generate semantic chunk and dense embedding artifacts from a job config.",
    )
    add_common_options(generate_chunks_parser)

    add_planned_command(subparsers, "generate-embeddings")

    compare_tokenizers_parser = subparsers.add_parser(
        "compare-tokenizers",
        help="Compare BGE-M3 and optional Sarvam token counts for chapter text.",
        description="Estimate local BGE-M3 token counts and optionally compare them with Sarvam prompt token counts.",
    )
    add_compare_tokenizers_options(compare_tokenizers_parser)

    add_planned_command(subparsers, "update-metadata")
    add_planned_command(subparsers, "download-subject")
    add_planned_command(subparsers, "delete-subject")

    legacy_parser = subparsers.add_parser(
        "legacy-convert",
        help="[deprecated] Run only the legacy DOCX to Unicode pipeline.",
        description="[deprecated] Convert supported legacy-font DOCX input to Unicode, then split chapters.",
    )
    add_common_options(legacy_parser)

    unicode_parser = subparsers.add_parser(
        "unicode-ingest",
        help="[deprecated] Run only the Unicode DOCX ingest pipeline.",
        description="[deprecated] Copy Unicode DOCX input, extract text, split chapters, and reject non-Unicode jobs.",
    )
    add_common_options(unicode_parser)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in PLANNED_COMMANDS:
        parser.error(f"{args.command} is planned but not implemented yet.")

    if args.command == "generate-chunks":
        context = resolve_project_context(args.project_root)
        config_path = resolve_project_path(context, args.config)
        config = load_generate_chunks_job(config_path)
        try:
            result = run_generate_chunks_job(context, config, overwrite=args.overwrite, config_path=config_path)
        except Exception as exc:
            parser.error(str(exc))
        print(
            "generate-chunks complete: "
            f"{result['processed_chapter_count']} chapter(s), {result['total_chunk_count']} chunk(s)"
        )
        return

    if args.command == "compare-tokenizers":
        try:
            comparisons = run_compare_tokenizers(args, progress=lambda message: print(message, file=sys.stderr))
        except Exception as exc:
            parser.error(str(exc))
        print(format_json(comparisons) if args.format == "json" else format_text(comparisons))
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
