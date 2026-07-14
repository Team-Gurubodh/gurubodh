import json
import re
from pathlib import Path

from gurubodh_utils.constants import (
    CONVERSION_JOB_SCHEMA_VERSION,
    DEFAULT_FORMATTING_CONFIG,
    PIPELINE_ENTRY_POINTS,
    PIPELINE_LEGACY_DOCX_TO_UNICODE,
    PIPELINE_UNICODE_DOCX_INGEST,
    PREVIOUS_CONVERSION_JOB_SCHEMA_VERSION,
    SUPPORTED_FORMATTING_MODELS,
    SUPPORTED_FORMATTING_OUTPUT_FORMATS,
    SUPPORTED_FORMATTING_PROVIDERS,
    SUPPORTED_FORMATTING_REGENERATE_MODES,
    SUPPORTED_LEGACY_ENCODINGS,
    SUPPORTED_FONT_ENCODINGS,
)


REGEX_FLAG_VALUES = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
    "VERBOSE": re.VERBOSE,
}

FORMATTING_KEYS = set(DEFAULT_FORMATTING_CONFIG)
MAX_FORMATTING_RETRIES = 5
SCHEMA_VERSION_PATTERN = re.compile(
    r'(?P<prefix>"schema_version"\s*:\s*")'
    + re.escape(PREVIOUS_CONVERSION_JOB_SCHEMA_VERSION)
    + r'(?P<suffix>")',
    re.MULTILINE,
)
PREVIOUS_CONVERSION_JOB_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / f"conversion_job.{PREVIOUS_CONVERSION_JOB_SCHEMA_VERSION}.schema.json"
)


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def schema_type_matches(value, expected_type):
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def schema_path_child(path, child):
    if path == "$":
        return f"$.{child}"
    return f"{path}.{child}"


def validate_json_schema_subset(value, schema, path="$"):
    errors = []

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path} must be {schema['const']!r}")
        return errors

    if "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(repr(item) for item in schema["enum"])
        errors.append(f"{path} must be one of: {allowed}")
        return errors

    expected_type = schema.get("type")
    if expected_type:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(schema_type_matches(value, item) for item in expected_types):
            errors.append(f"{path} must be {expected_type}")
            return errors

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path} must not be empty")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            errors.append(f"{path} must match {schema['pattern']}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path} must be at least {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path} must be at most {schema['maximum']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path} must contain at least {schema['minItems']} item(s)")
        serialized_items = {json.dumps(item, sort_keys=True) for item in value}
        if schema.get("uniqueItems") and len(serialized_items) != len(value):
            errors.append(f"{path} values must be unique")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                errors.extend(validate_json_schema_subset(item, item_schema, f"{path}[{index}]"))

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{schema_path_child(path, key)} is required")

        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown_keys = sorted(set(value) - set(properties))
            for key in unknown_keys:
                errors.append(f"{schema_path_child(path, key)} is not allowed")

        for key, property_schema in properties.items():
            if key in value:
                errors.extend(
                    validate_json_schema_subset(
                        value[key],
                        property_schema,
                        schema_path_child(path, key),
                    )
                )

    for subschema in schema.get("allOf", []):
        errors.extend(validate_json_schema_subset(value, subschema, path))

    if "if" in schema:
        if_errors = validate_json_schema_subset(value, schema["if"], path)
        if not if_errors and "then" in schema:
            errors.extend(validate_json_schema_subset(value, schema["then"], path))
        if if_errors and "else" in schema:
            errors.extend(validate_json_schema_subset(value, schema["else"], path))

    if "not" in schema:
        not_errors = validate_json_schema_subset(value, schema["not"], path)
        if not not_errors:
            errors.append(f"{path} must not match a disallowed schema")

    return errors


def validate_previous_conversion_job(path, data):
    schema = read_json(PREVIOUS_CONVERSION_JOB_SCHEMA_PATH)
    errors = validate_json_schema_subset(data, schema)
    if errors:
        details = "; ".join(errors[:3])
        if len(errors) > 3:
            details += f"; and {len(errors) - 3} more error(s)"
        raise SystemExit(
            f"Migration error: {path} is not valid schema_version "
            f"{PREVIOUS_CONVERSION_JOB_SCHEMA_VERSION}: {details}"
        )


