import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

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
class GlossaryArtifactValidationResult:
    is_valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True)
class GlossaryArtifactGenerationResult:
    source_key: str
    csv_path: str
    json_path: str
    record_count: int
    csv_validation_result: object
    artifact_validation_result: GlossaryArtifactValidationResult


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
    schema = _load_glossary_artifact_schema()
    errors = _validate_json_schema_value(artifact, schema, "$")
    return GlossaryArtifactValidationResult(
        is_valid=not errors,
        errors=tuple(errors),
    )


def _load_glossary_artifact_schema():
    with GLOSSARY_ARTIFACT_SCHEMA_PATH.open(encoding="utf-8") as schema_file:
        return json.load(schema_file)


def _validate_json_schema_value(value, schema, path):
    errors = []

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path} must equal {schema['const']!r}.")

    expected_type = schema.get("type")
    if expected_type and not _is_json_schema_type(value, expected_type):
        errors.append(f"{path} must be {expected_type}.")
        return errors

    if expected_type == "object":
        errors.extend(_validate_json_schema_object(value, schema, path))
    elif expected_type == "array":
        errors.extend(_validate_json_schema_array(value, schema, path))
    elif expected_type == "string":
        errors.extend(_validate_json_schema_string(value, schema, path))

    return errors


def _validate_json_schema_object(value, schema, path):
    errors = []
    properties = schema.get("properties", {})

    for field_name in schema.get("required", ()):
        if field_name not in value:
            errors.append(f"{path}.{field_name} is required.")

    if schema.get("additionalProperties") is False:
        for field_name in sorted(set(value) - set(properties)):
            errors.append(f"{path}.{field_name} is not allowed.")

    for field_name, field_schema in properties.items():
        if field_name in value:
            errors.extend(
                _validate_json_schema_value(
                    value[field_name],
                    field_schema,
                    f"{path}.{field_name}",
                )
            )

    return errors


def _validate_json_schema_array(value, schema, path):
    errors = []
    item_schema = schema.get("items")
    if not item_schema:
        return errors

    for index, item in enumerate(value):
        errors.extend(
            _validate_json_schema_value(item, item_schema, f"{path}[{index}]")
        )

    return errors


def _validate_json_schema_string(value, schema, path):
    errors = []

    min_length = schema.get("minLength")
    if min_length is not None and len(value) < min_length:
        errors.append(f"{path} must have at least {min_length} character(s).")

    pattern = schema.get("pattern")
    if pattern and not re.fullmatch(pattern, value):
        errors.append(f"{path} must match pattern {pattern}.")

    return errors


def _is_json_schema_type(value, expected_type):
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return False


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
            artifact_validation_result=GlossaryArtifactValidationResult(
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
