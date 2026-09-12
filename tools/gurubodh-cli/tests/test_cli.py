import unittest
from contextlib import redirect_stderr
from io import StringIO

from gurubodh.cli import build_parser


class CliTests(unittest.TestCase):
    def test_help_lists_commands_in_workflow_order(self):
        parser = build_parser()
        help_text = parser.format_help()
        expected_order = [
            "prep-subject",
            "generate-chunks",
            "generate-docx",
            "config",
            "lab",
            "compare-tokenizers",
        ]

        positions = [help_text.index(f"    {command}") for command in expected_order]

        self.assertEqual(positions, sorted(positions))

    def test_help_omits_retired_and_planned_commands(self):
        parser = build_parser()
        normalized_help = " ".join(parser.format_help().split())

        omitted_commands = (
            "unicode-ingest",
            "legacy-convert",
            "regenerate-embeddings",
            "update-metadata",
            "download-subject",
            "delete-subject",
        )
        for command in omitted_commands:
            self.assertNotIn(command, normalized_help)

    def test_generate_docx_has_overwrite_but_no_resume(self):
        parser = build_parser()
        generate_docx = next(
            action.choices["generate-docx"]
            for action in parser._actions
            if hasattr(action, "choices") and action.choices and "generate-docx" in action.choices
        )
        help_text = generate_docx.format_help()

        self.assertIn("--overwrite", help_text)
        self.assertNotIn("--resume", help_text)

    def test_lab_proofread_requires_explicit_source_locale_and_lab_root(self):
        parser = build_parser()
        lab = next(
            action.choices["lab"]
            for action in parser._actions
            if hasattr(action, "choices") and action.choices and "lab" in action.choices
        )
        proofread = next(action.choices["proofread"] for action in lab._actions if getattr(action, "choices", None))
        help_text = proofread.format_help()
        self.assertIn("--source", help_text)
        self.assertIn("--locale", help_text)
        self.assertIn("--lab-root", help_text)

    def test_lab_docx_commands_have_required_arguments_and_page_break_validation(self):
        parser = build_parser()
        lab = next(
            action.choices["lab"]
            for action in parser._actions
            if hasattr(action, "choices") and action.choices and "lab" in action.choices
        )
        lab_commands = next(action.choices for action in lab._actions if getattr(action, "choices", None))
        assemble_help = lab_commands["assemble-docx"].format_help()
        append_help = lab_commands["append-docx"].format_help()

        self.assertIn("input_directory", assemble_help)
        self.assertIn("output", assemble_help)
        self.assertIn("--overwrite", assemble_help)
        self.assertIn("source", append_help)
        self.assertIn("destination", append_help)
        self.assertIn("--page-break", append_help)
        self.assertIn("--no-page-break", append_help)
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["lab", "append-docx", "a.docx", "b.docx", "--page-break", "--no-page-break"])

    def test_removed_planned_commands_are_rejected(self):
        parser = build_parser()

        for command in (
            "regenerate-embeddings",
            "update-metadata",
            "download-subject",
            "delete-subject",
        ):
            stderr = StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as exit_context:
                parser.parse_args([command])

            self.assertEqual(exit_context.exception.code, 2)
            self.assertIn("invalid choice", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
