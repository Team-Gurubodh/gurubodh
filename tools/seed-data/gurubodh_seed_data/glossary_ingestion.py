import json
from dataclasses import dataclass

from gurubodh_seed_data.glossary import get_glossary_source
from gurubodh_seed_data.glossary_artifacts import validate_glossary_artifact
from gurubodh_seed_data.paths import glossary_paths
from gurubodh_seed_data.strapi_client import StrapiClientError


@dataclass(frozen=True)
class GlossaryTarget:
    source_key: str
    collection_type: str
    plural_api_id: str
    display_name: str


@dataclass(frozen=True)
class LoadedGlossaryArtifact:
    source_key: str
    path: str
    record_count: int
    collection_type: str
    plural_api_id: str
    display_name: str
    artifact: dict


@dataclass(frozen=True)
class GlossaryArtifactLoadResult:
    artifacts: tuple[LoadedGlossaryArtifact, ...]
    errors: tuple[str, ...]

    @property
    def is_valid(self):
        return not self.errors

    @property
    def total_records(self):
        return sum(artifact.record_count for artifact in self.artifacts)


@dataclass(frozen=True)
class GlossaryPreflightCheck:
    name: str
    passed: bool
    message: str


@dataclass(frozen=True)
class GlossaryPreflightResult:
    checks: tuple[GlossaryPreflightCheck, ...]

    @property
    def is_valid(self):
        return all(check.passed for check in self.checks)

    @property
    def errors(self):
        return tuple(check.message for check in self.checks if not check.passed)


@dataclass(frozen=True)
class GlossaryPlanItem:
    glossary: str
    code: str
    action: str
    plural_api_id: str
    document_id: str | None = None
    payload: dict | None = None
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
        return 1 if self.is_create or self.is_update else 0


@dataclass(frozen=True)
class GlossaryIngestionPlan:
    items: tuple[GlossaryPlanItem, ...]

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
                messages.append(f"{item.glossary} {item.code}: {message}")
        return tuple(messages)


APPROVED_GLOSSARY_TARGETS = {
    "sanatan-glossary": GlossaryTarget(
        source_key="sanatan-glossary",
        collection_type="sanatan-glossary",
        plural_api_id="sanatan-glossaries",
        display_name="Sanatan Glossary",
    ),
    "prabodhan-glossary": GlossaryTarget(
        source_key="prabodhan-glossary",
        collection_type="prabodhan-glossary",
        plural_api_id="prabodhan-glossaries",
        display_name="Prabodhan Glossary",
    ),
}


REQUIRED_ARTIFACT_FIELDS = ("term_code", "term", "definition")
REQUIRED_STRAPI_FIELDS = ("code", "term", "definition")


def load_glossary_ingestion_artifacts():
    artifacts = []
    errors = []

    for target in APPROVED_GLOSSARY_TARGETS.values():
        source = get_glossary_source(target.source_key)
        path = glossary_paths(source).json_output
        try:
            with path.open(encoding="utf-8") as artifact_file:
                artifact = json.load(artifact_file)
        except FileNotFoundError:
            errors.append(f"{target.source_key} artifact not found: {path}")
            continue
        except json.JSONDecodeError as error:
            errors.append(f"{target.source_key} artifact is not valid JSON: {path}: {error}")
            continue

        validation_result = validate_glossary_artifact(artifact)
        if not validation_result.is_valid:
            errors.extend(
                f"{target.source_key} artifact validation failed: {message}"
                for message in validation_result.errors
            )
            continue

        target_errors = _validate_approved_target(artifact, target)
        if target_errors:
            errors.extend(target_errors)
            continue

        records = artifact.get("records", ())
        artifacts.append(
            LoadedGlossaryArtifact(
                source_key=target.source_key,
                path=str(path),
                record_count=len(records),
                collection_type=target.collection_type,
                plural_api_id=target.plural_api_id,
                display_name=target.display_name,
                artifact=artifact,
            )
        )

    return GlossaryArtifactLoadResult(
        artifacts=tuple(artifacts),
        errors=tuple(errors),
    )


def run_glossary_preflight(client):
    checks = []
    for target in APPROVED_GLOSSARY_TARGETS.values():
        checks.append(_check_glossary_collection_access(client, target))
        checks.append(_check_glossary_draft_publish(client, target))
    return GlossaryPreflightResult(checks=tuple(checks))


def build_glossary_payload(record):
    return {
        "code": record.get("term_code"),
        "term": record.get("term"),
        "definition": record.get("definition"),
    }


def plan_glossary_ingestion(client, loaded_artifacts):
    items = []
    for loaded_artifact in loaded_artifacts:
        target = APPROVED_GLOSSARY_TARGETS.get(loaded_artifact.source_key)
        if target is None:
            items.append(
                GlossaryPlanItem(
                    glossary=loaded_artifact.display_name,
                    code="<unknown-target>",
                    action="blocked",
                    plural_api_id=loaded_artifact.plural_api_id,
                    messages=(
                        f"Unavailable glossary target for source {loaded_artifact.source_key}.",
                    ),
                )
            )
            continue
        items.extend(_plan_one_glossary(client, loaded_artifact, target).items)

    return GlossaryIngestionPlan(items=tuple(items))


