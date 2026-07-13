import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gurubodh_seed_data.strapi_client import StrapiClientError
from gurubodh_seed_data.strapi_config import load_strapi_config
from gurubodh_seed_data.target_ingestion import (
    INGEST_TARGET_REGISTRY,
    load_target_artifact,
    run_target_preflight,
)


class FakeTargetPreflightClient:
    def __init__(self, failing_plural_api_id=None):
        self.failing_plural_api_id = failing_plural_api_id
        self.get_collection_calls = []
        self.write_calls = []

    def get_collection(self, plural_api_id, page_size=100, status=None, **_kwargs):
        self.get_collection_calls.append((plural_api_id, status, page_size))
        if plural_api_id == self.failing_plural_api_id:
            raise StrapiClientError(
                "GET",
                f"http://localhost:1337/api/{plural_api_id}",
                status_code=404,
            )
        return {"data": []}

    def get_locales(self):
        return [
            {"code": "en", "isDefault": True},
            {"code": "hi-IN", "isDefault": False},
        ]

    def create_document(self, *_args, **_kwargs):
        self.write_calls.append("create")

    def update_document(self, *_args, **_kwargs):
        self.write_calls.append("update")

    def publish_document(self, *_args, **_kwargs):
        self.write_calls.append("publish")


def category_artifact():
    return {
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
                "name_hi_IN": "Tattvagyan",
                "description_hi_IN": "Tattvagyan",
            }
        ],
    }


def subject_artifact():
    return {
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
                "name_en": "Swasthya Rahasya",
                "description_en": "Swasthya Rahasya",
                "name_hi_IN": "Swasthya Rahasya",
                "description_hi_IN": "Swasthya Rahasya",
                "from_date": None,
                "to_date": None,
                "prabodhan_count": None,
            }
        ],
    }


def glossary_artifact(source_key):
    return {
        "schema_version": 1,
        "workflow": "glossary",
        "source": {"key": source_key, "label": source_key},
        "strapi": {"collection_type": source_key, "display_name": source_key},
        "records": [
            {
                "term_code": "T00001",
                "term": "anugraha",
                "definition": "grace",
            }
        ],
    }


VALID_ARTIFACTS = {
    "category": ("category/categories.json", category_artifact),
    "subject": ("subject/subjects.json", subject_artifact),
    "sanatan-glossary": (
        "glossary/sanatan-glossary.json",
        lambda: glossary_artifact("sanatan-glossary"),
    ),
    "prabodhan-glossary": (
        "glossary/prabodhan-glossary.json",
        lambda: glossary_artifact("prabodhan-glossary"),
    ),
}


class TargetArtifactLoadTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.artifact_root = self.root / "artifacts"
        (self.artifact_root / "category").mkdir(parents=True)
        (self.artifact_root / "subject").mkdir(parents=True)
        (self.artifact_root / "glossary").mkdir(parents=True)
        self.config_path = self.root / "seed_data_sources.json"
        self.config_path.write_text(
            "{\n"
            '  "schema_version": 1,\n'
            f'  "source_root": "{self.root / "csv_import"}",\n'
            f'  "artifact_root": "{self.artifact_root}",\n'
            '  "workflows": [\n'
            '    {"key": "category", "status": "scaffolded", "description": "Category"},\n'
            '    {"key": "subject", "status": "scaffolded", "description": "Subject"},\n'
            '    {"key": "glossary", "status": "scaffolded", "description": "Glossary"}\n'
            '  ],\n'
            '  "sources": [\n'
            '    {"key": "categories", "workflow": "category", "label": "Categories", "csv_path": "category/categories.csv", "artifact_path": "category/categories.json"},\n'
            '    {"key": "subjects", "workflow": "subject", "label": "Subjects", "csv_path": "subject/subjects.csv", "artifact_path": "subject/subjects.json"},\n'
            '    {"key": "sanatan-glossary", "workflow": "glossary", "label": "Sanatan Glossary", "csv_path": "glossary/sanatan-glossary.csv", "artifact_path": "glossary/sanatan-glossary.json"},\n'
            '    {"key": "prabodhan-glossary", "workflow": "glossary", "label": "Prabodhan Glossary", "csv_path": "glossary/prabodhan-glossary.csv", "artifact_path": "glossary/prabodhan-glossary.json"}\n'
            '  ]\n'
            "}\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_json(self, relative_path, value):
        path = self.artifact_root / relative_path
        path.write_text(json.dumps(value), encoding="utf-8")

    def write_text(self, relative_path, value):
        path = self.artifact_root / relative_path
        path.write_text(value, encoding="utf-8")

    def with_config(self, callback):
        with patch("gurubodh_seed_data.config.DEFAULT_CONFIG_PATH", self.config_path):
            return callback()

    def test_target_registry_contains_only_task_13_targets(self):
        self.assertEqual(
            (
                "category",
                "subject",
                "sanatan-glossary",
                "prabodhan-glossary",
            ),
            tuple(INGEST_TARGET_REGISTRY),
        )

    def test_loads_each_target_specific_artifact(self):
        for target_key, (relative_path, artifact_factory) in VALID_ARTIFACTS.items():
            with self.subTest(target_key=target_key):
                self.write_json(relative_path, artifact_factory())

                result = self.with_config(lambda: load_target_artifact(target_key))

                self.assertTrue(result.is_valid)
                self.assertEqual(target_key, result.artifact.target_key)
                self.assertEqual(1, result.total_records)

    def test_reports_missing_artifact_for_each_target(self):
        for target_key in VALID_ARTIFACTS:
            with self.subTest(target_key=target_key):
                result = self.with_config(lambda: load_target_artifact(target_key))

                self.assertFalse(result.is_valid)
                self.assertIn("artifact not found", result.errors[0])

    def test_reports_malformed_json_for_each_target(self):
        for target_key, (relative_path, _artifact_factory) in VALID_ARTIFACTS.items():
            with self.subTest(target_key=target_key):
                self.write_text(relative_path, "{")

                result = self.with_config(lambda: load_target_artifact(target_key))

                self.assertFalse(result.is_valid)
                self.assertIn("artifact is not valid JSON", result.errors[0])

    def test_reports_schema_invalid_artifact_for_each_target(self):
        for target_key, (relative_path, artifact_factory) in VALID_ARTIFACTS.items():
            with self.subTest(target_key=target_key):
                artifact = artifact_factory()
                artifact["records"] = [{}]
                self.write_json(relative_path, artifact)

                result = self.with_config(lambda: load_target_artifact(target_key))

                self.assertFalse(result.is_valid)
                self.assertTrue(
                    any("artifact validation failed" in error for error in result.errors)
                )

    def test_rejects_sanatan_artifact_routed_to_prabodhan_target(self):
        artifact = glossary_artifact("sanatan-glossary")
        self.write_json("glossary/prabodhan-glossary.json", artifact)

        result = self.with_config(lambda: load_target_artifact("prabodhan-glossary"))

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("source key must be prabodhan-glossary" in error for error in result.errors)
        )
        self.assertTrue(
            any("collection_type must be prabodhan-glossary" in error for error in result.errors)
        )

    def test_rejects_prabodhan_artifact_routed_to_sanatan_target(self):
        artifact = glossary_artifact("prabodhan-glossary")
        self.write_json("glossary/sanatan-glossary.json", artifact)

        result = self.with_config(lambda: load_target_artifact("sanatan-glossary"))

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("source key must be sanatan-glossary" in error for error in result.errors)
        )
        self.assertTrue(
            any("collection_type must be sanatan-glossary" in error for error in result.errors)
        )


class TargetPreflightTest(unittest.TestCase):
    def setUp(self):
        self.config = load_strapi_config(
            base_url="http://localhost:1337",
            api_token="token",
            environ={},
        )

    def test_category_preflight_checks_only_category_readiness(self):
        client = FakeTargetPreflightClient()

        result = run_target_preflight(client, self.config, "category")

        self.assertTrue(result.is_valid)
        self.assertEqual(
            [
                ("categories", None, 1),
                ("categories", "draft", 1),
            ],
            client.get_collection_calls,
        )
        self.assertEqual([], client.write_calls)

    def test_subject_preflight_checks_subject_and_category_read_access(self):
        client = FakeTargetPreflightClient()

        result = run_target_preflight(client, self.config, "subject")

        self.assertTrue(result.is_valid)
        self.assertEqual(
            [
                ("subjects", None, 1),
                ("categories", None, 1),
                ("subjects", "draft", 1),
            ],
            client.get_collection_calls,
        )
        self.assertEqual([], client.write_calls)

    def test_subject_preflight_fails_when_category_dependency_read_fails(self):
        client = FakeTargetPreflightClient(failing_plural_api_id="categories")

        result = run_target_preflight(client, self.config, "subject")

        self.assertFalse(result.is_valid)
        self.assertTrue(any("Cannot read categories" in error for error in result.errors))
        self.assertEqual([], client.write_calls)

    def test_glossary_preflight_checks_only_selected_glossary_target(self):
        client = FakeTargetPreflightClient()

        result = run_target_preflight(client, self.config, "sanatan-glossary")

        self.assertTrue(result.is_valid)
        self.assertEqual(
            [
                ("sanatan-glossaries", None, 1),
                ("sanatan-glossaries", "draft", 1),
            ],
            client.get_collection_calls,
        )
        self.assertEqual([], client.write_calls)


if __name__ == "__main__":
    unittest.main()
