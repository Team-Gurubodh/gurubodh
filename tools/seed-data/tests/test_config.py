import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from gurubodh_seed_data.config import load_seed_data_config


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


if __name__ == "__main__":
    unittest.main()
