import unittest

from gurubodh_seed_data.category_ingestion import (
    apply_category_ingestion,
    build_category_payloads,
    plan_category_ingestion,
)
from gurubodh_seed_data.ingestion_mode import IngestionMode
from gurubodh_seed_data.strapi_config import load_strapi_config


def category_artifact(*records):
    return {
        "schema_version": 1,
        "workflow": "category",
        "records": list(records),
    }


def category_record(
    code="CAT001",
    sort_order=1,
    desired_status="published",
    name_en="Tattvagyan",
    name_hi_IN="तत्त्वज्ञान",
):
    return {
        "category_code": code,
        "legacy_code": None,
        "is_active": True,
        "sort_order": sort_order,
        "desired_status": desired_status,
        "name_en": name_en,
        "description_en": name_en,
        "name_hi_IN": name_hi_IN,
        "description_hi_IN": name_hi_IN,
    }


def strapi_category(
    code="CAT001",
    document_id="category-document-id",
    sort_order=1,
    name="Tattvagyan",
    description="Tattvagyan",
    locale="en",
):
    return {
        "id": 1,
        "documentId": document_id,
        "code": code,
        "legacy_code": None,
        "is_active": True,
        "sort_order": sort_order,
        "name": name,
        "description": description,
        "locale": locale,
    }


class FakeCategoryClient:
    def __init__(self, records_by_locale=None):
        self.records_by_locale = records_by_locale or {}
        self.create_calls = []
        self.localization_calls = []
        self.update_calls = []
        self.publish_calls = []

    def get_collection(self, plural_api_id, filters=None, locale=None, status=None, page_size=100):
        records = self.records_by_locale.get(locale, ())
        if filters:
            for field, value in filters.items():
                records = tuple(record for record in records if record.get(field) == value)
        return {"data": list(records)}

    def create_document(self, plural_api_id, data, locale=None, publish=False):
        self.create_calls.append((plural_api_id, data, locale, publish))
        return {
            "data": {
                **data,
                "documentId": "created-document-id",
                "locale": locale,
            }
        }

    def create_localization(self, plural_api_id, document_id, data, locale=None, publish=False):
        self.localization_calls.append((plural_api_id, document_id, data, locale, publish))
        return {
            "data": {
                **data,
                "documentId": document_id,
                "locale": locale,
            }
        }

    def update_document(self, plural_api_id, document_id, data, locale=None, publish=False):
        self.update_calls.append((plural_api_id, document_id, data, locale, publish))
        return {"data": {**data, "documentId": document_id, "locale": locale}}

    def publish_document(self, plural_api_id, document_id, locale=None):
        self.publish_calls.append((plural_api_id, document_id, locale))
        return {"data": {"documentId": document_id, "locale": locale}}


class CategoryIngestionTest(unittest.TestCase):
    def setUp(self):
        self.config = load_strapi_config(
            base_url="http://localhost:1337",
            api_token="token",
            environ={},
        )

    def test_builds_category_payloads_from_artifact_fields(self):
        default_payload, localized_payload = build_category_payloads(category_record())

        self.assertEqual(
            {
                "code": "CAT001",
                "legacy_code": None,
                "is_active": True,
                "sort_order": 1,
                "name": "Tattvagyan",
                "description": "Tattvagyan",
            },
            default_payload,
        )
        self.assertEqual("तत्त्वज्ञान", localized_payload["name"])

    def test_dry_run_classifies_missing_category_as_create(self):
        plan = plan_category_ingestion(
            FakeCategoryClient(),
            self.config,
            category_artifact(category_record()),
        )

        self.assertEqual(1, plan.to_create)
        self.assertEqual(0, plan.to_update)
        self.assertEqual(2, plan.publish_actions)

    def test_dry_run_classifies_changed_category_as_update(self):
        client = FakeCategoryClient(
            {
                "en": (strapi_category(name="Old name", description="Old name"),),
                "hi-IN": (
                    strapi_category(
                        name="तत्त्वज्ञान",
                        description="तत्त्वज्ञान",
                        locale="hi-IN",
                    ),
                ),
            }
        )

        plan = plan_category_ingestion(client, self.config, category_artifact(category_record()))

        self.assertEqual(0, plan.to_create)
        self.assertEqual(1, plan.to_update)
        self.assertTrue(plan.items[0].update_default)
        self.assertFalse(plan.items[0].update_localized)

    def test_dry_run_classifies_matching_category(self):
        client = FakeCategoryClient(
            {
                "en": (strapi_category(),),
                "hi-IN": (
                    strapi_category(
                        name="तत्त्वज्ञान",
                        description="तत्त्वज्ञान",
                        locale="hi-IN",
                    ),
                ),
            }
        )

        plan = plan_category_ingestion(client, self.config, category_artifact(category_record()))

        self.assertEqual(1, plan.already_matching)
        self.assertEqual(0, plan.publish_actions)

    def test_reports_duplicate_existing_code_conflict(self):
        client = FakeCategoryClient(
            {
                "en": (
                    strapi_category(document_id="one"),
                    strapi_category(document_id="two"),
                )
            }
        )

        plan = plan_category_ingestion(client, self.config, category_artifact(category_record()))

        self.assertEqual(1, plan.conflicts)
        self.assertIn("Duplicate existing Category records", plan.messages[0])

    def test_reports_existing_sort_order_conflict(self):
        client = FakeCategoryClient(
            {
                "en": (strapi_category(code="CAT999", sort_order=1),),
            }
        )

        plan = plan_category_ingestion(client, self.config, category_artifact(category_record()))

        self.assertEqual(1, plan.conflicts)
        self.assertIn("sort_order 1 is already used", plan.messages[0])

    def test_uses_orphan_localized_record_document_id_to_create_default_locale(self):
        client = FakeCategoryClient(
            {
                "hi-IN": (
                    strapi_category(
                        name="तत्त्वज्ञान",
                        description="तत्त्वज्ञान",
                        locale="hi-IN",
                    ),
                ),
            }
        )

        plan = plan_category_ingestion(client, self.config, category_artifact(category_record()))

        self.assertEqual(0, plan.conflicts)
        self.assertEqual(1, plan.to_update)
        self.assertTrue(plan.items[0].update_default)
        self.assertEqual("category-document-id", plan.items[0].document_id)

    def test_apply_publishes_create_even_when_artifact_desired_status_is_draft(self):
        client = FakeCategoryClient()
        plan = plan_category_ingestion(
            client,
            self.config,
            category_artifact(category_record(desired_status="draft")),
        )

        apply_category_ingestion(client, self.config, IngestionMode(apply=True), plan)

        self.assertEqual(1, len(client.create_calls))
        self.assertEqual(1, len(client.localization_calls))
        self.assertTrue(client.create_calls[0][3])
        self.assertTrue(client.localization_calls[0][4])

    def test_dry_run_mode_cannot_apply(self):
        client = FakeCategoryClient()
        plan = plan_category_ingestion(
            client,
            self.config,
            category_artifact(category_record()),
        )

        with self.assertRaisesRegex(RuntimeError, "Dry-run mode cannot perform"):
            apply_category_ingestion(client, self.config, IngestionMode(), plan)


if __name__ == "__main__":
    unittest.main()
