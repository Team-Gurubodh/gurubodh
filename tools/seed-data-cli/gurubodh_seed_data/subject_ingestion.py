from __future__ import annotations

from dataclasses import dataclass


CATEGORY_PLURAL_API_ID = "categories"
SUBJECT_PLURAL_API_ID = "subjects"
DEFAULT_REQUIRED_FIELDS = (
    "subject_code",
    "is_active",
    "sort_order",
    "category_code",
    "name_en",
)
LOCALIZED_REQUIRED_FIELDS = (
    "subject_code",
    "is_active",
    "sort_order",
    "category_code",
    "name_hi_IN",
)


@dataclass(frozen=True)
class SubjectPlanItem:
    code: str
    action: str
    document_id: str | None = None
    default_payload: dict | None = None
    localized_payload: dict | None = None
    update_default: bool = False
    update_localized: bool = False
    create_localized: bool = False
    messages: tuple[str, ...] = ()

    @property
    def is_blocked(self):
        return self.action == "blocked"

    @property
    def is_conflict(self):
        return self.action == "conflict"

    @property
    def is_create(self):
        return self.action == "create"

    @property
    def is_update(self):
        return self.action == "update"

    @property
    def is_matching(self):
        return self.action == "matching"

    @property
    def publish_actions(self):
        if self.is_blocked or self.is_conflict or self.is_matching:
            return 0
        actions = 1
        if self.create_localized or self.update_localized:
            actions += 1
        return actions


@dataclass(frozen=True)
class SubjectIngestionPlan:
    items: tuple[SubjectPlanItem, ...]

    @property
    def to_create(self):
        return sum(1 for item in self.items if item.is_create)

    @property
    def to_update(self):
        return sum(1 for item in self.items if item.is_update)

    @property
    def already_matching(self):
        return sum(1 for item in self.items if item.is_matching)

    @property
    def conflicts(self):
        return sum(1 for item in self.items if item.is_conflict)

    @property
    def blocked_records(self):
        return sum(1 for item in self.items if item.is_blocked)

    @property
    def publish_actions(self):
        return sum(item.publish_actions for item in self.items)

    @property
    def can_apply(self):
        return self.conflicts == 0 and self.blocked_records == 0

    @property
    def messages(self):
        messages = []
        for item in self.items:
            for message in item.messages:
                messages.append(f"{item.code}: {message}")
        return tuple(messages)


def build_subject_payloads(record, category_document_id):
    shared = {
        "code": record.get("subject_code"),
        "legacy_code": record.get("legacy_code"),
        "is_active": record.get("is_active"),
        "sort_order": record.get("sort_order"),
        "category": category_document_id,
        "from_date": record.get("from_date"),
        "to_date": record.get("to_date"),
        "prabodhan_count": record.get("prabodhan_count"),
    }
    return (
        {
            **shared,
            "name": record.get("name_en"),
            "description": record.get("description_en"),
        },
        {
            **shared,
            "name": record.get("name_hi_IN"),
            "description": record.get("description_hi_IN"),
        },
    )


