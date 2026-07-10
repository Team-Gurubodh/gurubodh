import csv
import json
from dataclasses import dataclass
from pathlib import Path

from gurubodh_seed_data.category import get_category_source
from gurubodh_seed_data.json_schema import (
    ArtifactValidationResult,
    validate_json_schema_artifact,
)
from gurubodh_seed_data.paths import subject_paths
from gurubodh_seed_data.validation import (
    REQUIRED_SUBJECT_HEADERS,
    parse_boolean,
    parse_optional_integer,
    parse_optional_text,
    validate_subject_csv,
)


SUBJECT_ARTIFACT_SCHEMA_VERSION = 1
SUBJECT_WORKFLOW = "subject"
SUBJECT_ARTIFACT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "subject_artifact.schema.json"
)


@dataclass(frozen=True)
class SubjectArtifactGenerationResult:
    source_key: str
    csv_path: str
    json_path: str
    record_count: int
    csv_validation_result: object
    artifact_validation_result: ArtifactValidationResult


def _subject_record_from_csv_row(row):
    values = {
        column: row[column].strip()
        for column in REQUIRED_SUBJECT_HEADERS
    }
    return {
        "subject_code": values["code"],
        "legacy_code": parse_optional_text(values["legacy_code"]),
        "is_active": parse_boolean(values["is_active"]),
        "sort_order": int(values["sort_order"]),
        "category_code": values["category_code"],
        "desired_status": values["desired_status"],
        "name_en": values["name_en"],
        "description_en": values["description_en"],
        "name_hi_IN": values["name_hi-IN"],
        "description_hi_IN": values["description_hi-IN"],
        "from_date": parse_optional_text(values["from_date"]),
        "to_date": parse_optional_text(values["to_date"]),
        "prabodhan_count": parse_optional_integer(values["prabodhan_count"]),
    }


def build_subject_artifact(source):
    paths = subject_paths(source)
    records = []

    with paths.csv_input.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            records.append(_subject_record_from_csv_row(row))

    return {
        "schema_version": SUBJECT_ARTIFACT_SCHEMA_VERSION,
        "workflow": SUBJECT_WORKFLOW,
        "source": {
            "key": source.key,
            "label": source.label,
        },
        "strapi": {
            "collection_type": "subject",
            "display_name": source.label,
        },
        "records": records,
    }


def validate_subject_artifact(artifact):
    return validate_json_schema_artifact(artifact, SUBJECT_ARTIFACT_SCHEMA_PATH)


def write_subject_artifact(source):
    paths = subject_paths(source)
    category_source = get_category_source("categories")
    csv_validation_result = validate_subject_csv(source, category_source)
    if not csv_validation_result.is_valid:
        return SubjectArtifactGenerationResult(
            source_key=source.key,
            csv_path=str(paths.csv_input),
            json_path=str(paths.json_output),
            record_count=0,
            csv_validation_result=csv_validation_result,
            artifact_validation_result=ArtifactValidationResult(
                is_valid=False,
                errors=("CSV validation failed.",),
            ),
        )

    artifact = build_subject_artifact(source)
    artifact_validation_result = validate_subject_artifact(artifact)
    if not artifact_validation_result.is_valid:
        return SubjectArtifactGenerationResult(
            source_key=source.key,
            csv_path=str(paths.csv_input),
            json_path=str(paths.json_output),
            record_count=len(artifact.get("records", ())),
            csv_validation_result=csv_validation_result,
            artifact_validation_result=artifact_validation_result,
        )

    paths.json_output.parent.mkdir(parents=True, exist_ok=True)
    paths.json_output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return SubjectArtifactGenerationResult(
        source_key=source.key,
        csv_path=str(paths.csv_input),
        json_path=str(paths.json_output),
        record_count=len(artifact["records"]),
        csv_validation_result=csv_validation_result,
        artifact_validation_result=artifact_validation_result,
    )
