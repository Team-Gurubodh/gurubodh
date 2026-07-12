import json
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gurubodh_seed_data.cli import build_parser
from gurubodh_seed_data.glossary_ingestion import (
    APPROVED_GLOSSARY_TARGETS,
    LoadedGlossaryArtifact,
    apply_glossary_ingestion,
    build_glossary_payload,
    load_glossary_ingestion_artifacts,
    plan_glossary_ingestion,
    run_glossary_preflight,
)
from gurubodh_seed_data.ingestion_mode import IngestionMode
from gurubodh_seed_data.strapi_client import StrapiClientError


class FakeGlossaryClient:
    def __init__(self, failing_plural_api_id=None, records_by_plural_api_id=None):
        self.failing_plural_api_id = failing_plural_api_id
        self.records_by_plural_api_id = records_by_plural_api_id or {}
        self.get_collection_calls = []
        self.write_calls = []
        self.create_calls = []
        self.update_calls = []

    def get_collection(self, plural_api_id, filters=None, locale=None, status=None, page_size=100, page=None):
        self.get_collection_calls.append((plural_api_id, status, page_size))
        if plural_api_id == self.failing_plural_api_id:
            raise StrapiClientError("GET", f"http://localhost:1337/api/{plural_api_id}", status_code=404)
        records = self.records_by_plural_api_id.get(plural_api_id, ())
        if filters:
            for field, value in filters.items():
                records = tuple(record for record in records if record.get(field) == value)
        return {"data": list(records)}

    def create_document(self, plural_api_id, data, locale=None, publish=False):
        self.write_calls.append("create")
        self.create_calls.append((plural_api_id, data, locale, publish))
        return {"data": {**data, "documentId": "created-glossary-document-id"}}

    def update_document(self, plural_api_id, document_id, data, locale=None, publish=False):
        self.write_calls.append("update")
        self.update_calls.append((plural_api_id, document_id, data, locale, publish))
        return {"data": {**data, "documentId": document_id}}

    def publish_document(self, *_args, **_kwargs):
        self.write_calls.append("publish")
        raise AssertionError("Glossary dry-run must not publish documents.")


def glossary_record(code="T00001", term="anugraha", definition="grace"):
    return {
        "term_code": code,
        "term": term,
        "definition": definition,
    }


def strapi_glossary_record(
    code="T00001",
    document_id="glossary-document-id",
    numeric_id=1,
    term="anugraha",
    definition="grace",
):
    return {
        "id": numeric_id,
        "documentId": document_id,
        "code": code,
        "term": term,
        "definition": definition,
    }


def loaded_glossary_artifact(source_key, *records):
    target = APPROVED_GLOSSARY_TARGETS[source_key]
    return LoadedGlossaryArtifact(
        source_key=target.source_key,
        path=f"/tmp/{source_key}.json",
        record_count=len(records),
        collection_type=target.collection_type,
        plural_api_id=target.plural_api_id,
        display_name=target.display_name,
        artifact={
            "schema_version": 1,
            "workflow": "glossary",
            "source": {"key": target.source_key, "label": target.display_name},
            "strapi": {
                "collection_type": target.collection_type,
                "display_name": target.display_name,
            },
            "records": list(records),
        },
    )


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