def plan_subject_ingestion(client, config, subject_artifact):
    records = subject_artifact.get("records", ())
    category_lookup = _build_category_lookup(
        client,
        (config.default_locale, config.localized_locale),
    )
    existing_default = _fetch_existing_subjects_by_code(
        client,
        config.default_locale,
    )
    existing_localized = _fetch_existing_subjects_by_code(
        client,
        config.localized_locale,
    )
    existing_sort_orders = _fetch_existing_subject_sort_orders(
        client,
        (config.default_locale, config.localized_locale),
    )

    planned_codes = set()
    planned_sort_orders = {}
    items = []

    for record in records:
        code = record.get("subject_code") or "<missing-code>"
        category_code = record.get("category_code")
        blocking_messages = []
        conflict_messages = list(_validate_required_values(record))

        category_document_ids = category_lookup.get(category_code, ())
        if not category_document_ids:
            blocking_messages.append(
                f"Referenced Category code {category_code or '<missing-category-code>'} was not found."
            )
            category_document_id = None
        elif len(category_document_ids) > 1:
            blocking_messages.append(
                f"Referenced Category code {category_code} is ambiguous across documentIds: {', '.join(category_document_ids)}."
            )
            category_document_id = None
        else:
            category_document_id = category_document_ids[0]

        default_payload, localized_payload = build_subject_payloads(
            record,
            category_document_id,
        )

        if code in planned_codes:
            conflict_messages.append(f"Duplicate artifact subject_code: {code}.")
        planned_codes.add(code)

        sort_order = record.get("sort_order")
        if sort_order in planned_sort_orders and sort_order is not None:
            conflict_messages.append(
                f"Duplicate artifact sort_order {sort_order} also used by {planned_sort_orders[sort_order]}."
            )
        else:
            planned_sort_orders[sort_order] = code

        default_matches = existing_default.get(code, ())
        localized_matches = existing_localized.get(code, ())
        conflict_messages.extend(
            _duplicate_conflicts("default locale", code, default_matches)
        )
        conflict_messages.extend(
            _duplicate_conflicts("localized locale", code, localized_matches)
        )

        default_record = default_matches[0] if len(default_matches) == 1 else None
        localized_record = localized_matches[0] if len(localized_matches) == 1 else None
        document_source_record = default_record or localized_record
        document_id = _record_value(document_source_record, "documentId")

        if document_source_record is not None and not document_id:
            conflict_messages.append("Existing Subject is missing documentId.")

        sort_order_matches = existing_sort_orders.get(sort_order, ())
        conflicting_sort_orders = tuple(
            existing
            for existing in sort_order_matches
            if _record_value(existing, "code") != code
        )
        if conflicting_sort_orders:
            conflicting_codes = ", ".join(
                _record_value(existing, "code") or "<missing-code>"
                for existing in conflicting_sort_orders
            )
            conflict_messages.append(
                f"sort_order {sort_order} is already used by existing Subject code(s): {conflicting_codes}."
            )

        if blocking_messages:
            items.append(
                SubjectPlanItem(
                    code=code,
                    action="blocked",
                    default_payload=default_payload,
                    localized_payload=localized_payload,
                    messages=tuple(blocking_messages),
                )
            )
            continue

        if conflict_messages:
            items.append(
                SubjectPlanItem(
                    code=code,
                    action="conflict",
                    default_payload=default_payload,
                    localized_payload=localized_payload,
                    messages=tuple(conflict_messages),
                )
            )
            continue

        if default_record is None and localized_record is None:
            items.append(
                SubjectPlanItem(
                    code=code,
                    action="create",
                    default_payload=default_payload,
                    localized_payload=localized_payload,
                    create_localized=True,
                )
            )
            continue

        update_default = (
            True
            if default_record is None
            else _payload_differs(default_payload, default_record)
        )
        update_localized = (
            True
            if localized_record is None
            else _payload_differs(localized_payload, localized_record)
        )
        if update_default or update_localized:
            items.append(
                SubjectPlanItem(
                    code=code,
                    action="update",
                    document_id=document_id,
                    default_payload=default_payload,
                    localized_payload=localized_payload,
                    update_default=update_default,
                    update_localized=localized_record is not None and update_localized,
                    create_localized=localized_record is None,
                )
            )
            continue

        items.append(
            SubjectPlanItem(
                code=code,
                action="matching",
                document_id=document_id,
                default_payload=default_payload,
                localized_payload=localized_payload,
            )
        )

    return SubjectIngestionPlan(items=tuple(items))


def apply_subject_ingestion(client, config, mode, plan):
    mode.require_write_allowed()
    if not plan.can_apply:
        raise RuntimeError(
            "Subject ingestion plan has blocked records or conflicts and cannot be applied."
        )

    for item in plan.items:
        if item.is_matching:
            continue
        if item.is_create:
            default_response = client.create_document(
                SUBJECT_PLURAL_API_ID,
                item.default_payload,
                locale=config.default_locale,
                publish=True,
            )
            document_id = _response_document_id(default_response)
            client.create_localization(
                SUBJECT_PLURAL_API_ID,
                document_id,
                item.localized_payload,
                locale=config.localized_locale,
                publish=True,
            )
            continue
        if item.is_update:
            if item.update_default:
                client.update_document(
                    SUBJECT_PLURAL_API_ID,
                    item.document_id,
                    item.default_payload,
                    locale=config.default_locale,
                    publish=True,
                )
            else:
                client.publish_document(
                    SUBJECT_PLURAL_API_ID,
                    item.document_id,
                    locale=config.default_locale,
                )
            if item.create_localized:
                client.create_localization(
                    SUBJECT_PLURAL_API_ID,
                    item.document_id,
                    item.localized_payload,
                    locale=config.localized_locale,
                    publish=True,
                )
            elif item.update_localized:
                client.update_document(
                    SUBJECT_PLURAL_API_ID,
                    item.document_id,
                    item.localized_payload,
                    locale=config.localized_locale,
                    publish=True,
                )