def default_formatting_block_text():
    formatting_json = json.dumps(DEFAULT_FORMATTING_CONFIG, ensure_ascii=False, indent=2)
    lines = formatting_json.splitlines()
    property_lines = [f'  "formatting": {lines[0]}']
    property_lines.extend(f"  {line}" for line in lines[1:])
    return "\n".join(property_lines)


def find_root_object_closing_brace(text):
    in_string = False
    escaped = False
    depth = 0
    root_started = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
            root_started = True
        elif char == "}":
            depth -= 1
            if root_started and depth == 0:
                return index

    return None


def add_default_formatting_block(text):
    closing_brace_index = find_root_object_closing_brace(text)
    if closing_brace_index is None:
        raise SystemExit("Migration error: could not find root object closing brace")

    insertion_index = closing_brace_index
    while insertion_index > 0 and text[insertion_index - 1].isspace():
        insertion_index -= 1

    formatting_block = default_formatting_block_text()
    return (
        text[:insertion_index]
        + ",\n"
        + formatting_block
        + "\n"
        + text[closing_brace_index:]
    )


def require_object(data, key, context):
    value = data.get(key)
    if not isinstance(value, dict):
        raise SystemExit(f"Config error: {context}.{key} must be an object")
    return value


def require_string(data, key, context, pattern=None):
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise SystemExit(f"Config error: {context}.{key} must be a non-empty string")
    if pattern and not re.fullmatch(pattern, value):
        raise SystemExit(f"Config error: {context}.{key} has invalid value: {value}")
    return value


def optional_string_or_null(data, key, context):
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        raise SystemExit(f"Config error: {context}.{key} must be a string or null")
    return value


def require_boolean(data, key, context):
    value = data.get(key)
    if not isinstance(value, bool):
        raise SystemExit(f"Config error: {context}.{key} must be true or false")
    return value


def require_number(data, key, context, minimum=None):
    value = data.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise SystemExit(f"Config error: {context}.{key} must be a number")
    if minimum is not None and value < minimum:
        raise SystemExit(f"Config error: {context}.{key} must be at least {minimum}")
    return value


