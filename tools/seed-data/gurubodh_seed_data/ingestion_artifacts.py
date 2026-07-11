import json
from dataclasses import dataclass

from gurubodh_seed_data.category import get_category_source
from gurubodh_seed_data.category_artifacts import validate_category_artifact
from gurubodh_seed_data.paths import category_paths, subject_paths
from gurubodh_seed_data.subject import get_subject_source
from gurubodh_seed_data.subject_artifacts import validate_subject_artifact


@dataclass(frozen=True)
class LoadedArtifact:
    workflow: str
    path: str
    record_count: int
    artifact: dict


@dataclass(frozen=True)
class ArtifactLoadResult:
    artifacts: tuple[LoadedArtifact, ...]
    errors: tuple[str, ...]

    @property
    def is_valid(self):
        return not self.errors

    @property
    def total_records(self):
        return sum(artifact.record_count for artifact in self.artifacts)


def load_ingestion_artifacts():
    loaders = (
        ("category", category_paths(get_category_source("categories")).json_output, validate_category_artifact),
        ("subject", subject_paths(get_subject_source("subjects")).json_output, validate_subject_artifact),
    )
    artifacts = []
    errors = []

    for workflow, path, validator in loaders:
        try:
            with path.open(encoding="utf-8") as artifact_file:
                artifact = json.load(artifact_file)
        except FileNotFoundError:
            errors.append(f"{workflow} artifact not found: {path}")
            continue
        except json.JSONDecodeError as error:
            errors.append(f"{workflow} artifact is not valid JSON: {path}: {error}")
            continue

        validation_result = validator(artifact)
        if not validation_result.is_valid:
            errors.extend(
                f"{workflow} artifact validation failed: {message}"
                for message in validation_result.errors
            )
            continue

        records = artifact.get("records", ())
        artifacts.append(
            LoadedArtifact(
                workflow=workflow,
                path=str(path),
                record_count=len(records),
                artifact=artifact,
            )
        )

    return ArtifactLoadResult(
        artifacts=tuple(artifacts),
        errors=tuple(errors),
    )