def _build_category_lookup(client, locales):
    by_code = {}
    for locale in locales:
        for record in _fetch_existing_records(
            client,
            CATEGORY_PLURAL_API_ID,
            locale,
            populate=None,
        ):
            code = _record_value(record, "code")
            document_id = _record_value(record, "documentId")
            if not code:
                continue
            by_code.setdefault(code, set()).add(document_id)

    return {
        code: tuple(sorted(document_id for document_id in document_ids if document_id))
        for code, document_ids in by_code.items()
    }


def _fetch_existing_subjects_by_code(client, locale):
    by_code = {}
    for record in _fetch_existing_records(
        client,
        SUBJECT_PLURAL_API_ID,
        locale,
        populate="category",
    ):
        code = _record_value(record, "code")
        by_code.setdefault(code, []).append(record)
    return {code: tuple(records) for code, records in by_code.items()}


def _fetch_existing_subject_sort_orders(client, locales):
    by_sort_order = {}
    for locale in locales:
        for record in _fetch_existing_records(
            client,
            SUBJECT_PLURAL_API_ID,
            locale,
            populate="category",
        ):
            sort_order = _record_value(record, "sort_order")
            by_sort_order.setdefault(sort_order, []).append(record)
    return {sort_order: tuple(records) for sort_order, records in by_sort_order.items()}


def _fetch_existing_records(client, plural_api_id, locale, populate=None):
    records = {}
    for status in ("draft", "published", None):
        for record in _fetch_collection_records(
            client,
            plural_api_id,
            locale,
            status,
            populate=populate,
        ):
            key = (
                _record_value(record, "documentId"),
                _record_value(record, "locale"),
                _record_value(record, "code"),
                _record_value(record, "sort_order"),
                _relation_document_id(record, "category"),
            )
            records[key] = record
    return tuple(records.values())


def _fetch_collection_records(client, plural_api_id, locale, status, populate=None):
    page = 1
    page_count = 1
    while page <= page_count:
        kwargs = {
            "locale": locale,
            "page_size": 100,
            "page": page,
        }
        if status:
            kwargs["status"] = status
        if populate:
            kwargs["populate"] = populate
        response = client.get_collection(plural_api_id, **kwargs)
        yield from _response_data(response)
        page_count = _response_page_count(response)
        page += 1


def _response_data(response):
    if isinstance(response, dict):
        data = response.get("data", ())
        return data if isinstance(data, list) else ()
    return ()


def _response_page_count(response):
    if not isinstance(response, dict):
        return 1
    meta = response.get("meta")
    if not isinstance(meta, dict):
        return 1
    pagination = meta.get("pagination")
    if not isinstance(pagination, dict):
        return 1
    return pagination.get("pageCount") or 1


def _response_document_id(response):
    data = response.get("data") if isinstance(response, dict) else None
    document_id = _record_value(data, "documentId")
    if not document_id:
        raise RuntimeError("Strapi create response did not include documentId.")
    return document_id


def _record_value(record, field):
    if not isinstance(record, dict):
        return None
    if field in record:
        return record.get(field)
    attributes = record.get("attributes")
    if isinstance(attributes, dict):
        return attributes.get(field)
    return None


def _relation_document_id(record, field):
    relation = _record_value(record, field)
    if isinstance(relation, str):
        return relation
    if isinstance(relation, dict):
        if relation.get("documentId"):
            return relation.get("documentId")
        data = relation.get("data")
        if isinstance(data, dict):
            return _record_value(data, "documentId")
    return None


def _validate_required_values(record):
    missing = []
    for field in DEFAULT_REQUIRED_FIELDS + LOCALIZED_REQUIRED_FIELDS:
        value = record.get(field)
        if value is None or value == "":
            missing.append(f"Missing required artifact value: {field}.")
    return tuple(missing)


def _duplicate_conflicts(scope, code, records):
    if len(records) <= 1:
        return ()
    return (f"Duplicate existing Subject records with code {code} in {scope}.",)


def _payload_differs(payload, existing_record):
    for field, value in payload.items():
        existing_value = (
            _relation_document_id(existing_record, field)
            if field == "category"
            else _record_value(existing_record, field)
        )
        if value != existing_value:
            return True
    return False
