from __future__ import annotations

from dataclasses import dataclass


PLURAL_API_ID = "categories"
DEFAULT_REQUIRED_FIELDS = ("category_code", "is_active", "sort_order", "name_en")
LOCALIZED_REQUIRED_FIELDS = ("category_code", "is_active", "sort_order", "name_hi_IN")


@dataclass(frozen=True)
class CategoryPlanItem:
    code: str
    action: str
    document_id: str | None = None
    default_payload: dict | None = None
    localized_payload: dict | None = None
    update_default: bool = False
    update_localized: bool = False
    create_localized: bool = False
    conflict_messages: tuple[str, ...] = ()

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
    def needs_write(self):
        return self.is_create or self.is_update

    @property
    def publish_actions(self):
        if self.is_conflict or self.is_matching:
            return 0
        actions = 1
        if self.create_localized or self.update_localized:
            actions += 1
        return actions


@dataclass(frozen=True)
class CategoryIngestionPlan:
    items: tuple[CategoryPlanItem, ...]

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
    def publish_actions(self):
        return sum(item.publish_actions for item in self.items)

    @property
    def can_apply(self):
        return self.conflicts == 0

    @property
    def messages(self):
        messages = []
        for item in self.items:
            for conflict in item.conflict_messages:
                messages.append(f"{item.code}: {conflict}")
        return tuple(messages)


def build_category_payloads(record):
    shared = {
        "code": record.get("category_code"),
        "legacy_code": record.get("legacy_code"),
        "is_active": record.get("is_active"),
        "sort_order": record.get("sort_order"),
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


def plan_category_ingestion(client, config, category_artifact):
    records = category_artifact.get("records", ())
    existing_default = _fetch_existing_by_code(client, config.default_locale)
    existing_localized = _fetch_existing_by_code(client, config.localized_locale)
    existing_sort_orders = _fetch_existing_sort_orders(
        client,
        (config.default_locale, config.localized_locale),
    )

    planned_codes = set()
    planned_sort_orders = {}
    items = []

    for record in records:
        code = record.get("category_code") or "<missing-code>"
        default_payload, localized_payload = build_category_payloads(record)
        conflicts = list(_validate_required_values(record))

        if code in planned_codes:
            conflicts.append(f"Duplicate artifact category_code: {code}.")
        planned_codes.add(code)

        sort_order = record.get("sort_order")
        if sort_order in planned_sort_orders and sort_order is not None:
            conflicts.append(
                f"Duplicate artifact sort_order {sort_order} also used by {planned_sort_orders[sort_order]}."
            )
        else:
            planned_sort_orders[sort_order] = code

        default_matches = existing_default.get(code, ())
        localized_matches = existing_localized.get(code, ())
        conflicts.extend(_duplicate_conflicts("default locale", code, default_matches))
        conflicts.extend(_duplicate_conflicts("localized locale", code, localized_matches))

        default_record = default_matches[0] if len(default_matches) == 1 else None
        localized_record = localized_matches[0] if len(localized_matches) == 1 else None
        document_source_record = default_record or localized_record
        document_id = _record_value(document_source_record, "documentId")

        if document_source_record is not None and not document_id:
            conflicts.append("Existing Category is missing documentId.")

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
            conflicts.append(
                f"sort_order {sort_order} is already used by existing Category code(s): {conflicting_codes}."
            )

        if conflicts:
            items.append(
                CategoryPlanItem(
                    code=code,
                    action="conflict",
                    default_payload=default_payload,
                    localized_payload=localized_payload,
                    conflict_messages=tuple(conflicts),
                )
            )
            continue

        if default_record is None and localized_record is None:
            items.append(
                CategoryPlanItem(
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
                CategoryPlanItem(
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
            CategoryPlanItem(
                code=code,
                action="matching",
                document_id=document_id,
                default_payload=default_payload,
                localized_payload=localized_payload,
            )
        )

    return CategoryIngestionPlan(items=tuple(items))


def apply_category_ingestion(client, config, mode, plan):
    mode.require_write_allowed()
    if not plan.can_apply:
        raise RuntimeError("Category ingestion plan has conflicts and cannot be applied.")

    for item in plan.items:
        if item.is_matching:
            continue
        if item.is_create:
            default_response = client.create_document(
                PLURAL_API_ID,
                item.default_payload,
                locale=config.default_locale,
                publish=True,
            )
            document_id = _response_document_id(default_response)
            client.create_localization(
                PLURAL_API_ID,
                document_id,
                item.localized_payload,
                locale=config.localized_locale,
                publish=True,
            )
            continue
        if item.is_update:
            if item.update_default:
                client.update_document(
                    PLURAL_API_ID,
                    item.document_id,
                    item.default_payload,
                    locale=config.default_locale,
                    publish=True,
                )
            else:
                client.publish_document(
                    PLURAL_API_ID,
                    item.document_id,
                    locale=config.default_locale,
                )
            if item.create_localized:
                client.create_localization(
                    PLURAL_API_ID,
                    item.document_id,
                    item.localized_payload,
                    locale=config.localized_locale,
                    publish=True,
                )
            elif item.update_localized:
                client.update_document(
                    PLURAL_API_ID,
                    item.document_id,
                    item.localized_payload,
                    locale=config.localized_locale,
                    publish=True,
                )


def _fetch_existing_by_code(client, locale):
    by_code = {}
    for record in _fetch_existing_records(client, locale):
        code = _record_value(record, "code")
        by_code.setdefault(code, []).append(record)
    return {code: tuple(records) for code, records in by_code.items()}


def _fetch_existing_sort_orders(client, locales):
    by_sort_order = {}
    for locale in locales:
        for record in _fetch_existing_records(client, locale):
            sort_order = _record_value(record, "sort_order")
            by_sort_order.setdefault(sort_order, []).append(record)
    return {sort_order: tuple(records) for sort_order, records in by_sort_order.items()}


def _fetch_existing_records(client, locale):
    records = {}
    for status in ("draft", "published", None):
        for record in _fetch_collection_records(client, locale, status):
            key = (
                _record_value(record, "documentId"),
                _record_value(record, "locale"),
                _record_value(record, "code"),
                _record_value(record, "sort_order"),
            )
            records[key] = record
    return tuple(records.values())


def _fetch_collection_records(client, locale, status):
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
        response = client.get_collection(PLURAL_API_ID, **kwargs)
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
    return (f"Duplicate existing Category records with code {code} in {scope}.",)


def _payload_differs(payload, existing_record):
    return any(payload.get(field) != _record_value(existing_record, field) for field in payload)
