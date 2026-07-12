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