def require_integer(data, key, context, minimum=None, maximum=None):
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise SystemExit(f"Config error: {context}.{key} must be an integer")
    if minimum is not None and value < minimum:
        raise SystemExit(f"Config error: {context}.{key} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise SystemExit(f"Config error: {context}.{key} must be at most {maximum}")
    return value


def require_enum(data, key, context, allowed_values):
    value = require_string(data, key, context)
    if value not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        raise SystemExit(f"Config error: {context}.{key} must be one of: {allowed}")
    return value


def chapter_split_regex_flags(chapter_split):
    flags = chapter_split.get("flags", [])
    if not isinstance(flags, list):
        raise SystemExit("Config error: chapter_split.flags must be an array of strings")

    compiled_flags = 0
    for flag in flags:
        if not isinstance(flag, str) or flag not in REGEX_FLAG_VALUES:
            allowed = ", ".join(sorted(REGEX_FLAG_VALUES))
            raise SystemExit(f"Config error: unsupported chapter_split flag {flag!r}. Allowed: {allowed}")
        compiled_flags |= REGEX_FLAG_VALUES[flag]
    return compiled_flags


def prepare_chapter_split(chapter_split):
    pattern_type = require_string(chapter_split, "pattern_type", "chapter_split", r"(literal|regex)")
    pattern = require_string(chapter_split, "pattern", "chapter_split")

    if pattern_type == "literal":
        if "flags" in chapter_split:
            raise SystemExit("Config error: chapter_split.flags can only be used with regex patterns")
        return

    flags = chapter_split_regex_flags(chapter_split)
    try:
        chapter_split["_compiled_pattern"] = re.compile(pattern, flags)
    except re.error as exc:
        raise SystemExit(f"Config error: chapter_split.pattern is not a valid regex: {exc}") from exc


def normalized_source_font_encoding(config):
    return config["source"]["font_encoding"].strip().lower()


def source_is_unicode(config):
    return normalized_source_font_encoding(config) == "unicode"


def source_is_legacy(config):
    return normalized_source_font_encoding(config) in SUPPORTED_LEGACY_ENCODINGS


def storage_backend(section, context):
    backend = section.get("backend", "local")
    if backend not in {"local", "r2"}:
        raise SystemExit(f"Config error: {context}.backend must be local or r2")
    return backend


def validate_source_storage(source):
    backend = storage_backend(source, "source")
    if backend == "local":
        require_string(source, "root_dir", "source")
        require_string(source, "relative_path", "source")
    else:
        require_string(source, "bucket", "source")
        require_string(source, "key", "source")
        optional_string_or_null(source, "url_base", "source")


def validate_destination_storage(destination):
    backend = storage_backend(destination, "destination")
    if backend == "local":
        require_string(destination, "root_dir", "destination")
    else:
        require_string(destination, "bucket", "destination")
        require_string(destination, "prefix", "destination")
        optional_string_or_null(destination, "url_base", "destination")
    require_string(destination, "subject_dir", "destination")


def validate_and_normalize_formatting(config):
    raw_formatting = config.get("formatting")
    if raw_formatting is None:
        config["formatting"] = dict(DEFAULT_FORMATTING_CONFIG)
        return config["formatting"]
    if not isinstance(raw_formatting, dict):
        raise SystemExit("Config error: formatting must be an object")

    unknown_keys = sorted(set(raw_formatting) - FORMATTING_KEYS)
    if unknown_keys:
        keys = ", ".join(unknown_keys)
        raise SystemExit(f"Config error: formatting has unsupported fields: {keys}")

    formatting = dict(DEFAULT_FORMATTING_CONFIG)
    formatting.update(raw_formatting)

    require_boolean(formatting, "enabled", "formatting")
    require_enum(formatting, "provider", "formatting", SUPPORTED_FORMATTING_PROVIDERS)
    require_enum(formatting, "model", "formatting", SUPPORTED_FORMATTING_MODELS)
    require_enum(formatting, "fallback_model", "formatting", SUPPORTED_FORMATTING_MODELS)

    output_formats = formatting.get("output_formats")
    if not isinstance(output_formats, list) or not output_formats:
        raise SystemExit("Config error: formatting.output_formats must be a non-empty array")
    seen_formats = set()
    for output_format in output_formats:
        if not isinstance(output_format, str) or output_format not in SUPPORTED_FORMATTING_OUTPUT_FORMATS:
            allowed = ", ".join(sorted(SUPPORTED_FORMATTING_OUTPUT_FORMATS))
            raise SystemExit(f"Config error: formatting.output_formats must contain only: {allowed}")
        if output_format in seen_formats:
            raise SystemExit("Config error: formatting.output_formats values must be unique")
        seen_formats.add(output_format)

    require_boolean(formatting, "continue_on_error", "formatting")
    require_number(formatting, "delay_seconds", "formatting", minimum=0)
    require_integer(formatting, "max_retries", "formatting", minimum=0, maximum=MAX_FORMATTING_RETRIES)
    require_enum(formatting, "regenerate", "formatting", SUPPORTED_FORMATTING_REGENERATE_MODES)

    config["formatting"] = formatting
    return formatting


def validate_pipeline_matches_source(config, expected_pipeline=None):
    pipeline = config["pipeline"]
    if expected_pipeline and pipeline != expected_pipeline:
        raise SystemExit(
            f"Config error: pipeline {pipeline!r} cannot be processed by {expected_pipeline!r}"
        )
    if pipeline == PIPELINE_UNICODE_DOCX_INGEST and not source_is_unicode(config):
        raise SystemExit("Config error: unicode-docx-ingest requires source.font_encoding=unicode")
    if pipeline == PIPELINE_LEGACY_DOCX_TO_UNICODE and not source_is_legacy(config):
        raise SystemExit(
            "Config error: legacy-docx-to-unicode requires source.font_encoding to be aps or shreelipi"
        )


def load_conversion_job(path):
    config = read_json(path)
    if not isinstance(config, dict):
        raise SystemExit("Config error: root must be an object")
    if config.get("schema_version") != CONVERSION_JOB_SCHEMA_VERSION:
        raise SystemExit(
            f"Config error: schema_version must be {CONVERSION_JOB_SCHEMA_VERSION}"
        )

    pipeline = require_string(config, "pipeline", "root")
    if pipeline not in PIPELINE_ENTRY_POINTS:
        allowed = ", ".join(sorted(PIPELINE_ENTRY_POINTS))
        raise SystemExit(f"Config error: pipeline must be one of: {allowed}")

    source = require_object(config, "source", "root")
    destination = require_object(config, "destination", "root")
    naming = require_object(config, "naming", "root")
    chapter_split = require_object(config, "chapter_split", "root")

    validate_source_storage(source)
    font_encoding = require_string(source, "font_encoding", "source")
    if font_encoding not in SUPPORTED_FONT_ENCODINGS:
        allowed = ", ".join(sorted(SUPPORTED_FONT_ENCODINGS))
        raise SystemExit(f"Config error: source.font_encoding must be one of: {allowed}")
    file_format = require_string(source, "file_format", "source", r"[A-Za-z0-9]+")
    if file_format.lower() != "docx":
        raise SystemExit("Config error: source.file_format must be docx")
    validate_destination_storage(destination)

    require_string(naming, "category_code", "naming", r"CAT[0-9]{3}")
    require_string(naming, "subject_code", "naming", r"SUB[0-9]{3}")
    require_string(naming, "title_slug", "naming", r"[A-Za-z0-9][A-Za-z0-9-]*")
    require_string(naming, "version", "naming", r"[0-9]{2}")
    require_string(naming, "subversion", "naming", r"[0-9]{2}")

    if not isinstance(chapter_split.get("enabled"), bool):
        raise SystemExit("Config error: chapter_split.enabled must be true or false")
    if chapter_split.get("enabled"):
        prepare_chapter_split(chapter_split)

    validate_and_normalize_formatting(config)

    metadata_defaults = config.get("metadata_defaults", {})
    if metadata_defaults and not isinstance(metadata_defaults, dict):
        raise SystemExit("Config error: metadata_defaults must be an object")
    validate_pipeline_matches_source(config)
    return config


def migrate_conversion_job_text(path, apply=False):
    data = read_json(path)
    if not isinstance(data, dict):
        raise SystemExit(f"Migration error: {path} root must be an object")

    original_text = path.read_text(encoding="utf-8")
    schema_version = data.get("schema_version")
    if schema_version == CONVERSION_JOB_SCHEMA_VERSION:
        if "formatting" in data:
            return {"path": path, "status": "unchanged-current"}

        migrated_text = add_default_formatting_block(original_text)
        if apply:
            path.write_text(migrated_text, encoding="utf-8")
            status = "added-formatting-defaults"
        else:
            status = "would-add-formatting-defaults"
        return {
            "path": path,
            "status": status,
            "formatting_block": default_formatting_block_text(),
        }
    if schema_version != PREVIOUS_CONVERSION_JOB_SCHEMA_VERSION:
        raise SystemExit(
            f"Migration error: {path} has unsupported schema_version {schema_version!r}"
        )
    validate_previous_conversion_job(path, data)

    migrated_text, replacements = SCHEMA_VERSION_PATTERN.subn(
        rf'\g<prefix>{CONVERSION_JOB_SCHEMA_VERSION}\g<suffix>',
        original_text,
        count=1,
    )
    if replacements != 1:
        raise SystemExit(f"Migration error: could not update schema_version in {path}")
    migrated_text = add_default_formatting_block(migrated_text)

    if apply:
        path.write_text(migrated_text, encoding="utf-8")
        status = "migrated"
    else:
        status = "would-migrate"
    return {
        "path": path,
        "status": status,
        "formatting_block": default_formatting_block_text(),
    }


def migrate_conversion_job_paths(paths, apply=False):
    return [migrate_conversion_job_text(path, apply=apply) for path in paths]
