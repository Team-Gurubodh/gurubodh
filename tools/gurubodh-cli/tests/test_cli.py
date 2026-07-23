import unittest
from contextlib import redirect_stderr
from io import StringIO

from gurubodh.cli import PLANNED_COMMANDS, build_parser, main


class CliTests(unittest.TestCase):
    def test_help_lists_commands_in_workflow_order(self):
        parser = build_parser()
        help_text = parser.format_help()
        expected_order = [
            "prep-subject",
            "generate-chunks",
            "regenerate-embeddings",
            "compare-tokenizers",
            "update-metadata",
            "download-subject",
            "delete-subject",
            "legacy-convert",
            "unicode-ingest",
        ]

        positions = [help_text.index(f"    {command}") for command in expected_order]

        self.assertEqual(positions, sorted(positions))

    def test_help_marks_legacy_commands_deprecated(self):
        parser = build_parser()
        normalized_help = " ".join(parser.format_help().split())

        self.assertIn("[deprecated] Run only the Unicode DOCX ingest pipeline.", normalized_help)
        self.assertIn("[deprecated] Run only the legacy DOCX to Unicode pipeline.", normalized_help)

    def test_help_lists_planned_commands(self):
        parser = build_parser()
        help_text = parser.format_help()
        normalized_help = " ".join(help_text.split())

        for command, command_help in PLANNED_COMMANDS.items():
            self.assertIn(command, help_text)
            self.assertIn(f"[planned] {command_help}", normalized_help)

        self.assertIn("generate-chunks", help_text)
        self.assertIn("compare-tokenizers", help_text)
        self.assertNotIn("[planned] Generate semantic text chunks from prepared chapter text files.", normalized_help)
        self.assertNotIn("[planned] Compare BGE-M3 and optional Sarvam token counts for chapter text.", normalized_help)

    def test_planned_command_exits_with_clear_message(self):
        stderr = StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as exit_context:
            main(["download-subject"])

        self.assertEqual(exit_context.exception.code, 2)
        self.assertIn("download-subject is planned but not implemented yet.", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
