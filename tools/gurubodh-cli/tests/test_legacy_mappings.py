import hashlib
import json
import tempfile
import unittest
import shutil
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from docx import Document
from docx.enum.style import WD_STYLE_TYPE

from gurubodh.legacy.converter import check_aps_conversion, check_node, convert_texts
from gurubodh.legacy.docx_converter import convert_docx, target_devanagari_font
from gurubodh.errors import ConfigurationError, ProcessingError
from gurubodh.cli import main


CLI_ROOT = Path(__file__).parents[1]
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "aps_prakash_golden.json"
LEGACY_CONVERTER = CLI_ROOT / "scripts" / "legacy_font_convert.js"


class ApsGoldenMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_fixture_pins_the_vendored_mapping_revision(self):
        mapping = self.fixture["mapping"]
        vendor_path = CLI_ROOT / mapping["vendor_file"]

        self.assertEqual(
            hashlib.sha256(vendor_path.read_bytes()).hexdigest(),
            mapping["sha256"],
        )

    def test_fixture_covers_the_required_mapping_categories(self):
        categories = {category for case in self.fixture["cases"] for category in case["categories"]}

        self.assertTrue(self.fixture["fixture_provenance"]["source_font_family"])
        self.assertTrue(self.fixture["fixture_provenance"]["source_document_identifier"])
        self.assertTrue(self.fixture["fixture_provenance"]["initial_verification"])
        self.assertTrue(self.fixture["fixture_provenance"]["confidence_note"])
        self.assertTrue(
            {
                "matra",
                "reph",
                "half-letter",
                "conjunct",
                "anusvar",
                "chandrabindu",
                "visarga",
                "nukta",
                "digits",
                "punctuation",
                "whitespace",
                "postprocess",
            }.issubset(categories)
        )

    def test_aps_golden_cases_match_exact_unicode_output(self):
        cases = self.fixture["cases"]
        converted = convert_texts(
            [case["legacy_input"] for case in cases],
            self.fixture["converter"],
            LEGACY_CONVERTER,
        )

        for case, actual in zip(cases, converted):
            with self.subTest(case=case["id"], categories=case["categories"]):
                self.assertEqual(actual, case["expected_unicode"])


class ApsDocxConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def test_real_conversion_joins_split_aps_runs_and_preserves_adjacent_unicode_text(self):
        source_path = self.root / "source.docx"
        output_path = self.root / "converted.docx"
        document = Document()
        aps_style = document.styles.add_style("APS Legacy", WD_STYLE_TYPE.PARAGRAPH)
        aps_style.font.name = "APS-DV-Prakash"
        paragraph = document.add_paragraph(style=aps_style)
        paragraph.add_run("ef")
        paragraph.add_run("keâ&")
        unicode_run = paragraph.add_run(" [Unicode]")
        unicode_run.font.name = "Mangal"
        document.save(source_path)

        conversion = convert_docx(
            source_path,
            target_devanagari_font(),
            LEGACY_CONVERTER,
            output_path,
        )

        converted = Document(output_path)
        converted_paragraph = converted.paragraphs[0]
        self.assertEqual(converted_paragraph.text, "र्कि [Unicode]")
        self.assertEqual(converted_paragraph.runs[0].text, "र्कि")
        self.assertEqual(converted_paragraph.runs[1].text, "")
        self.assertEqual(converted_paragraph.runs[2].text, " [Unicode]")
        self.assertEqual(converted_paragraph.runs[2].font.name, "Mangal")
        self.assertEqual(conversion["converter_counts"], {"aps": 1})


class ConverterFailureTests(unittest.TestCase):
    def test_missing_node_explains_installation_and_path(self):
        with patch("gurubodh.legacy.converter.shutil.which", return_value=None):
            with self.assertRaises(ConfigurationError) as caught:
                check_node()
        self.assertIn("https://nodejs.org/en/download", str(caught.exception))
        self.assertIn("PATH", str(caught.exception))

    def test_incompatible_and_unrecognized_node_versions_fail(self):
        for version, reason in (("v20.19.0", "Incompatible"), ("v23.11.0", "Incompatible"),
                                ("unexpected", "Unrecognized")):
            with self.subTest(version=version), \
                    patch("gurubodh.legacy.converter.shutil.which", return_value="/bin/node"), \
                    patch("gurubodh.legacy.converter.subprocess.run") as run:
                run.return_value.stdout = version + "\n"
                with self.assertRaisesRegex(ConfigurationError, reason):
                    check_node()

    def test_diagnostic_reports_mismatch_as_failure(self):
        with patch("gurubodh.legacy.converter.convert_texts", return_value=["wrong"]):
            with self.assertRaisesRegex(ProcessingError, "APS diagnostic failed"):
                check_aps_conversion()

    def test_missing_node_stops_docx_conversion_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "created" / "converted.docx"
            with patch("gurubodh.legacy.converter.shutil.which", return_value=None):
                with self.assertRaisesRegex(ConfigurationError, "Node.js is required"):
                    convert_docx(Path(directory) / "source.docx", "Mangal", LEGACY_CONVERTER, output)
            self.assertFalse(output.parent.exists())

    def test_legacy_font_check_explains_output_and_succeeds_only_on_match(self):
        with redirect_stdout(StringIO()) as stdout:
            main(["legacy-font", "check"])
        lines = stdout.getvalue().splitlines()
        self.assertIn("APS identifies a supported family of legacy fonts", lines[0])
        self.assertIn("sample in that encoding and its Unicode conversion", lines[1])
        self.assertEqual(lines[2], "Legacy-font text (input): efkeâ&")
        self.assertEqual(lines[3], "Unicode text (converted result): र्कि")
        self.assertIn("Legacy-font diagnostic succeeded", lines[4])
        with patch("gurubodh.cli.check_aps_conversion", side_effect=ProcessingError("mismatch")), \
                redirect_stdout(StringIO()), redirect_stderr(StringIO()) as stderr, \
                self.assertRaises(SystemExit) as caught:
            main(["legacy-font", "check"])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("mismatch", stderr.getvalue())

    def test_missing_vendor_exposes_node_error_at_cli_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            wrapper = Path(directory) / LEGACY_CONVERTER.name
            shutil.copyfile(LEGACY_CONVERTER, wrapper)
            # Reach the normal CLI error handler with a real failing subprocess.
            with patch("gurubodh.cli._run_command", side_effect=lambda *_: convert_texts(
                ["efkeâ&"], "aps", wrapper
            )), redirect_stderr(StringIO()) as stderr, self.assertRaises(SystemExit) as caught:
                main(["prep-subject", "--subject", "test", "--language", "hi-IN",
                      "--environment", "development", "--storage-profile", "r2"])
            self.assertEqual(caught.exception.code, 2)
            self.assertIn("exit 1", stderr.getvalue())
            self.assertIn("ENOENT", stderr.getvalue())
            self.assertIn("hindietools_aps_prakash_to_unicode.js", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_failure_without_stderr_has_actionable_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            wrapper = Path(directory) / "silent.js"
            wrapper.write_text("process.exit(7);", encoding="utf-8")
            with self.assertRaisesRegex(ProcessingError, "exit 7") as caught:
                convert_texts(["text"], "aps", wrapper)
            self.assertIn("Node produced no error output", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
