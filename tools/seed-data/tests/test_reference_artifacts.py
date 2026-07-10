import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gurubodh_seed_data.category_artifacts import (
    build_category_artifact,
    validate_category_artifact,
    write_category_artifact,
)
from gurubodh_seed_data.config import SeedDataSource
from gurubodh_seed_data.subject_artifacts import (
    build_subject_artifact,
    validate_subject_artifact,
    write_subject_artifact,
)


class ReferenceArtifactTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source_root = self.root / "csv_import"
        self.artifact_root = self.root / "artifacts"
        (self.source_root / "category").mkdir(parents=True)
        (self.source_root / "subject").mkdir(parents=True)
        self.config_path = self.root / "seed_data_sources.json"
        self.config_path.write_text(
            "{\n"
            '  "schema_version": 1,\n'
            f'  "source_root": "{self.source_root}",\n'
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

    def test_builds_category_artifact_shape(self):
        self.write_category_csv(
            "code,legacy_code,is_active,sort_order,desired_status,name_en,description_en,name_hi-IN,description_hi-IN\n"
            "CAT001,,TRUE,1,published,Tattvagyan,Tattvagyan,तत्त्वज्ञान,तत्त्वज्ञान\n"
        )

        artifact = self.with_config(lambda: build_category_artifact(self.category_source))

        self.assertEqual("category", artifact["workflow"])
        self.assertEqual(
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
            },
            artifact["records"][0],
        )
        self.assertTrue(validate_category_artifact(artifact).is_valid)

    def test_writes_category_artifact_after_validation(self):
        self.write_category_csv(
            "code,legacy_code,is_active,sort_order,desired_status,name_en,description_en,name_hi-IN,description_hi-IN\n"
            "CAT001,,TRUE,1,published,Tattvagyan,Tattvagyan,तत्त्वज्ञान,तत्त्वज्ञान\n"
        )

        result = self.with_config(lambda: write_category_artifact(self.category_source))

        artifact_path = self.artifact_root / self.category_source.artifact_path
        self.assertTrue(result.csv_validation_result.is_valid)
        self.assertTrue(result.artifact_validation_result.is_valid)
        self.assertTrue(artifact_path.exists())
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        self.assertEqual("CAT001", artifact["records"][0]["category_code"])

    def test_builds_subject_artifact_shape(self):
        self.write_subject_csv(
            "code,legacy_code,is_active,sort_order,category_code,desired_status,name_en,description_en,name_hi-IN,description_hi-IN,from_date,to_date,prabodhan_count\n"
            "SUB001,,TRUE,1,CAT001,published,Shrimad Bhagvad Geeta,Shrimad Bhagvad Geeta,श्रीमद् भगवद्गीता,श्रीमद् भगवद्गीता,2006-01-20,2006-06-23,21\n"
        )

        artifact = self.with_config(lambda: build_subject_artifact(self.subject_source))

        self.assertEqual("subject", artifact["workflow"])
        self.assertEqual("SUB001", artifact["records"][0]["subject_code"])
        self.assertEqual("CAT001", artifact["records"][0]["category_code"])
        self.assertEqual(21, artifact["records"][0]["prabodhan_count"])
        self.assertTrue(validate_subject_artifact(artifact).is_valid)

    def test_writes_subject_artifact_after_reference_validation(self):
        self.write_category_csv(
            "code,legacy_code,is_active,sort_order,desired_status,name_en,description_en,name_hi-IN,description_hi-IN\n"
            "CAT001,,TRUE,1,published,Tattvagyan,Tattvagyan,तत्त्वज्ञान,तत्त्वज्ञान\n"
        )
        self.write_subject_csv(
            "code,legacy_code,is_active,sort_order,category_code,desired_status,name_en,description_en,name_hi-IN,description_hi-IN,from_date,to_date,prabodhan_count\n"
            "SUB001,,TRUE,1,CAT001,published,Shrimad Bhagvad Geeta,Shrimad Bhagvad Geeta,श्रीमद् भगवद्गीता,श्रीमद् भगवद्गीता,2006-01-20,2006-06-23,21\n"
        )

        result = self.with_config(lambda: write_subject_artifact(self.subject_source))

        artifact_path = self.artifact_root / self.subject_source.artifact_path
        self.assertTrue(result.csv_validation_result.is_valid)
        self.assertTrue(result.artifact_validation_result.is_valid)
        self.assertTrue(artifact_path.exists())

    def test_does_not_write_subject_artifact_when_reference_validation_fails(self):
        self.write_category_csv(
            "code,legacy_code,is_active,sort_order,desired_status,name_en,description_en,name_hi-IN,description_hi-IN\n"
            "CAT001,,TRUE,1,published,Tattvagyan,Tattvagyan,तत्त्वज्ञान,तत्त्वज्ञान\n"
        )
        self.write_subject_csv(
            "code,legacy_code,is_active,sort_order,category_code,desired_status,name_en,description_en,name_hi-IN,description_hi-IN,from_date,to_date,prabodhan_count\n"
            "SUB001,,TRUE,1,CAT999,published,Shrimad Bhagvad Geeta,Shrimad Bhagvad Geeta,श्रीमद् भगवद्गीता,श्रीमद् भगवद्गीता,2006-01-20,2006-06-23,21\n"
        )

        result = self.with_config(lambda: write_subject_artifact(self.subject_source))

        self.assertFalse(result.csv_validation_result.is_valid)
        self.assertFalse(result.artifact_validation_result.is_valid)
        self.assertFalse((self.artifact_root / self.subject_source.artifact_path).exists())


if __name__ == "__main__":
    unittest.main()
