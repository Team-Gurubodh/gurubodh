import argparse
import json
import sys

from gurubodh.docx.namespaces import register_namespaces
from gurubodh.errors import GurubodhError
from gurubodh.job_components import ComponentCatalog
from gurubodh.job_composition import resolve_job
from gurubodh.lab_docx import run_lab_append_docx, run_lab_assemble_docx
from gurubodh.lab_proofread import run_lab_proofread
from gurubodh.ml.tokenization.cli import add_compare_tokenizers_options, format_json, format_text, run_compare_tokenizers
from gurubodh.pipelines.generate_chunks import run_generate_chunks_job
from gurubodh.pipelines.generate_docx import run_generate_docx_job
from gurubodh.pipelines.dispatcher import run_prepared_job
from gurubodh.project import resolve_project_context


COMPOSED_COMMANDS = ("prep-subject", "generate-chunks", "generate-docx")


def add_project_option(parser):
    parser.add_argument(
        "--project-root",
        help=(
            "Project root containing jobs/subjects/ and, optionally, one complete reusable component catalog. "
            "If omitted, uses GURUBODH_CLI_ROOT or walks upward from the current directory."
        ),
    )


def add_composed_options(parser, command=None, *, required=False):
    parser.add_argument("--subject", required=required, help="Subject manifest ID (not the subject code).")
    parser.add_argument("--language", required=required, help="Explicit manifest edition: hi-IN or mr-IN.")
    parser.add_argument("--environment", required=required, help="Environment component ID, e.g. development.")
    parser.add_argument(
        "--storage-profile", required=required,
        help="Storage profile ID: local, r2-output, or r2. r2-output reads downstream artifacts locally.",
    )
    for kind, applicable in (("proofreading", "prep-subject"), ("chunking", "generate-chunks")):
        if command is None or command == applicable:
            parser.add_argument(
                f"--{kind}-profile",
                help=f"Complete {kind} profile ID ({applicable} only); replaces the selected JSON profile as a whole.",
            )
    if command is None or command == "generate-chunks":
        parser.add_argument(
            "--chapters", nargs="+", metavar="NNN",
            help="generate-chunks only: unique three-ASCII-digit chapter numbers, e.g. --chapters 001 002.",
        )


def add_common_options(parser, command):
    add_composed_options(parser, command, required=True)
    parser.epilog = (
        "Profile precedence: command definition < manifest < edition < invocation; no scalar overrides."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing local output or R2 objects instead of failing.",
    )
    add_project_option(parser)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="gurubodh",
        description="Run Gurubodh CMS DOCX processing pipelines.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prep_subject_parser = subparsers.add_parser(
        "prep-subject",
        help="Prepare subject artifacts using the pipeline declared by the job config.",
        description="Compose a job from explicit selectors, then dispatch its declared pipeline.",
    )
    add_common_options(prep_subject_parser, "prep-subject")
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
    add_common_options(generate_chunks_parser, "generate-chunks")

    generate_docx_parser = subparsers.add_parser(
        "generate-docx",
        help="Generate validated DOCX exports from canonical proofread chapter text.",
        description="Generate one candidate-manifest-bound DOCX export per canonical chapter.",
    )
    add_common_options(generate_docx_parser, "generate-docx")

    config_parser = subparsers.add_parser("config", help="Validate and inspect composed job configurations.")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    resolve_parser = config_subparsers.add_parser(
        "resolve", help="Emit a validated assembled job as JSON without executing a workflow.",
        description=(
            "Emit deterministic job JSON to stdout without reading content or initializing providers/storage/models. "
            "No provider credentials or downloaded model cache are required. "
            "The JSON is for audit/debugging inspection only; exported JSON is not an executable input."
        ),
        epilog="Profile precedence: command definition < manifest < edition < invocation; whole profiles only.",
    )
    resolve_parser.add_argument("--command", dest="resolved_command", required=True, choices=COMPOSED_COMMANDS)
    add_composed_options(resolve_parser, required=True)
    add_project_option(resolve_parser)
    resolve_parser.add_argument(
        "--provenance", action="store_true",
        help="Emit separate provenance JSON to stderr; stdout remains executable job JSON only.",
    )

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
        "--project-root", help="Gurubodh CLI project root for JSON profiles and the bundled legacy converter."
    )
    lab_proofread_parser.add_argument(
        "--proofreading-profile",
        help="Complete proofreading profile ID; otherwise use lab's JSON-declared default shared with canonical prep.",
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

    compare_tokenizers_parser = subparsers.add_parser(
        "compare-tokenizers",
        help="Compare BGE-M3 and optional Sarvam token counts for chapter text.",
        description="Estimate local BGE-M3 token counts and optionally compare them with Sarvam prompt token counts.",
    )
    add_compare_tokenizers_options(compare_tokenizers_parser)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run_command(parser, args)
    except GurubodhError as exc:
        parser.error(str(exc))


def _run_command(parser, args):

    if args.command in COMPOSED_COMMANDS or args.command == "config":
        command = args.resolved_command if args.command == "config" else args.command
        _validate_job_options(parser, args, command)
        context = resolve_project_context(args.project_root)
        if args.command == "config":
            job = _resolve_composed_job(context, args, command)
            payload = json.dumps(job.to_payload(), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            if args.provenance:
                print(json.dumps(job.provenance.to_payload(), ensure_ascii=False, sort_keys=True, indent=2), file=sys.stderr)
            print(payload)
            return

        job = _resolve_composed_job(context, args, command)
        if command == "prep-subject":
            register_namespaces()
            run_prepared_job(context, job, overwrite=args.overwrite, resume=args.resume)
            return

        runner = run_generate_chunks_job if command == "generate-chunks" else run_generate_docx_job
        try:
            runner(context, job, overwrite=args.overwrite)
        except Exception as exc:
            parser.error(str(exc))
        return

    if args.command == "lab" and args.lab_command == "proofread":
        try:
            context = resolve_project_context(args.project_root)
            run_lab_proofread(
                context, args.source, args.locale, args.lab_root, progress=print,
                proofreading_profile_id=args.proofreading_profile,
            )
        except Exception as exc:
            parser.error(str(exc))
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

    if args.command == "compare-tokenizers":
        try:
            comparisons = run_compare_tokenizers(args, progress=lambda message: print(message, file=sys.stderr))
        except Exception as exc:
            parser.error(str(exc))
        print(format_json(comparisons) if args.format == "json" else format_text(comparisons))
        return

    parser.error(f"Unsupported command: {args.command}")


def _validate_job_options(parser, args, command):
    if getattr(args, "resume", False) and args.overwrite:
        parser.error("--resume and --overwrite are mutually exclusive for prep-subject.")
    for name, applicable in (("proofreading_profile", "prep-subject"),
                             ("chunking_profile", "generate-chunks"), ("chapters", "generate-chunks")):
        if getattr(args, name, None) is not None and command != applicable:
            parser.error(f"--{name.replace('_', '-')} is supported only by {applicable}.")


def _resolve_composed_job(context, args, command):
    return resolve_job(
        ComponentCatalog(context.root, context.resource_root), command=command, manifest_id=args.subject,
        locale=args.language, environment_id=args.environment, storage_profile_id=args.storage_profile,
        proofreading_profile_id=getattr(args, "proofreading_profile", None),
        chunking_profile_id=getattr(args, "chunking_profile", None),
        chapters=getattr(args, "chapters", None),
    ).job


if __name__ == "__main__":
    main()
