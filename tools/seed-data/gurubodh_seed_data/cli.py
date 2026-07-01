import argparse

from gurubodh_seed_data.glossary import get_glossary_source, list_glossary_sources
from gurubodh_seed_data.paths import glossary_paths
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
        (source.key, source.name)
        for source in list_glossary_sources()
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


def _print_workflows():
    rows = [
        (workflow.key, workflow.status, workflow.description)
        for workflow in list_workflows()
    ]
    _print_table(("Key", "Status", "Description"), rows)


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

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except ValueError as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
