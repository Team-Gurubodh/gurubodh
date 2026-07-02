import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gurubodh_seed_data.glossary import GlossarySource
from gurubodh_seed_data.validation import validate_glossary_csv


class GlossaryValidationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source_dir = self.root / "sources" / "glossary"
        self.source_dir.mkdir(parents=True)
        self.source = GlossarySource(
            key="test-glossary",
            name="Test Glossary",
            csv_filename="test-glossary.csv",
            json_filename="test-glossary.json",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_csv(self, content):
        csv_path = self.source_dir / self.source.csv_filename
        csv_path.write_text(content, encoding="utf-8")

    def validate(self):
        with patch("gurubodh_seed_data.paths.SEED_DATA_ROOT", self.root):
            return validate_glossary_csv(self.source)

    def test_valid_glossary_csv_passes(self):
        self.write_csv(
            "Sr No,Term Code,Term,Definition\n"
            "1,T00001,anirvachaneeya,indescribable\n"
            "2,T50000,anugraha,grace\n"
        )

        result = self.validate()

        self.assertTrue(result.is_valid)
        self.assertEqual(2, result.data_row_count)
        self.assertEqual(0, len(result.errors))
        self.assertEqual(0, len(result.warnings))

    def test_reports_whitespace_as_warning(self):
        self.write_csv(
            "Sr No,Term Code,Term,Definition\n"
            "1,T00001,सूक्ष्म देह,समष्टि \n"
        )

        result = self.validate()

        self.assertTrue(result.is_valid)
        self.assertEqual(0, len(result.errors))
        self.assertEqual(2, len(result.warnings))
        self.assertEqual({"Term", "Definition"}, {issue.column for issue in result.warnings})
        self.assertTrue(
            any(
                issue.message == (
                    "Term contains whitespace; duplicate checks ignore all whitespace."
                )
                for issue in result.warnings
            )
        )

    def test_reports_invalid_rows_and_values_as_errors(self):
        self.write_csv(
            "Sr No,Term Code,Term,Definition\n"
            "1,T00000,duplicate term,definition\n"
            "2,T50001,duplicateterm,definition\n"
            "3,T12,unique,definition\n"
            "4,T00004,,definition\n"
            "\n"
            "6,T00006,too-few-columns\n"
        )

        result = self.validate()

        self.assertFalse(result.is_valid)
        messages = [issue.message for issue in result.errors]
        self.assertIn("Term Code must be in range T00001 through T50000.", messages)
        self.assertIn("Expected format Tnnnnn, for example T00001.", messages)
        self.assertIn("Required value is missing.", messages)
        self.assertIn("Blank rows are not allowed.", messages)
        self.assertIn("Expected 4 columns, found 3.", messages)
        self.assertTrue(
            any(message.startswith("Duplicate term within source") for message in messages)
        )
        self.assertEqual(
            2,
            len(
                [
                    issue for issue in result.errors
                    if issue.message.startswith("Duplicate term within source")
                ]
            ),
        )

    def test_reports_missing_required_headers(self):
        self.write_csv(
            "Sr No,Term Code,Term\n"
            "1,T00001,anirvachaneeya\n"
        )

        result = self.validate()

        self.assertFalse(result.is_valid)
        self.assertEqual(1, len(result.errors))
        self.assertEqual("Header", result.errors[0].column)


if __name__ == "__main__":
    unittest.main()
