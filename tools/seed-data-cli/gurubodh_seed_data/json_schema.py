import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactValidationResult:
    is_valid: bool
    errors: tuple[str, ...]


def load_json_schema(schema_path):
    with schema_path.open(encoding="utf-8") as schema_file:
        return json.load(schema_file)


def validate_json_schema_value(value, schema, path="$"):
    errors = []

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path} must equal {schema['const']!r}.")

    if "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(repr(item) for item in schema["enum"])
        errors.append(f"{path} must be one of: {allowed}.")

    expected_type = schema.get("type")
    if expected_type and not _is_json_schema_type(value, expected_type):
        errors.append(f"{path} must be {expected_type}.")
        return errors

    if isinstance(value, dict):
        errors.extend(_validate_json_schema_object(value, schema, path))
    elif isinstance(value, list):
        errors.extend(_validate_json_schema_array(value, schema, path))
    elif isinstance(value, str):
        errors.extend(_validate_json_schema_string(value, schema, path))
    elif isinstance(value, int) and not isinstance(value, bool):
        errors.extend(_validate_json_schema_integer(value, schema, path))

    return errors


def validate_json_schema_artifact(artifact, schema_path):
    schema = load_json_schema(schema_path)
    errors = validate_json_schema_value(artifact, schema, "$")
    return ArtifactValidationResult(
        is_valid=not errors,
        errors=tuple(errors),
    )


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
                validate_json_schema_value(
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
        errors.extend(validate_json_schema_value(item, item_schema, f"{path}[{index}]"))

    return errors


def _validate_json_schema_string(value, schema, path):
    errors = []

    min_length = schema.get("minLength")
    if min_length is not None and len(value) < min_length:
        errors.append(f"{path} must have at least {min_length} character(s).")

    max_length = schema.get("maxLength")
    if max_length is not None and len(value) > max_length:
        errors.append(f"{path} must have at most {max_length} character(s).")

    pattern = schema.get("pattern")
    if pattern and not re.fullmatch(pattern, value):
        errors.append(f"{path} must match pattern {pattern}.")

    return errors


def _validate_json_schema_integer(value, schema, path):
    errors = []

    minimum = schema.get("minimum")
    if minimum is not None and value < minimum:
        errors.append(f"{path} must be greater than or equal to {minimum}.")

    return errors


def _is_json_schema_type(value, expected_type):
    if isinstance(expected_type, list):
        return any(_is_json_schema_type(value, item) for item in expected_type)
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
