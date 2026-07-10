import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gurubodh_seed_data.config import SeedDataSource
from gurubodh_seed_data.validation import (
    validate_category_csv,
    validate_glossary_csv,
    validate_subject_csv,
)


class GlossaryValidationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source_root = self.root / "csv_import"
        self.source_dir = self.source_root / "glossary"
        self.source_dir.mkdir(parents=True)
        self.config_path = self.root / "seed_data_sources.json"
        self.config_path.write_text(
            "{\n"
            '  "schema_version": 1,\n'
            f'  "source_root": "{self.source_root}",\n'
            '  "artifact_root": "artifacts",\n'
            '  "workflows": [\n'
            '    {"key": "glossary", "status": "scaffolded", "description": "Glossary"}\n'
            '  ],\n'
            '  "sources": [\n'
            '    {"key": "test-glossary", "workflow": "glossary", "label": "Test Glossary", "csv_path": "glossary/test-glossary.csv", "artifact_path": "glossary/test-glossary.json"}\n'
            '  ]\n'
            "}\n",
            encoding="utf-8",
        )
        self.source = SeedDataSource(
            key="test-glossary",
            workflow="glossary",
            label="Test Glossary",
            csv_path=Path("glossary/test-glossary.csv"),
            artifact_path=Path("glossary/test-glossary.json"),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_csv(self, content):
        csv_path = self.source_root / self.source.csv_path
        csv_path.write_text(content, encoding="utf-8")

    def validate(self):
        with patch("gurubodh_seed_data.config.DEFAULT_CONFIG_PATH", self.config_path):
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

    def test_allows_internal_term_whitespace_and_ignores_non_term_whitespace(self):
        self.write_csv(
            "Sr No,Term Code,Term,Definition\n"
            "1,T00001,सूक्ष्म देह,समष्टि \n"
        )

        result = self.validate()

        self.assertTrue(result.is_valid)
        self.assertEqual(0, len(result.errors))
        self.assertEqual(0, len(result.warnings))

    def test_reports_leading_or_trailing_term_whitespace_as_error(self):
        self.write_csv(
            "Sr No,Term Code,Term,Definition\n"
            "1,T00001, समष्टि ,definition\n"
        )

        result = self.validate()

        self.assertFalse(result.is_valid)
        self.assertEqual(1, len(result.errors))
        self.assertEqual(0, len(result.warnings))
        self.assertEqual("Term", result.errors[0].column)
        self.assertEqual(
            "Term has leading or trailing whitespace. Cell value: ' समष्टि '.",
            result.errors[0].message,
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


class CategorySubjectValidationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source_root = self.root / "csv_import"
        (self.source_root / "category").mkdir(parents=True)
        (self.source_root / "subject").mkdir(parents=True)
        self.config_path = self.root / "seed_data_sources.json"
        self.config_path.write_text(
            "{\n"
            '  "schema_version": 1,\n'
            f'  "source_root": "{self.source_root}",\n'
            '  "artifact_root": "artifacts",\n'
            '  "workflows": [\n'
            '    {"key": "category", "status": "scaffolded", "description": "Category"},\n'
            '    {"key": "subject", "status": "scaffolded", "description": "Subject"}\n'
            '  ],\n'
            '  "sources": [\n'
            '    {"key": "categories", "workflow": "category", "label": "Categories", "csv_path": "category/categories.csv", "artifact_path": "category/categories.json"},\n'
            '    {"key": "subjects", "workflow": "subject", "label": "Subjects", "csv_path": "subject/subjects.csv", "artifact_path": "subject/subjects.json"}\n'
            '  ]\n'
            "}\n",
            encoding="utf-8",
        )
        self.category_source = SeedDataSource(
            key="categories",
            workflow="category",
            label="Categories",
            csv_path=Path("category/categories.csv"),
            artifact_path=Path("category/categories.json"),
        )
        self.subject_source = SeedDataSource(
            key="subjects",
            workflow="subject",
            label="Subjects",
            csv_path=Path("subject/subjects.csv"),
            artifact_path=Path("subject/subjects.json"),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_category_csv(self, content):
        (self.source_root / self.category_source.csv_path).write_text(
            content,
            encoding="utf-8",
        )

    def write_subject_csv(self, content):
        (self.source_root / self.subject_source.csv_path).write_text(
            content,
            encoding="utf-8",
        )

    def with_config(self, callback):
        with patch("gurubodh_seed_data.config.DEFAULT_CONFIG_PATH", self.config_path):
            return callback()

    def test_valid_category_csv_passes(self):
        self.write_category_csv(
            "code,legacy_code,is_active,sort_order,desired_status,name_en,description_en,name_hi-IN,description_hi-IN\n"
            "CAT001,,TRUE,1,published,Tattvagyan,Tattvagyan,तत्त्वज्ञान,तत्त्वज्ञान\n"
        )

        result = self.with_config(lambda: validate_category_csv(self.category_source))

        self.assertTrue(result.is_valid)
        self.assertEqual(1, result.data_row_count)

    def test_category_validation_reports_duplicates_and_invalid_values(self):
        self.write_category_csv(
            "code,legacy_code,is_active,sort_order,desired_status,name_en,description_en,name_hi-IN,description_hi-IN\n"
            "CAT001,OLD,maybe,1,review,Tattvagyan,Tattvagyan,तत्त्वज्ञान,तत्त्वज्ञान\n"
            "CAT001,OLD,TRUE,1,published,,Description,हिन्दी,हिन्दी\n"
            "\n"
        )

        result = self.with_config(lambda: validate_category_csv(self.category_source))

        self.assertFalse(result.is_valid)
        messages = [issue.message for issue in result.errors]
        self.assertIn("Expected boolean value true or false.", messages)
        self.assertIn("Expected desired_status to be draft or published.", messages)
        self.assertIn("Required value is missing.", messages)
        self.assertIn("Blank rows are not allowed.", messages)
        self.assertTrue(any(message.startswith("Duplicate non-empty code") for message in messages))
        self.assertTrue(any(message.startswith("Duplicate non-empty legacy_code") for message in messages))
        self.assertTrue(any(message.startswith("Duplicate non-empty sort_order") for message in messages))

    def test_valid_subject_csv_passes_with_category_reference(self):
        self.write_category_csv(
            "code,legacy_code,is_active,sort_order,desired_status,name_en,description_en,name_hi-IN,description_hi-IN\n"
            "CAT001,,TRUE,1,published,Tattvagyan,Tattvagyan,तत्त्वज्ञान,तत्त्वज्ञान\n"
        )
        self.write_subject_csv(
            "code,legacy_code,is_active,sort_order,category_code,desired_status,name_en,description_en,name_hi-IN,description_hi-IN,from_date,to_date,prabodhan_count\n"
            "SUB001,,TRUE,1,CAT001,published,Shrimad Bhagvad Geeta,Shrimad Bhagvad Geeta,श्रीमद् भगवद्गीता,श्रीमद् भगवद्गीता,2006-01-20,2006-06-23,21\n"
        )

        result = self.with_config(
            lambda: validate_subject_csv(self.subject_source, self.category_source)
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(1, result.data_row_count)

    def test_subject_validation_reports_unresolved_category_reference(self):
        self.write_category_csv(
            "code,legacy_code,is_active,sort_order,desired_status,name_en,description_en,name_hi-IN,description_hi-IN\n"
            "CAT001,,TRUE,1,published,Tattvagyan,Tattvagyan,तत्त्वज्ञान,तत्त्वज्ञान\n"
        )
        self.write_subject_csv(
            "code,legacy_code,is_active,sort_order,category_code,desired_status,name_en,description_en,name_hi-IN,description_hi-IN,from_date,to_date,prabodhan_count\n"
            "SUB001,,TRUE,1,CAT999,published,Shrimad Bhagvad Geeta,Shrimad Bhagvad Geeta,श्रीमद् भगवद्गीता,श्रीमद् भगवद्गीता,2006-01-20,2006-06-23,21\n"
        )

        result = self.with_config(
            lambda: validate_subject_csv(self.subject_source, self.category_source)
        )

        self.assertFalse(result.is_valid)
        self.assertIn(
            "Unresolved category_code; no matching category code found: CAT999.",
            [issue.message for issue in result.errors],
        )

    def test_subject_validation_reports_optional_field_formats(self):
        self.write_category_csv(
            "code,legacy_code,is_active,sort_order,desired_status,name_en,description_en,name_hi-IN,description_hi-IN\n"
            "CAT001,,TRUE,1,published,Tattvagyan,Tattvagyan,तत्त्वज्ञान,तत्त्वज्ञान\n"
        )
        self.write_subject_csv(
            "code,legacy_code,is_active,sort_order,category_code,desired_status,name_en,description_en,name_hi-IN,description_hi-IN,from_date,to_date,prabodhan_count\n"
            "SUB001,,TRUE,1,CAT001,published,Shrimad Bhagvad Geeta,Shrimad Bhagvad Geeta,श्रीमद् भगवद्गीता,श्रीमद् भगवद्गीता,01/20/2006,soon,many\n"
        )

        result = self.with_config(
            lambda: validate_subject_csv(self.subject_source, self.category_source)
        )

        self.assertFalse(result.is_valid)
        messages = [issue.message for issue in result.errors]
        self.assertIn("Expected date format YYYY-MM-DD when present.", messages)
        self.assertIn("Expected an integer value when present.", messages)


if __name__ == "__main__":
    unittest.main()