class GlossaryPlanningTest(unittest.TestCase):
    def test_builds_glossary_payload_from_artifact_fields(self):
        payload = build_glossary_payload(glossary_record())

        self.assertEqual(
            {
                "code": "T00001",
                "term": "anugraha",
                "definition": "grace",
            },
            payload,
        )

    def test_dry_run_classifies_missing_glossary_record_as_create(self):
        client = FakeGlossaryClient()

        plan = plan_glossary_ingestion(
            client,
            (loaded_glossary_artifact("sanatan-glossary", glossary_record()),),
        )

        self.assertEqual(1, plan.to_create)
        self.assertEqual(0, plan.to_update)
        self.assertEqual(1, plan.publish_actions)
        self.assertEqual([], client.write_calls)

    def test_dry_run_classifies_changed_glossary_record_as_update(self):
        client = FakeGlossaryClient(
            records_by_plural_api_id={
                "sanatan-glossaries": (
                    strapi_glossary_record(definition="old definition"),
                )
            }
        )

        plan = plan_glossary_ingestion(
            client,
            (loaded_glossary_artifact("sanatan-glossary", glossary_record()),),
        )

        self.assertEqual(0, plan.to_create)
        self.assertEqual(1, plan.to_update)
        self.assertEqual(1, plan.publish_actions)
        self.assertEqual("glossary-document-id", plan.items[0].document_id)

    def test_dry_run_classifies_matching_glossary_record(self):
        client = FakeGlossaryClient(
            records_by_plural_api_id={
                "sanatan-glossaries": (strapi_glossary_record(),)
            }
        )

        plan = plan_glossary_ingestion(
            client,
            (loaded_glossary_artifact("sanatan-glossary", glossary_record()),),
        )

        self.assertEqual(1, plan.already_matching)
        self.assertEqual(0, plan.publish_actions)

    def test_reports_duplicate_artifact_codes_within_one_glossary(self):
        plan = plan_glossary_ingestion(
            FakeGlossaryClient(),
            (
                loaded_glossary_artifact(
                    "sanatan-glossary",
                    glossary_record(),
                    glossary_record(term="second term"),
                ),
            ),
        )

        self.assertEqual(1, plan.conflicts)
        self.assertIn("Duplicate artifact term_code", plan.messages[0])

    def test_allows_same_code_across_different_glossary_collections(self):
        plan = plan_glossary_ingestion(
            FakeGlossaryClient(),
            (
                loaded_glossary_artifact("sanatan-glossary", glossary_record()),
                loaded_glossary_artifact("prabodhan-glossary", glossary_record()),
            ),
        )

        self.assertEqual(0, plan.conflicts)
        self.assertEqual(2, plan.to_create)

    def test_reports_duplicate_existing_code_within_one_glossary(self):
        client = FakeGlossaryClient(
            records_by_plural_api_id={
                "sanatan-glossaries": (
                    strapi_glossary_record(document_id="one"),
                    strapi_glossary_record(document_id="two"),
                )
            }
        )

        plan = plan_glossary_ingestion(
            client,
            (loaded_glossary_artifact("sanatan-glossary", glossary_record()),),
        )

        self.assertEqual(1, plan.conflicts)
        self.assertIn("Duplicate existing Sanatan Glossary records", plan.messages[0])

    def test_deduplicates_same_document_returned_with_different_numeric_ids(self):
        client = FakeGlossaryClient(
            records_by_plural_api_id={
                "sanatan-glossaries": (
                    strapi_glossary_record(numeric_id=1),
                    strapi_glossary_record(numeric_id=2),
                )
            }
        )

        plan = plan_glossary_ingestion(
            client,
            (loaded_glossary_artifact("sanatan-glossary", glossary_record()),),
        )

        self.assertEqual(0, plan.conflicts)
        self.assertEqual(1, plan.already_matching)

    def test_reports_missing_required_artifact_values(self):
        plan = plan_glossary_ingestion(
            FakeGlossaryClient(),
            (
                loaded_glossary_artifact(
                    "sanatan-glossary",
                    {"term_code": "T00001", "term": "", "definition": "grace"},
                ),
            ),
        )

        self.assertEqual(1, plan.conflicts)
        self.assertIn("Missing required artifact value: term", plan.messages[0])

    def test_reports_missing_required_strapi_fields(self):
        client = FakeGlossaryClient(
            records_by_plural_api_id={
                "sanatan-glossaries": (
                    {
                        "id": 1,
                        "documentId": "glossary-document-id",
                        "code": "T00001",
                        "term": "anugraha",
                    },
                )
            }
        )

        plan = plan_glossary_ingestion(
            client,
            (loaded_glossary_artifact("sanatan-glossary", glossary_record()),),
        )

        self.assertEqual(1, plan.conflicts)
        self.assertIn("missing required Strapi field: definition", plan.messages[0])


class GlossaryApplyTest(unittest.TestCase):
    def test_dry_run_mode_cannot_apply(self):
        client = FakeGlossaryClient()
        plan = plan_glossary_ingestion(
            client,
            (loaded_glossary_artifact("sanatan-glossary", glossary_record()),),
        )

        with self.assertRaisesRegex(RuntimeError, "Dry-run mode cannot perform"):
            apply_glossary_ingestion(client, IngestionMode(), plan)

        self.assertEqual([], client.write_calls)

    def test_apply_is_blocked_by_conflicts(self):
        client = FakeGlossaryClient()
        plan = plan_glossary_ingestion(
            client,
            (
                loaded_glossary_artifact(
                    "sanatan-glossary",
                    glossary_record(),
                    glossary_record(term="duplicate"),
                ),
            ),
        )

        with self.assertRaisesRegex(RuntimeError, "conflicts or blocked records"):
            apply_glossary_ingestion(client, IngestionMode(apply=True), plan)

        self.assertEqual([], client.write_calls)

    def test_apply_creates_missing_glossary_record_as_published(self):
        client = FakeGlossaryClient()
        plan = plan_glossary_ingestion(
            client,
            (loaded_glossary_artifact("sanatan-glossary", glossary_record()),),
        )

        apply_glossary_ingestion(client, IngestionMode(apply=True), plan)

        self.assertEqual(
            [
                (
                    "sanatan-glossaries",
                    {"code": "T00001", "term": "anugraha", "definition": "grace"},
                    None,
                    True,
                )
            ],
            client.create_calls,
        )
        self.assertEqual([], client.update_calls)

    def test_apply_updates_changed_glossary_record_as_published(self):
        client = FakeGlossaryClient(
            records_by_plural_api_id={
                "sanatan-glossaries": (
                    strapi_glossary_record(definition="old definition"),
                )
            }
        )
        plan = plan_glossary_ingestion(
            client,
            (loaded_glossary_artifact("sanatan-glossary", glossary_record()),),
        )

        apply_glossary_ingestion(client, IngestionMode(apply=True), plan)

        self.assertEqual([], client.create_calls)
        self.assertEqual(
            [
                (
                    "sanatan-glossaries",
                    "glossary-document-id",
                    {"code": "T00001", "term": "anugraha", "definition": "grace"},
                    None,
                    True,
                )
            ],
            client.update_calls,
        )


class GlossaryIngestionCliTest(unittest.TestCase):
    def test_glossary_stage2_command_does_not_accept_apply_mode(self):
        parser = build_parser()

        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(("ingest", "glossary-preflight", "--apply"))

    def test_glossary_stage4_command_accepts_apply_mode(self):
        parser = build_parser()

        args = parser.parse_args(("ingest", "glossary-plan", "--apply"))

        self.assertTrue(args.apply)


if __name__ == "__main__":
    unittest.main()
