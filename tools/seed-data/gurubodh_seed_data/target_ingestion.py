import json
from dataclasses import dataclass

from gurubodh_seed_data.category_ingestion import plan_category_ingestion
from gurubodh_seed_data.category import get_category_source
from gurubodh_seed_data.category_artifacts import validate_category_artifact
from gurubodh_seed_data.glossary import get_glossary_source
from gurubodh_seed_data.glossary_artifacts import validate_glossary_artifact
from gurubodh_seed_data.glossary_ingestion import (
    LoadedGlossaryArtifact,
    plan_glossary_ingestion,
)
from gurubodh_seed_data.paths import category_paths, glossary_paths, subject_paths
from gurubodh_seed_data.strapi_client import StrapiClientError
from gurubodh_seed_data.strapi_preflight import PreflightCheck, PreflightResult
from gurubodh_seed_data.subject import get_subject_source
from gurubodh_seed_data.subject_artifacts import validate_subject_artifact
from gurubodh_seed_data.subject_ingestion import plan_subject_ingestion


@dataclass(frozen=True)
class IngestTarget:
    key: str
    workflow: str
    source_key: str
    collection_type: str
    plural_api_id: str
    display_name: str
    get_source: object
    get_paths: object
    validate_artifact: object


@dataclass(frozen=True)
class LoadedTargetArtifact:
    target_key: str
    workflow: str
    source_key: str
    path: str
    record_count: int
    collection_type: str
    plural_api_id: str
    display_name: str
    artifact: dict


@dataclass(frozen=True)
class TargetArtifactLoadResult:
    target: IngestTarget
    artifact: LoadedTargetArtifact | None
    errors: tuple[str, ...]

    @property
    def is_valid(self):
        return not self.errors

    @property
    def total_records(self):
        return self.artifact.record_count if self.artifact else 0


@dataclass(frozen=True)
class TargetIngestionPlan:
    target: IngestTarget
    plan: object | None = None
    errors: tuple[str, ...] = ()

    @property
    def is_valid(self):
        return not self.errors

    @property
    def to_create(self):
        return self.plan.to_create if self.plan else 0

    @property
    def to_update(self):
        return self.plan.to_update if self.plan else 0

    @property
    def already_matching(self):
        return self.plan.already_matching if self.plan else 0

    @property
    def conflicts(self):
        return self.plan.conflicts if self.plan else 0

    @property
    def blocked_records(self):
        return getattr(self.plan, "blocked_records", 0) if self.plan else 0

    @property
    def publish_actions(self):
        return self.plan.publish_actions if self.plan else 0

    @property
    def messages(self):
        return self.plan.messages if self.plan else ()

    @property
    def can_apply(self):
        return bool(self.plan and self.plan.can_apply)


INGEST_TARGET_REGISTRY = {
    "category": IngestTarget(
        key="category",
        workflow="category",
        source_key="categories",
        collection_type="category",
        plural_api_id="categories",
        display_name="Categories",
        get_source=get_category_source,
        get_paths=category_paths,
        validate_artifact=validate_category_artifact,
    ),
    "subject": IngestTarget(
        key="subject",
        workflow="subject",
        source_key="subjects",
        collection_type="subject",
        plural_api_id="subjects",
        display_name="Subjects",
        get_source=get_subject_source,
        get_paths=subject_paths,
        validate_artifact=validate_subject_artifact,
    ),
    "sanatan-glossary": IngestTarget(
        key="sanatan-glossary",
        workflow="glossary",
        source_key="sanatan-glossary",
        collection_type="sanatan-glossary",
        plural_api_id="sanatan-glossaries",
        display_name="Sanatan Glossary",
        get_source=get_glossary_source,
        get_paths=glossary_paths,
        validate_artifact=validate_glossary_artifact,
    ),
    "prabodhan-glossary": IngestTarget(
        key="prabodhan-glossary",
        workflow="glossary",
        source_key="prabodhan-glossary",
        collection_type="prabodhan-glossary",
        plural_api_id="prabodhan-glossaries",
        display_name="Prabodhan Glossary",
        get_source=get_glossary_source,
        get_paths=glossary_paths,
        validate_artifact=validate_glossary_artifact,
    ),
}


def get_ingest_target(target_key):
    try:
        return INGEST_TARGET_REGISTRY[target_key]
    except KeyError as error:
        accepted_values = ", ".join(INGEST_TARGET_REGISTRY)
        raise ValueError(
            f"Unsupported ingest target: {target_key}\n"
            f"Accepted values: {accepted_values}"
        ) from error


def load_target_artifact(target_key):
    target = get_ingest_target(target_key)
    source = target.get_source(target.source_key)
    path = target.get_paths(source).json_output
    errors = []

    try:
        with path.open(encoding="utf-8") as artifact_file:
            artifact = json.load(artifact_file)
    except FileNotFoundError:
        return TargetArtifactLoadResult(
            target=target,
            artifact=None,
            errors=(f"{target.key} artifact not found: {path}",),
        )
    except json.JSONDecodeError as error:
        return TargetArtifactLoadResult(
            target=target,
            artifact=None,
            errors=(f"{target.key} artifact is not valid JSON: {path}: {error}",),
        )

    validation_result = target.validate_artifact(artifact)
    if not validation_result.is_valid:
        errors.extend(
            f"{target.key} artifact validation failed: {message}"
            for message in validation_result.errors
        )

    errors.extend(_validate_target_identity(artifact, target))
    if errors:
        return TargetArtifactLoadResult(
            target=target,
            artifact=None,
            errors=tuple(errors),
        )

    records = artifact.get("records", ())
    return TargetArtifactLoadResult(
        target=target,
        artifact=LoadedTargetArtifact(
            target_key=target.key,
            workflow=target.workflow,
            source_key=target.source_key,
            path=str(path),
            record_count=len(records),
            collection_type=target.collection_type,
            plural_api_id=target.plural_api_id,
            display_name=target.display_name,
            artifact=artifact,
        ),
        errors=(),
    )


