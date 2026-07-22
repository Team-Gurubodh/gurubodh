import csv
import json
from dataclasses import dataclass
from pathlib import Path

from gurubodh_seed_data.json_schema import (
    ArtifactValidationResult,
    validate_json_schema_artifact,
)
from gurubodh_seed_data.paths import glossary_paths
from gurubodh_seed_data.validation import (
    REQUIRED_GLOSSARY_HEADERS,
    validate_glossary_csv,
)


GLOSSARY_ARTIFACT_SCHEMA_VERSION = 1
GLOSSARY_WORKFLOW = "glossary"
GLOSSARY_ARTIFACT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "glossary_artifact.schema.json"
)


@dataclass(frozen=True)
class GlossaryArtifactGenerationResult:
    source_key: str
    csv_path: str
    json_path: str
    record_count: int
    csv_validation_result: object
    artifact_validation_result: ArtifactValidationResult


def _glossary_record_from_csv_row(row):
    values = {
        column: row[column].strip()
        for column in REQUIRED_GLOSSARY_HEADERS
    }
    return {
        "term_code": values["Term Code"],
        "term": values["Term"],
        "definition": values["Definition"],
    }


def build_glossary_artifact(source):
    paths = glossary_paths(source)
    records = []

    with paths.csv_input.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            records.append(_glossary_record_from_csv_row(row))

    return {
        "schema_version": GLOSSARY_ARTIFACT_SCHEMA_VERSION,
        "workflow": GLOSSARY_WORKFLOW,
        "source": {
            "key": source.key,
            "label": source.label,
        },
        "strapi": {
            "collection_type": source.key,
            "display_name": source.label,
        },
        "records": records,
    }


def validate_glossary_artifact(artifact):
    return validate_json_schema_artifact(artifact, GLOSSARY_ARTIFACT_SCHEMA_PATH)


def write_glossary_artifact(source):
    paths = glossary_paths(source)
    csv_validation_result = validate_glossary_csv(source)
    if not csv_validation_result.is_valid:
        return GlossaryArtifactGenerationResult(
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

    artifact = build_glossary_artifact(source)
    artifact_validation_result = validate_glossary_artifact(artifact)
    if not artifact_validation_result.is_valid:
        return GlossaryArtifactGenerationResult(
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

    return GlossaryArtifactGenerationResult(
        source_key=source.key,
        csv_path=str(paths.csv_input),
        json_path=str(paths.json_output),
        record_count=len(artifact["records"]),
        csv_validation_result=csv_validation_result,
        artifact_validation_result=artifact_validation_result,
    )
