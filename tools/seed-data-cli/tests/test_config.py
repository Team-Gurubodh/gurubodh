import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gurubodh_seed_data.category import get_category_source, list_category_sources
from gurubodh_seed_data.config import load_seed_data_config
from gurubodh_seed_data.paths import category_paths, subject_paths
from gurubodh_seed_data.subject import get_subject_source, list_subject_sources


class SeedDataConfigTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.config_path = self.root / "seed_data_sources.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_config(self, body):
        self.config_path.write_text(body, encoding="utf-8")

    def test_loads_workflows_and_sources(self):
        self.write_config(
            "{\n"
            '  "schema_version": 1,\n'
            '  "source_root": "/tmp/seed-data",\n'
            '  "artifact_root": "artifacts",\n'
            '  "workflows": [\n'
            '    {"key": "glossary", "status": "scaffolded", "description": "Glossary"}\n'
            '  ],\n'
            '  "sources": [\n'
            '    {"key": "sanatan-glossary", "workflow": "glossary", "label": "Sanatan Glossary", "csv_path": "glossary/sanatan-glossary.csv", "artifact_path": "glossary/sanatan-glossary.json"}\n'
            '  ]\n'
            "}\n"
        )

        config = load_seed_data_config(self.config_path)

        self.assertEqual(1, config.schema_version)
        self.assertEqual(("glossary",), tuple(workflow.key for workflow in config.workflows))
        self.assertEqual(
            ("sanatan-glossary",),
            tuple(source.key for source in config.sources_for_workflow("glossary")),
        )
        self.assertEqual(
            "Sanatan Glossary",
            config.get_source("glossary", "sanatan-glossary").label,
        )

    def test_rejects_source_for_unknown_workflow(self):
        self.write_config(
            "{\n"
            '  "schema_version": 1,\n'
            '  "source_root": "/tmp/seed-data",\n'
            '  "artifact_root": "artifacts",\n'
            '  "workflows": [\n'
            '    {"key": "glossary", "status": "scaffolded", "description": "Glossary"}\n'
            '  ],\n'
            '  "sources": [\n'
            '    {"key": "subjects", "workflow": "subject", "label": "Subjects", "csv_path": "subject/subjects.csv", "artifact_path": "subject/subjects.json"}\n'
            '  ]\n'
            "}\n"
        )

        with self.assertRaisesRegex(ValueError, "unsupported workflow"):
            load_seed_data_config(self.config_path)

    def test_category_and_subject_source_lookup_and_paths(self):
        self.write_config(
            "{\n"
            '  "schema_version": 1,\n'
            '  "source_root": "/tmp/seed-data",\n'
            '  "artifact_root": "artifacts",\n'
            '  "workflows": [\n'
            '    {"key": "category", "status": "scaffolded", "description": "Category"},\n'
            '    {"key": "subject", "status": "scaffolded", "description": "Subject"}\n'
            '  ],\n'
            '  "sources": [\n'
            '    {"key": "categories", "workflow": "category", "label": "Categories", "csv_path": "category/categories.csv", "artifact_path": "category/categories.json"},\n'
            '    {"key": "subjects", "workflow": "subject", "label": "Subjects", "csv_path": "subject/subjects.csv", "artifact_path": "subject/subjects.json"}\n'
            '  ]\n'
            "}\n"
        )

        with patch("gurubodh_seed_data.config.DEFAULT_CONFIG_PATH", self.config_path):
            self.assertEqual(("categories",), tuple(source.key for source in list_category_sources()))
            self.assertEqual(("subjects",), tuple(source.key for source in list_subject_sources()))
            category = get_category_source("categories")
            subject = get_subject_source("subjects")

            self.assertEqual(
                Path("/tmp/seed-data/category/categories.csv"),
                category_paths(category).csv_input,
            )
            self.assertTrue(str(subject_paths(subject).json_output).endswith("artifacts/subject/subjects.json"))


if __name__ == "__main__":
    unittest.main()
