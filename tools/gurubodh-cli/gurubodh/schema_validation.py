"""Executable JSON Schema boundaries for Gurubodh CLI jobs and artifacts."""

from __future__ import annotations

from functools import lru_cache
from importlib.metadata import PackageNotFoundError, distribution
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError


JOB_SCHEMAS = {
    "prep-subject": "prep_subject_job.schema.json",
    "generate-chunks": "generate_chunks_job.schema.json",
    "generate-docx": "generate_docx_job.schema.json",
}

ARTIFACT_SCHEMAS = {
    "chapter metadata": "chapter_metadata.schema.json",
    "chapter content manifest": "chapter_content_manifest.schema.json",
    "chapter proofreading": "chapter_proofreading.schema.json",
    "DOCX manifest": "docx_manifest.schema.json",
    "prep-subject job state": "prep_subject_job_state.schema.json",
    "proofreading manifest": "proofreading_manifest.schema.json",
    "semantic chunks": "semantic_chunks.schema.json",
    "semantic chunks manifest": "semantic_chunks_manifest.schema.json",
}


class SchemaDefinitionError(RuntimeError):
    """A required bundled schema is missing, malformed, or invalid."""


def _source_tree_schema_path(kind: str, filename: str) -> Path:
    return Path(__file__).resolve().parents[1] / "config" / kind / filename


def _installed_schema_path(kind: str, filename: str) -> Path | None:
    try:
        package_distribution = distribution("gurubodh_cli")
    except PackageNotFoundError:
        return None
    return Path(package_distribution.locate_file(Path("config") / kind / filename))


@lru_cache(maxsize=None)
def schema_path(kind: str, filename: str) -> Path:
    candidates = (
        _source_tree_schema_path(kind, filename),
        _installed_schema_path(kind, filename),
    )
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    locations = ", ".join(str(candidate) for candidate in candidates if candidate is not None)
    raise SchemaDefinitionError(
        f"Required bundled JSON Schema {kind}/{filename} was not found (checked: {locations})."
    )


@lru_cache(maxsize=None)
def _validator(kind: str, filename: str) -> Draft202012Validator:
    path = schema_path(kind, filename)
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaDefinitionError(f"Bundled JSON Schema is unreadable or malformed: {path}: {exc}") from exc
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        location = _json_path(exc.absolute_schema_path)
        raise SchemaDefinitionError(
            f"Bundled Draft 2020-12 JSON Schema is invalid: {path}: {location} violates the meta-schema."
        ) from exc
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _json_path(parts: Iterable[Any]) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", str(part)):
            path += f".{part}"
        else:
            escaped = str(part).replace("\\", "\\\\").replace("'", "\\'")
            path += f"['{escaped}']"
    return path


def _path_key(parts: Iterable[Any]) -> tuple[tuple[int, Any], ...]:
    return tuple((0, part) if isinstance(part, int) else (1, str(part)) for part in parts)


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _ensure_json_compatible(value: Any, parts: tuple[Any, ...] = ()) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{_json_path(parts)} must contain a finite JSON number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _ensure_json_compatible(item, (*parts, index))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{_json_path(parts)} has a non-string object property name")
            _ensure_json_compatible(item, (*parts, key))
        return
    raise ValueError(f"{_json_path(parts)} contains non-JSON value type {_json_type(value)}")


def _leaf_errors(error: ValidationError) -> list[ValidationError]:
    if error.validator not in {"oneOf", "anyOf"} or not error.context:
        return [error]

    branches: dict[Any, list[ValidationError]] = {}
    for child in error.context:
        schema_path = list(child.relative_schema_path)
        branch = schema_path[0] if schema_path else 0
        branches.setdefault(branch, []).extend(_leaf_errors(child))

    if isinstance(error.instance, dict) and isinstance(error.validator_value, list):
        for branch_index, branch_schema in enumerate(error.validator_value):
            if not isinstance(branch_schema, dict):
                continue
            properties = branch_schema.get("properties", {})
            for property_name, property_schema in properties.items():
                if (
                    isinstance(property_schema, dict)
                    and "const" in property_schema
                    and error.instance.get(property_name) == property_schema["const"]
                    and branch_index in branches
                ):
                    return branches[branch_index]

    def branch_score(item: tuple[Any, list[ValidationError]]) -> tuple[Any, ...]:
        branch, errors = item
        deepest_instance_path = max((len(error.absolute_path) for error in errors), default=0)
        return (
            len(errors),
            -deepest_instance_path,
            tuple(_path_key(error.absolute_path) for error in errors),
            str(branch),
        )

    return min(branches.items(), key=branch_score)[1]


def _actionable_errors(validator: Draft202012Validator, instance: Any) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for error in validator.iter_errors(instance):
        errors.extend(_leaf_errors(error))
    errors.sort(
        key=lambda error: (
            _path_key(error.absolute_path),
            _path_key(error.absolute_schema_path),
            error.validator or "",
            error.message,
        )
    )
    paths_with_const = {
        tuple(error.absolute_path) for error in errors if error.validator == "const"
    }
    return [
        error
        for error in errors
        if not (
            tuple(error.absolute_path) in paths_with_const
            and error.validator in {"enum", "type"}
        )
    ]


