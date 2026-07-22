import unittest

from gurubodh_seed_data.ingestion_mode import IngestionMode
from gurubodh_seed_data.strapi_config import load_strapi_config
from gurubodh_seed_data.subject_ingestion import (
    apply_subject_ingestion,
    build_subject_payloads,
    plan_subject_ingestion,
)


def subject_artifact(*records):
    return {
        "schema_version": 1,
        "workflow": "subject",
        "records": list(records),
    }


def subject_record(
    code="SUB001",
    sort_order=1,
    category_code="CAT001",
    desired_status="published",
    name_en="Shrimad Bhagvad Geeta",
    name_hi_IN="श्रीमद् भगवद्गीता",
):
    return {
        "subject_code": code,
        "legacy_code": None,
        "is_active": True,
        "sort_order": sort_order,
        "category_code": category_code,
        "desired_status": desired_status,
        "name_en": name_en,
        "description_en": name_en,
        "name_hi_IN": name_hi_IN,
        "description_hi_IN": name_hi_IN,
        "from_date": "2006-01-20",
        "to_date": "2006-06-23",
        "prabodhan_count": 21,
    }


def strapi_category(
    code="CAT001",
    document_id="category-document-id",
    sort_order=1,
    locale="en",
):
    return {
        "id": 1,
        "documentId": document_id,
        "code": code,
        "sort_order": sort_order,
        "locale": locale,
    }


def strapi_subject(
    code="SUB001",
    document_id="subject-document-id",
    sort_order=1,
    name="Shrimad Bhagvad Geeta",
    description="Shrimad Bhagvad Geeta",
    locale="en",
    category_document_id="category-document-id",
):
    return {
        "id": 1,
        "documentId": document_id,
        "code": code,
        "legacy_code": None,
        "is_active": True,
        "sort_order": sort_order,
        "category": {"documentId": category_document_id},
        "from_date": "2006-01-20",
        "to_date": "2006-06-23",
        "prabodhan_count": 21,
        "name": name,
        "description": description,
        "locale": locale,
    }


