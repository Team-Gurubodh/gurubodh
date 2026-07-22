import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gurubodh_seed_data.ingestion_artifacts import load_ingestion_artifacts


class IngestionArtifactLoadTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.artifact_root = self.root / "artifacts"
        (self.artifact_root / "category").mkdir(parents=True)
        (self.artifact_root / "subject").mkdir(parents=True)
        self.config_path = self.root / "seed_data_sources.json"
        self.config_path.write_text(
            "{\n"
            '  "schema_version": 1,\n'
            f'  "source_root": "{self.root / "csv_import"}",\n'
            f'  "artifact_root": "{self.artifact_root}",\n'
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

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_json(self, relative_path, value):
        path = self.artifact_root / relative_path
        path.write_text(json.dumps(value), encoding="utf-8")

    def test_loads_reviewed_category_and_subject_artifacts(self):
        self.write_json(
            "category/categories.json",
            {
                "schema_version": 1,
                "workflow": "category",
                "source": {"key": "categories", "label": "Categories"},
                "strapi": {"collection_type": "category", "display_name": "Categories"},
                "records": [
                    {
                        "category_code": "CAT001",
                        "legacy_code": None,
                        "is_active": True,
                        "sort_order": 1,
                        "desired_status": "published",
                        "name_en": "Tattvagyan",
                        "description_en": "Tattvagyan",
                        "name_hi_IN": "तत्त्वज्ञान",
                        "description_hi_IN": "तत्त्वज्ञान",
                    }
                ],
            },
        )
        self.write_json(
            "subject/subjects.json",
            {
                "schema_version": 1,
                "workflow": "subject",
                "source": {"key": "subjects", "label": "Subjects"},
                "strapi": {"collection_type": "subject", "display_name": "Subjects"},
                "records": [
                    {
                        "subject_code": "SUB001",
                        "legacy_code": None,
                        "is_active": True,
                        "sort_order": 1,
                        "category_code": "CAT001",
                        "desired_status": "published",
                        "name_en": "Shrimad Bhagvad Geeta",
                        "description_en": "Shrimad Bhagvad Geeta",
                        "name_hi_IN": "श्रीमद् भगवद्गीता",
                        "description_hi_IN": "श्रीमद् भगवद्गीता",
                        "from_date": "2006-01-20",
                        "to_date": "2006-06-23",
                        "prabodhan_count": 21,
                    }
                ],
            },
        )

        with patch("gurubodh_seed_data.config.DEFAULT_CONFIG_PATH", self.config_path):
            result = load_ingestion_artifacts()

        self.assertTrue(result.is_valid)
        self.assertEqual(2, len(result.artifacts))
        self.assertEqual(2, result.total_records)

    def test_reports_missing_artifacts(self):
        with patch("gurubodh_seed_data.config.DEFAULT_CONFIG_PATH", self.config_path):
            result = load_ingestion_artifacts()

        self.assertFalse(result.is_valid)
        self.assertEqual(2, len(result.errors))
        self.assertTrue(result.errors[0].startswith("category artifact not found"))


if __name__ == "__main__":
    unittest.main()
