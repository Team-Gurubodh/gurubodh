import argparse
import sys

from gurubodh.docx.namespaces import register_namespaces
from gurubodh.config import load_generate_chunks_job, load_generate_docx_job
from gurubodh.lab_docx import run_lab_append_docx, run_lab_assemble_docx
from gurubodh.lab_proofread import run_lab_proofread
from gurubodh.ml.tokenization.cli import add_compare_tokenizers_options, format_json, format_text, run_compare_tokenizers
from gurubodh.pipelines.generate_chunks import run_generate_chunks_job
from gurubodh.pipelines.generate_docx import run_generate_docx_job
from gurubodh.pipelines.dispatcher import run_configured_job, run_legacy_job, run_unicode_job
from gurubodh.project import resolve_project_context, resolve_project_path


PLANNED_COMMANDS = {
    "regenerate-embeddings": "Regenerate vector embeddings for prepared semantic chunks.",
    "update-metadata": "Update subject and chapter metadata from the configured metadata source.",
    "download-subject": "Download subject source files and existing artifacts from configured storage.",
    "delete-subject": "Delete a subject and its generated artifacts from configured storage.",
}


def add_common_options(parser):
    parser.add_argument("--config", required=True, help="Path to a Gurubodh job JSON file.")
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
    prep_subject_parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume a compatible incomplete prep-subject checkpoint without repeating successful chapter proofreads.",
    )

    generate_chunks_parser = subparsers.add_parser(
        "generate-chunks",
        help="Generate candidate-manifest-bound semantic chunks from prepared chapter text.",
        description="Generate semantic chunk artifacts from an authoritative candidate manifest.",
    )
    add_common_options(generate_chunks_parser)

    generate_docx_parser = subparsers.add_parser(
        "generate-docx",
        help="Generate validated DOCX exports from canonical proofread chapter text.",
        description="Generate one candidate-manifest-bound DOCX export per canonical chapter.",
    )
    add_common_options(generate_docx_parser)

    lab_parser = subparsers.add_parser(
        "lab",
        help="Run explicitly non-canonical local experimentation commands.",
        description="Run explicitly non-canonical local experimentation commands.",
    )
    lab_subparsers = lab_parser.add_subparsers(dest="lab_command", required=True)
    lab_proofread_parser = lab_subparsers.add_parser(
        "proofread",
        help="Proofread one local DOCX into a distinct non-canonical lab run.",
    )
    lab_proofread_parser.add_argument(
        "--source", required=True, help="Explicit local DOCX source to read without modifying."
    )
    lab_proofread_parser.add_argument("--locale", required=True, help="Proofreading locale: hi-IN or mr-IN.")
    lab_proofread_parser.add_argument(
        "--lab-root", required=True, help="Explicit root for non-canonical lab output."
    )
    lab_proofread_parser.add_argument(
        "--project-root", help="Gurubodh CLI project root, used only for the bundled legacy converter."
    )
    lab_assemble_docx_parser = lab_subparsers.add_parser(
        "assemble-docx",
        help="Assemble controlled local Gurubodh DOCX exports into one non-canonical DOCX.",
    )
    lab_assemble_docx_parser.add_argument("input_directory", help="Directory containing direct-child DOCX exports.")
    lab_assemble_docx_parser.add_argument("output", help="Local DOCX file to create.")
    lab_assemble_docx_parser.add_argument(
        "--overwrite", action="store_true", help="Replace an existing output DOCX."
    )
    lab_append_docx_parser = lab_subparsers.add_parser(
        "append-docx",
        help="Append one controlled local Gurubodh DOCX export to another non-canonically.",
    )
    lab_append_docx_parser.add_argument("source", help="Local DOCX export to append.")
    lab_append_docx_parser.add_argument("destination", help="Local DOCX export to replace atomically.")
    page_break_group = lab_append_docx_parser.add_mutually_exclusive_group()
    page_break_group.add_argument(
        "--page-break", dest="page_break", action="store_true", default=True, help="Insert a page break before the appended content (default)."
    )
    page_break_group.add_argument(
        "--no-page-break", dest="page_break", action="store_false", help="Append without a page break."
    )

    add_planned_command(subparsers, "regenerate-embeddings")

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

    if args.command == "lab" and args.lab_command == "proofread":
        try:
            context = resolve_project_context(args.project_root)
            result = run_lab_proofread(
                context, args.source, args.locale, args.lab_root, progress=print
            )
        except Exception as exc:
            parser.error(str(exc))
        print(f"lab proofread complete: {result['run_directory']}")
        return

    if args.command == "lab" and args.lab_command == "assemble-docx":
        try:
            result = run_lab_assemble_docx(args.input_directory, args.output, overwrite=args.overwrite)
        except Exception as exc:
            parser.error(str(exc))
        print("lab assemble-docx sources:")
        for source in result["sources"]:
            print(f"- {source}")
        print(f"lab assemble-docx complete: {len(result['sources'])} document(s) -> {result['output']}")
        return

    if args.command == "lab" and args.lab_command == "append-docx":
        try:
            result = run_lab_append_docx(args.source, args.destination, page_break=args.page_break)
        except Exception as exc:
            parser.error(str(exc))
        print(f"lab append-docx source: {result['source']}")
        print(
            f"lab append-docx complete: {result['destination']} "
            f"(page break: {'yes' if result['page_break'] else 'no'})"
        )
        return

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

    if args.command == "generate-docx":
        context = resolve_project_context(args.project_root)
        config_path = resolve_project_path(context, args.config)
        config = load_generate_docx_job(config_path)
        try:
            result = run_generate_docx_job(
                context, config, overwrite=args.overwrite, config_path=config_path
            )
        except Exception as exc:
            parser.error(str(exc))
        print(f"generate-docx complete: {result['processed_chapter_count']} chapter DOCX file(s)")
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
        if args.resume and args.overwrite:
            parser.error("--resume and --overwrite are mutually exclusive for prep-subject.")
        run_configured_job(context, config_path, overwrite=args.overwrite, resume=args.resume)
    elif args.command == "unicode-ingest":
        run_unicode_job(config_path, overwrite=args.overwrite)
    elif args.command == "legacy-convert":
        run_legacy_job(context, config_path, overwrite=args.overwrite)
    else:
        parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