class FakeSubjectClient:
    def __init__(self, categories_by_locale=None, subjects_by_locale=None, paginate=False):
        self.categories_by_locale = categories_by_locale or {}
        self.subjects_by_locale = subjects_by_locale or {}
        self.paginate = paginate
        self.create_calls = []
        self.localization_calls = []
        self.update_calls = []
        self.publish_calls = []

    def get_collection(
        self,
        plural_api_id,
        filters=None,
        locale=None,
        status=None,
        page_size=100,
        page=None,
        populate=None,
    ):
        if plural_api_id == "categories":
            records = self.categories_by_locale.get(locale, ())
        elif plural_api_id == "subjects":
            records = self.subjects_by_locale.get(locale, ())
        else:
            records = ()
        if filters:
            for field, value in filters.items():
                records = tuple(record for record in records if record.get(field) == value)
        if not self.paginate:
            return {"data": list(records)}

        page = page or 1
        start = (page - 1) * page_size
        end = start + page_size
        page_records = records[start:end]
        page_count = (len(records) + page_size - 1) // page_size
        return {
            "data": list(page_records),
            "meta": {
                "pagination": {
                    "page": page,
                    "pageSize": page_size,
                    "pageCount": page_count,
                    "total": len(records),
                }
            },
        }

    def create_document(self, plural_api_id, data, locale=None, publish=False):
        self.create_calls.append((plural_api_id, data, locale, publish))
        return {
            "data": {
                **data,
                "documentId": "created-subject-document-id",
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


class SubjectIngestionTest(unittest.TestCase):
    def setUp(self):
        self.config = load_strapi_config(
            base_url="http://localhost:1337",
            api_token="token",
            environ={},
        )

    def category_client(self, subjects_by_locale=None, categories_by_locale=None):
        return FakeSubjectClient(
            categories_by_locale
            or {
                "en": (strapi_category(),),
                "hi-IN": (strapi_category(locale="hi-IN"),),
            },
            subjects_by_locale,
        )

    def test_builds_subject_payloads_from_artifact_fields_and_category_document_id(self):
        default_payload, localized_payload = build_subject_payloads(
            subject_record(),
            "category-document-id",
        )

        self.assertEqual(
            {
                "code": "SUB001",
                "legacy_code": None,
                "is_active": True,
                "sort_order": 1,
                "category": "category-document-id",
                "from_date": "2006-01-20",
                "to_date": "2006-06-23",
                "prabodhan_count": 21,
                "name": "Shrimad Bhagvad Geeta",
                "description": "Shrimad Bhagvad Geeta",
            },
            default_payload,
        )
        self.assertEqual("श्रीमद् भगवद्गीता", localized_payload["name"])

    def test_dry_run_classifies_missing_subject_as_create(self):
        plan = plan_subject_ingestion(
            self.category_client(),
            self.config,
            subject_artifact(subject_record()),
        )

        self.assertEqual(1, plan.to_create)
        self.assertEqual(0, plan.to_update)
        self.assertEqual(2, plan.publish_actions)

    def test_blocks_subject_when_category_is_missing(self):
        plan = plan_subject_ingestion(
            FakeSubjectClient(),
            self.config,
            subject_artifact(subject_record(category_code="CAT999")),
        )

        self.assertEqual(1, plan.blocked_records)
        self.assertIn("Referenced Category code CAT999 was not found", plan.messages[0])
        self.assertFalse(plan.can_apply)

    def test_blocks_subject_when_category_is_ambiguous(self):
        client = self.category_client(
            categories_by_locale={
                "en": (
                    strapi_category(document_id="category-one"),
                    strapi_category(document_id="category-two"),
                )
            }
        )

        plan = plan_subject_ingestion(client, self.config, subject_artifact(subject_record()))

        self.assertEqual(1, plan.blocked_records)
        self.assertIn("Referenced Category code CAT001 is ambiguous", plan.messages[0])

    def test_dry_run_classifies_changed_relation_as_update(self):
        client = self.category_client(
            {
                "en": (strapi_subject(category_document_id="old-category-document-id"),),
                "hi-IN": (
                    strapi_subject(
                        name="श्रीमद् भगवद्गीता",
                        description="श्रीमद् भगवद्गीता",
                        locale="hi-IN",
                    ),
                ),
            }
        )

        plan = plan_subject_ingestion(client, self.config, subject_artifact(subject_record()))

        self.assertEqual(1, plan.to_update)
        self.assertTrue(plan.items[0].update_default)

    def test_dry_run_classifies_matching_subject(self):
        client = self.category_client(
            {
                "en": (strapi_subject(),),
                "hi-IN": (
                    strapi_subject(
                        name="श्रीमद् भगवद्गीता",
                        description="श्रीमद् भगवद्गीता",
                        locale="hi-IN",
                    ),
                ),
            }
        )

        plan = plan_subject_ingestion(client, self.config, subject_artifact(subject_record()))

        self.assertEqual(1, plan.already_matching)
        self.assertEqual(0, plan.publish_actions)

    def test_dry_run_reads_existing_subjects_across_pages(self):
        records = [subject_record(code=f"SUB{number:03d}", sort_order=number) for number in range(1, 102)]
        default_subjects = tuple(
            strapi_subject(
                code=record["subject_code"],
                document_id=f"subject-document-id-{record['subject_code']}",
                sort_order=record["sort_order"],
            )
            for record in records
        )
        localized_subjects = tuple(
            strapi_subject(
                code=record["subject_code"],
                document_id=f"subject-document-id-{record['subject_code']}",
                sort_order=record["sort_order"],
                name=record["name_hi_IN"],
                description=record["description_hi_IN"],
                locale="hi-IN",
            )
            for record in records
        )
        client = FakeSubjectClient(
            categories_by_locale={
                "en": (strapi_category(),),
                "hi-IN": (strapi_category(locale="hi-IN"),),
            },
            subjects_by_locale={
                "en": default_subjects,
                "hi-IN": localized_subjects,
            },
            paginate=True,
        )

        plan = plan_subject_ingestion(client, self.config, subject_artifact(*records))

        self.assertEqual(101, plan.already_matching)
        self.assertEqual(0, plan.to_create)

    def test_reports_duplicate_existing_code_conflict(self):
        client = self.category_client(
            {
                "en": (
                    strapi_subject(document_id="one"),
                    strapi_subject(document_id="two"),
                )
            }
        )

        plan = plan_subject_ingestion(client, self.config, subject_artifact(subject_record()))

        self.assertEqual(1, plan.conflicts)
        self.assertIn("Duplicate existing Subject records", plan.messages[0])

    def test_apply_publishes_create_even_when_artifact_desired_status_is_draft(self):
        client = self.category_client()
        plan = plan_subject_ingestion(
            client,
            self.config,
            subject_artifact(subject_record(desired_status="draft")),
        )

        apply_subject_ingestion(client, self.config, IngestionMode(apply=True), plan)

        self.assertEqual(1, len(client.create_calls))
        self.assertEqual(1, len(client.localization_calls))
        self.assertTrue(client.create_calls[0][3])
        self.assertTrue(client.localization_calls[0][4])

    def test_dry_run_mode_cannot_apply(self):
        client = self.category_client()
        plan = plan_subject_ingestion(
            client,
            self.config,
            subject_artifact(subject_record()),
        )

        with self.assertRaisesRegex(RuntimeError, "Dry-run mode cannot perform"):
            apply_subject_ingestion(client, self.config, IngestionMode(), plan)


if __name__ == "__main__":
    unittest.main()
