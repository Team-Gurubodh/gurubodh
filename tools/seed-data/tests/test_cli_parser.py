import unittest
from contextlib import redirect_stderr
from io import StringIO

from gurubodh_seed_data.cli import (
    INGEST_OPERATIONS,
    INGEST_TARGETS,
    _run_target_ingestion_command,
    build_parser,
)


class IngestCliParserTest(unittest.TestCase):
    def parse(self, argv):
        return build_parser().parse_args(argv)

    def assert_parse_fails(self, argv):
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                self.parse(argv)

    def test_ingest_commands_parse_operation_target_and_dispatch(self):
        for operation in INGEST_OPERATIONS:
            for target in INGEST_TARGETS:
                with self.subTest(operation=operation, target=target):
                    args = self.parse(("ingest", operation, target))

                    self.assertEqual("ingest", args.command)
                    self.assertEqual(operation, args.operation)
                    self.assertEqual(target, args.target)
                    self.assertIs(_run_target_ingestion_command, args.handler)

    def test_unsupported_aggregate_targets_are_rejected(self):
        for operation in INGEST_OPERATIONS:
            for target in ("all", "glossary", "category-subject"):
                with self.subTest(operation=operation, target=target):
                    self.assert_parse_fails(("ingest", operation, target))

    def test_legacy_ingest_command_forms_are_rejected(self):
        for argv in (
            ("ingest", "preflight"),
            ("ingest", "plan"),
            ("ingest", "glossary-preflight"),
            ("ingest", "glossary-plan"),
            ("ingest", "glossary-plan", "--apply"),
        ):
            with self.subTest(argv=argv):
                self.assert_parse_fails(argv)

    def test_plan_apply_flag_is_rejected(self):
        for target in INGEST_TARGETS:
            with self.subTest(target=target):
                self.assert_parse_fails(("ingest", "plan", "--apply", target))
                self.assert_parse_fails(("ingest", "plan", target, "--apply"))


if __name__ == "__main__":
    unittest.main()