def run_target_preflight(client, config, target_key):
    target = get_ingest_target(target_key)
    checks = []

    if target.key == "category":
        checks.append(_check_collection_access(client, "categories"))
        checks.extend(_check_locales(client, config))
        checks.append(_check_draft_publish(client, "categories"))
    elif target.key == "subject":
        checks.append(_check_collection_access(client, "subjects"))
        checks.append(_check_collection_access(client, "categories"))
        checks.extend(_check_locales(client, config))
        checks.append(_check_draft_publish(client, "subjects"))
    else:
        checks.append(_check_collection_access(client, target.plural_api_id))
        checks.append(_check_draft_publish(client, target.plural_api_id))

    return PreflightResult(checks=tuple(checks))


def plan_target_ingestion(client, config, artifact_result):
    if not artifact_result.is_valid:
        return TargetIngestionPlan(
            target=artifact_result.target,
            errors=artifact_result.errors,
        )

    target = artifact_result.target
    artifact = artifact_result.artifact.artifact

    if target.key == "category":
        plan = plan_category_ingestion(client, config, artifact)
    elif target.key == "subject":
        plan = plan_subject_ingestion(client, config, artifact)
    elif target.workflow == "glossary":
        loaded_artifact = _as_glossary_artifact(artifact_result.artifact)
        plan = plan_glossary_ingestion(client, (loaded_artifact,))
    else:
        return TargetIngestionPlan(
            target=target,
            errors=(f"Unsupported target plan route: {target.key}",),
        )

    return TargetIngestionPlan(target=target, plan=plan)


def _as_glossary_artifact(artifact):
    return LoadedGlossaryArtifact(
        source_key=artifact.source_key,
        path=artifact.path,
        record_count=artifact.record_count,
        collection_type=artifact.collection_type,
        plural_api_id=artifact.plural_api_id,
        display_name=artifact.display_name,
        artifact=artifact.artifact,
    )


def _validate_target_identity(artifact, target):
    if not isinstance(artifact, dict):
        return ()

    errors = []
    workflow = artifact.get("workflow")
    source_key = artifact.get("source", {}).get("key")
    collection_type = artifact.get("strapi", {}).get("collection_type")

    if workflow != target.workflow:
        errors.append(
            f"{target.key} artifact workflow must be {target.workflow}: {workflow}"
        )
    if source_key != target.source_key:
        errors.append(
            f"{target.key} artifact source key must be {target.source_key}: {source_key}"
        )
    if collection_type != target.collection_type:
        errors.append(
            f"{target.key} artifact collection_type must be {target.collection_type}: {collection_type}"
        )

    return tuple(errors)


def _check_collection_access(client, plural_api_id):
    try:
        client.get_collection(plural_api_id, page_size=1)
    except StrapiClientError as error:
        return PreflightCheck(
            name=f"{plural_api_id} access",
            passed=False,
            message=f"Cannot read {plural_api_id}: {error}",
        )
    return PreflightCheck(
        name=f"{plural_api_id} access",
        passed=True,
        message=f"{plural_api_id} endpoint is reachable.",
    )


def _check_locales(client, config):
    try:
        locales = client.get_locales()
    except StrapiClientError as error:
        return (
            PreflightCheck(
                name="locale access",
                passed=False,
                message=f"Cannot read Strapi locales: {error}",
            ),
        )

    locale_records = locales if isinstance(locales, list) else locales.get("data", ())
    by_code = {
        record.get("code"): record
        for record in locale_records
        if isinstance(record, dict)
    }
    return (
        PreflightCheck(
            name="default locale",
            passed=bool(
                by_code.get(config.default_locale)
                and by_code[config.default_locale].get("isDefault")
            ),
            message=(
                f"Default locale is {config.default_locale}."
                if (
                    by_code.get(config.default_locale)
                    and by_code[config.default_locale].get("isDefault")
                )
                else f"Default locale must be {config.default_locale} for English fields."
            ),
        ),
        PreflightCheck(
            name="localized locale",
            passed=config.localized_locale in by_code,
            message=(
                f"Localized locale {config.localized_locale} is available."
                if config.localized_locale in by_code
                else f"Localized locale is missing: {config.localized_locale}."
            ),
        ),
    )


def _check_draft_publish(client, plural_api_id):
    try:
        client.get_collection(plural_api_id, status="draft", page_size=1)
    except StrapiClientError as error:
        return PreflightCheck(
            name=f"{plural_api_id} draft access",
            passed=False,
            message=f"Cannot query {plural_api_id} drafts: {error}",
        )
    return PreflightCheck(
        name=f"{plural_api_id} draft access",
        passed=True,
        message=f"{plural_api_id} supports Draft & Publish status queries.",
    )
