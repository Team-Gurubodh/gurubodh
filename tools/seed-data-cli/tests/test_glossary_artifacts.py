import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gurubodh_seed_data.config import SeedDataSource
from gurubodh_seed_data.glossary_artifacts import (
    build_glossary_artifact,
    validate_glossary_artifact,
    write_glossary_artifact,
)


class GlossaryArtifactTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source_root = self.root / "csv_import"
        self.artifact_root = self.root / "artifacts"
        self.source_dir = self.source_root / "glossary"
        self.source_dir.mkdir(parents=True)
        self.config_path = self.root / "seed_data_sources.json"
        self.config_path.write_text(
            "{\n"
            '  "schema_version": 1,\n'
            f'  "source_root": "{self.source_root}",\n'
            f'  "artifact_root": "{self.artifact_root}",\n'
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

    def with_config(self, callback):
        with patch("gurubodh_seed_data.config.DEFAULT_CONFIG_PATH", self.config_path):
            return callback()

    def test_builds_glossary_artifact_shape(self):
        self.write_csv(
            "Sr No,Term Code,Term,Definition\n"
            "1,T00001,anirvachaneeya,indescribable\n"
            "2,T00002,समष्टि,समष्टि \n"
        )

        artifact = self.with_config(lambda: build_glossary_artifact(self.source))

        self.assertEqual(1, artifact["schema_version"])
        self.assertEqual("glossary", artifact["workflow"])
        self.assertEqual(
            {"key": "test-glossary", "label": "Test Glossary"},
            artifact["source"],
        )
        self.assertEqual(
            {
                "collection_type": "test-glossary",
                "display_name": "Test Glossary",
            },
            artifact["strapi"],
        )
        self.assertEqual(
            [
                {
                    "term_code": "T00001",
                    "term": "anirvachaneeya",
                    "definition": "indescribable",
                },
                {
                    "term_code": "T00002",
                    "term": "समष्टि",
                    "definition": "समष्टि",
                },
            ],
            artifact["records"],
        )
        self.assertTrue(validate_glossary_artifact(artifact).is_valid)

    def test_writes_valid_artifact_after_csv_validation(self):
        self.write_csv(
            "Sr No,Term Code,Term,Definition\n"
            "1,T00001,anirvachaneeya,indescribable\n"
        )

        result = self.with_config(lambda: write_glossary_artifact(self.source))

        artifact_path = self.artifact_root / self.source.artifact_path
        self.assertTrue(result.csv_validation_result.is_valid)
        self.assertTrue(result.artifact_validation_result.is_valid)
        self.assertEqual(1, result.record_count)
        self.assertTrue(artifact_path.exists())

        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        self.assertEqual("test-glossary", artifact["source"]["key"])
        self.assertEqual("test-glossary", artifact["strapi"]["collection_type"])
        self.assertEqual("T00001", artifact["records"][0]["term_code"])

    def test_does_not_write_artifact_when_csv_validation_fails(self):
        self.write_csv(
            "Sr No,Term Code,Term,Definition\n"
            "1,T00001, duplicate ,definition\n"
        )

        result = self.with_config(lambda: write_glossary_artifact(self.source))

        artifact_path = self.artifact_root / self.source.artifact_path
        self.assertFalse(result.csv_validation_result.is_valid)
        self.assertFalse(result.artifact_validation_result.is_valid)
        self.assertEqual(0, result.record_count)
        self.assertFalse(artifact_path.exists())

    def test_artifact_validation_rejects_strapi_internal_fields(self):
        artifact = {
            "schema_version": 1,
            "workflow": "glossary",
            "source": {
                "key": "test-glossary",
                "label": "Test Glossary",
            },
            "strapi": {
                "collection_type": "test-glossary",
                "display_name": "Test Glossary",
            },
            "records": [
                {
                    "id": 1,
                    "term_code": "T00001",
                    "term": "anirvachaneeya",
                    "definition": "indescribable",
                }
            ],
        }

        result = validate_glossary_artifact(artifact)

        self.assertFalse(result.is_valid)
        self.assertIn(
            "$.records[0].id is not allowed.",
            result.errors,
        )


if __name__ == "__main__":
    unittest.main()