def _additional_properties(error: ValidationError) -> list[str]:
    if not isinstance(error.instance, dict) or not isinstance(error.schema, dict):
        return []
    declared = set(error.schema.get("properties", {}))
    pattern_properties = [re.compile(pattern) for pattern in error.schema.get("patternProperties", {})]
    return sorted(
        key
        for key in error.instance
        if key not in declared and not any(pattern.search(key) for pattern in pattern_properties)
    )


def _expected(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _messages_for(error: ValidationError) -> list[tuple[tuple[Any, ...], str]]:
    parts = tuple(error.absolute_path)
    rule = error.validator
    value = error.validator_value

    if rule == "additionalProperties":
        unknown = _additional_properties(error)
        return [((*parts, key), "is not allowed.") for key in unknown] or [(parts, "contains an unknown property.")]
    if rule == "required":
        match = re.match(r"'([^']+)' is a required property", error.message)
        if match:
            return [((*parts, match.group(1)), "is required.")]
    if rule == "type":
        expected = " or ".join(value) if isinstance(value, list) else str(value)
        return [(parts, f"must be {expected}; found {_json_type(error.instance)}.")]
    if rule == "const":
        return [(parts, f"must equal {_expected(value)}.")]
    if rule == "enum":
        return [(parts, f"must be one of {_expected(value)}.")]
    if rule == "pattern":
        return [(parts, f"must match {value}.")]
    if rule == "minimum":
        return [(parts, f"must be at least {value}.")]
    if rule == "maximum":
        return [(parts, f"must be at most {value}.")]
    if rule == "exclusiveMinimum":
        return [(parts, f"must be greater than {value}.")]
    if rule == "exclusiveMaximum":
        return [(parts, f"must be less than {value}.")]
    if rule == "minLength":
        return [(parts, "must not be empty." if value == 1 else f"must contain at least {value} characters.")]
    if rule == "minItems":
        return [(parts, f"must contain at least {value} item(s).")]
    if rule == "maxItems":
        return [(parts, f"must contain at most {value} item(s).")]
    if rule == "uniqueItems":
        return [(parts, "must not contain duplicate items.")]
    if rule == "format":
        return [(parts, f"must be a valid {value} value.")]
    if rule == "not" and isinstance(value, dict) and value.get("required"):
        return [((*parts, key), "is not allowed in this context.") for key in sorted(value["required"])]
    if rule in {"oneOf", "anyOf"}:
        return [(parts, "does not match an allowed object shape.")]
    return [(parts, f"violates JSON Schema rule {rule!r}.")]


def _validation_failure(prefix: str, errors: list[ValidationError]) -> SystemExit:
    messages: list[tuple[tuple[Any, ...], str]] = []
    for error in errors:
        messages.extend(_messages_for(error))
    messages = sorted(set(messages), key=lambda item: (_path_key(item[0]), item[1]))
    rendered = [f"{_json_path(path)} {message}" for path, message in messages]
    if len(rendered) == 1:
        return SystemExit(f"{prefix}: {rendered[0]}")
    return SystemExit(f"{prefix}:\n" + "\n".join(f"- {message}" for message in rendered))


def _validate(instance: Any, kind: str, filename: str, prefix: str) -> None:
    try:
        _ensure_json_compatible(instance)
        validator = _validator(kind, filename)
    except (SchemaDefinitionError, ValueError) as exc:
        raise SystemExit(f"{prefix}: {str(exc).rstrip('.')}.") from exc
    errors = _actionable_errors(validator, instance)
    if errors:
        raise _validation_failure(prefix, errors)


def validate_job(instance: Any, job_name: str, path: str | Path | None = None) -> None:
    filename = JOB_SCHEMAS[job_name]
    identity = f"{job_name} job"
    if path is not None:
        identity += f", {path}"
    _validate(instance, "jobs", filename, f"Config validation failed ({identity})")


def validate_artifact(
    instance: Any,
    artifact_name: str,
    path: str | Path | None = None,
) -> None:
    filename = ARTIFACT_SCHEMAS[artifact_name]
    identity = artifact_name
    if path is not None:
        identity += f", {path}"
    _validate(instance, "artifacts", filename, f"Artifact validation failed ({identity})")


def validated_artifact_json(
    instance: Any,
    artifact_name: str,
    path: str | Path | None = None,
) -> str:
    """Validate an artifact payload before returning deterministic JSON text."""
    validate_artifact(instance, artifact_name, path)
    return json.dumps(instance, ensure_ascii=False, indent=2) + "\n"


def write_json_artifact(path: str | Path, instance: Any, artifact_name: str) -> Path:
    """Validate and write one schema-governed JSON artifact."""
    output = Path(path)
    serialized = validated_artifact_json(instance, artifact_name, output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialized, encoding="utf-8")
    return output