def _validate_approved_target(artifact, target):
    errors = []
    source_key = artifact.get("source", {}).get("key")
    collection_type = artifact.get("strapi", {}).get("collection_type")
    if source_key != target.source_key:
        errors.append(
            f"{target.source_key} artifact source key must be {target.source_key}: {source_key}"
        )
    if collection_type != target.collection_type:
        errors.append(
            f"{target.source_key} artifact collection_type must be {target.collection_type}: {collection_type}"
        )
    return tuple(errors)


def _check_glossary_collection_access(client, target):
    try:
        client.get_collection(target.plural_api_id, page_size=1)
    except StrapiClientError as error:
        return GlossaryPreflightCheck(
            name=f"{target.plural_api_id} access",
            passed=False,
            message=f"Cannot read {target.plural_api_id}: {error}",
        )
    return GlossaryPreflightCheck(
        name=f"{target.plural_api_id} access",
        passed=True,
        message=f"{target.plural_api_id} endpoint is reachable.",
    )


def _check_glossary_draft_publish(client, target):
    try:
        client.get_collection(target.plural_api_id, status="draft", page_size=1)
    except StrapiClientError as error:
        return GlossaryPreflightCheck(
            name=f"{target.plural_api_id} draft access",
            passed=False,
            message=f"Cannot query {target.plural_api_id} drafts: {error}",
        )
    return GlossaryPreflightCheck(
        name=f"{target.plural_api_id} draft access",
        passed=True,
        message=f"{target.plural_api_id} supports Draft & Publish status queries.",
    )


def _plan_one_glossary(client, loaded_artifact, target):
    target_errors = _validate_approved_target(loaded_artifact.artifact, target)
    if target_errors:
        return GlossaryIngestionPlan(
            items=(
                GlossaryPlanItem(
                    glossary=target.display_name,
                    code="<target>",
                    action="blocked",
                    plural_api_id=target.plural_api_id,
                    messages=target_errors,
                ),
            )
        )

    existing_by_code = _fetch_existing_by_code(client, target)
    planned_codes = set()
    items = []

    for record in loaded_artifact.artifact.get("records", ()):
        code = record.get("term_code") or "<missing-code>"
        payload = build_glossary_payload(record)
        messages = list(_validate_required_values(record))

        if code in planned_codes:
            messages.append(f"Duplicate artifact term_code: {code}.")
        planned_codes.add(code)

        matches = existing_by_code.get(code, ())
        messages.extend(_duplicate_conflicts(target.display_name, code, matches))

        existing_record = matches[0] if len(matches) == 1 else None
        document_id = _record_value(existing_record, "documentId")
        if existing_record is not None:
            if not document_id:
                messages.append("Existing glossary record is missing documentId.")
            messages.extend(_missing_strapi_field_messages(existing_record))

        if messages:
            items.append(
                GlossaryPlanItem(
                    glossary=target.display_name,
                    code=code,
                    action="conflict",
                    plural_api_id=target.plural_api_id,
                    payload=payload,
                    messages=tuple(messages),
                )
            )
            continue

        if existing_record is None:
            items.append(
                GlossaryPlanItem(
                    glossary=target.display_name,
                    code=code,
                    action="create",
                    plural_api_id=target.plural_api_id,
                    payload=payload,
                )
            )
            continue

        if _payload_differs(payload, existing_record):
            items.append(
                GlossaryPlanItem(
                    glossary=target.display_name,
                    code=code,
                    action="update",
                    plural_api_id=target.plural_api_id,
                    document_id=document_id,
                    payload=payload,
                )
            )
            continue

        items.append(
            GlossaryPlanItem(
                glossary=target.display_name,
                code=code,
                action="matching",
                plural_api_id=target.plural_api_id,
                document_id=document_id,
                payload=payload,
            )
        )

    return GlossaryIngestionPlan(items=tuple(items))


def _fetch_existing_by_code(client, target):
    by_code = {}
    for record in _fetch_existing_records(client, target.plural_api_id):
        code = _record_value(record, "code")
        by_code.setdefault(code, []).append(record)
    return {code: tuple(records) for code, records in by_code.items()}


def _fetch_existing_records(client, plural_api_id):
    records = {}
    for status in ("draft", "published", None):
        for record in _fetch_collection_records(client, plural_api_id, status):
            key = (
                _record_value(record, "documentId"),
                _record_value(record, "id"),
                _record_value(record, "code"),
            )
            records[key] = record
    return tuple(records.values())


def _fetch_collection_records(client, plural_api_id, status):
    page = 1
    page_count = 1
    while page <= page_count:
        kwargs = {
            "page_size": 100,
            "page": page,
        }
        if status:
            kwargs["status"] = status
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
    messages = []
    for field in REQUIRED_ARTIFACT_FIELDS:
        value = record.get(field)
        if value is None or value == "":
            messages.append(f"Missing required artifact value: {field}.")
    return tuple(messages)


def _duplicate_conflicts(display_name, code, records):
    if len(records) <= 1:
        return ()
    return (f"Duplicate existing {display_name} records with code {code}.",)


def _missing_strapi_field_messages(record):
    messages = []
    for field in REQUIRED_STRAPI_FIELDS:
        value = _record_value(record, field)
        if value is None or value == "":
            messages.append(f"Existing glossary record is missing required Strapi field: {field}.")
    return tuple(messages)


def _payload_differs(payload, existing_record):
    return any(
        payload.get(field) != _record_value(existing_record, field)
        for field in payload
    )
