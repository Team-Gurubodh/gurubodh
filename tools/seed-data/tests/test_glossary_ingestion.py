import json
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gurubodh_seed_data.cli import build_parser
from gurubodh_seed_data.glossary_ingestion import (
    load_glossary_ingestion_artifacts,
    run_glossary_preflight,
)
from gurubodh_seed_data.strapi_client import StrapiClientError


class FakeGlossaryClient:
    def __init__(self, failing_plural_api_id=None):
        self.failing_plural_api_id = failing_plural_api_id
        self.get_collection_calls = []
        self.write_calls = []

    def get_collection(self, plural_api_id, filters=None, locale=None, status=None, page_size=100, page=None):
        self.get_collection_calls.append((plural_api_id, status, page_size))
        if plural_api_id == self.failing_plural_api_id:
            raise StrapiClientError("GET", f"http://localhost:1337/api/{plural_api_id}", status_code=404)
        return {"data": []}

    def create_document(self, *_args, **_kwargs):
        self.write_calls.append("create")
        raise AssertionError("Glossary Stage 2 must not create documents.")

    def update_document(self, *_args, **_kwargs):
        self.write_calls.append("update")
        raise AssertionError("Glossary Stage 2 must not update documents.")

    def publish_document(self, *_args, **_kwargs):
        self.write_calls.append("publish")
        raise AssertionError("Glossary Stage 2 must not publish documents.")


class GlossaryIngestionArtifactLoadTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.artifact_root = self.root / "artifacts"
        (self.artifact_root / "glossary").mkdir(parents=True)
        self.config_path = self.root / "seed_data_sources.json"
        self.config_path.write_text(
            "{\n"
            '  "schema_version": 1,\n'
            f'  "source_root": "{self.root / "csv_import"}",\n'
            f'  "artifact_root": "{self.artifact_root}",\n'
            '  "workflows": [\n'
            '    {"key": "glossary", "status": "scaffolded", "description": "Glossary"}\n'
            '  ],\n'
            '  "sources": [\n'
            '    {"key": "sanatan-glossary", "workflow": "glossary", "label": "Sanatan Glossary", "csv_path": "glossary/sanatan-glossary.csv", "artifact_path": "glossary/sanatan-glossary.json"},\n'
            '    {"key": "prabodhan-glossary", "workflow": "glossary", "label": "Prabodhan Glossary", "csv_path": "glossary/prabodhan-glossary.csv", "artifact_path": "glossary/prabodhan-glossary.json"}\n'
            '  ]\n'
            "}\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_artifact(self, source_key, record_count=1, collection_type=None):
        records = [
            {
                "term_code": f"T{index + 1:05d}",
                "term": f"Term {index + 1}",
                "definition": f"Definition {index + 1}",
            }
            for index in range(record_count)
        ]
        path = self.artifact_root / "glossary" / f"{source_key}.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "workflow": "glossary",
                    "source": {"key": source_key, "label": source_key},
                    "strapi": {
                        "collection_type": collection_type or source_key,
                        "display_name": source_key,
                    },
                    "records": records,
                }
            ),
            encoding="utf-8",
        )

    def with_config(self, callback):
        with patch("gurubodh_seed_data.config.DEFAULT_CONFIG_PATH", self.config_path):
            return callback()

    def test_loads_reviewed_glossary_artifacts(self):
        self.write_artifact("sanatan-glossary", record_count=5)
        self.write_artifact("prabodhan-glossary", record_count=19)

        result = self.with_config(load_glossary_ingestion_artifacts)

        self.assertTrue(result.is_valid)
        self.assertEqual(2, len(result.artifacts))
        self.assertEqual(24, result.total_records)
        self.assertEqual("sanatan-glossaries", result.artifacts[0].plural_api_id)

    def test_reports_missing_glossary_artifacts(self):
        result = self.with_config(load_glossary_ingestion_artifacts)

        self.assertFalse(result.is_valid)
        self.assertEqual(2, len(result.errors))
        self.assertTrue(result.errors[0].startswith("sanatan-glossary artifact not found"))

    def test_rejects_unapproved_glossary_collection_target(self):
        self.write_artifact("sanatan-glossary", collection_type="category")
        self.write_artifact("prabodhan-glossary")

        result = self.with_config(load_glossary_ingestion_artifacts)

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("collection_type must be sanatan-glossary" in error for error in result.errors)
        )

    def test_rejects_invalid_glossary_artifact_schema(self):
        path = self.artifact_root / "glossary" / "sanatan-glossary.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "workflow": "glossary",
                    "source": {"key": "sanatan-glossary", "label": "Sanatan Glossary"},
                    "strapi": {
                        "collection_type": "sanatan-glossary",
                        "display_name": "Sanatan Glossary",
                    },
                    "records": [{"term": "Term", "definition": "Definition"}],
                }
            ),
            encoding="utf-8",
        )
        self.write_artifact("prabodhan-glossary")

        result = self.with_config(load_glossary_ingestion_artifacts)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("$.records[0].term_code is required" in error for error in result.errors))


class GlossaryPreflightTest(unittest.TestCase):
    def test_preflight_passes_for_accessible_glossary_endpoints(self):
        client = FakeGlossaryClient()

        result = run_glossary_preflight(client)

        self.assertTrue(result.is_valid)
        self.assertEqual(4, len(result.checks))
        self.assertEqual(
            [
                ("sanatan-glossaries", None, 1),
                ("sanatan-glossaries", "draft", 1),
                ("prabodhan-glossaries", None, 1),
                ("prabodhan-glossaries", "draft", 1),
            ],
            client.get_collection_calls,
        )
        self.assertEqual([], client.write_calls)

    def test_preflight_fails_when_glossary_endpoint_is_missing(self):
        client = FakeGlossaryClient(failing_plural_api_id="prabodhan-glossaries")

        result = run_glossary_preflight(client)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("Cannot read prabodhan-glossaries" in error for error in result.errors))


class GlossaryIngestionCliTest(unittest.TestCase):
    def test_glossary_stage2_command_does_not_accept_apply_mode(self):
        parser = build_parser()

        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(("ingest", "glossary-preflight", "--apply"))


if __name__ == "__main__":
    unittest.main()
