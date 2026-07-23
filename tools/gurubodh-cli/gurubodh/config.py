import json
import re

from gurubodh.constants import (
    CONVERSION_JOB_SCHEMA_VERSION,
    GENERATE_CHUNKS_JOB_SCHEMA_VERSION,
    PIPELINE_GENERATE_CHUNKS,
    PIPELINE_ENTRY_POINTS,
    PIPELINE_LEGACY_DOCX_TO_UNICODE,
    PIPELINE_UNICODE_DOCX_INGEST,
    SUPPORTED_LEGACY_ENCODINGS,
    SUPPORTED_FONT_ENCODINGS,
)
from gurubodh.ml.semantic_chunking.config import SemanticChunkConfig, SemanticChunkConfigError


REGEX_FLAG_VALUES = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
    "VERBOSE": re.VERBOSE,
}


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


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


def optional_string_array(data, key, context):
    value = data.get(key)
    if value is None:
        return value
    if not isinstance(value, list):
        raise SystemExit(f"Config error: {context}.{key} must be an array of strings")
    for item in value:
        if not isinstance(item, str) or not item:
            raise SystemExit(f"Config error: {context}.{key} must contain only non-empty strings")
    return value


def require_number(data, key, context):
    value = data.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise SystemExit(f"Config error: {context}.{key} must be a number")
    return value


def require_integer(data, key, context):
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise SystemExit(f"Config error: {context}.{key} must be an integer")
    return value


def require_boolean(data, key, context):
    value = data.get(key)
    if not isinstance(value, bool):
        raise SystemExit(f"Config error: {context}.{key} must be true or false")
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


def validate_subject_artifact_storage(section, context):
    backend = storage_backend(section, context)
    if backend == "local":
        require_string(section, "root_dir", context)
    else:
        require_string(section, "bucket", context)
        require_string(section, "prefix", context)
        optional_string_or_null(section, "url_base", context)
    require_string(section, "subject_dir", context)


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


def load_prep_subject_job(path):
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

    metadata_defaults = config.get("metadata_defaults", {})
    if metadata_defaults and not isinstance(metadata_defaults, dict):
        raise SystemExit("Config error: metadata_defaults must be an object")
    optional_string_array(metadata_defaults, "summary_chapter_markers", "metadata_defaults")
    validate_pipeline_matches_source(config)
    return config


def load_conversion_job(path):
    return load_prep_subject_job(path)


def load_generate_chunks_job(path):
    config = read_json(path)
    if not isinstance(config, dict):
        raise SystemExit("Config error: root must be an object")
    if config.get("schema_version") != GENERATE_CHUNKS_JOB_SCHEMA_VERSION:
        raise SystemExit(
            f"Config error: schema_version must be {GENERATE_CHUNKS_JOB_SCHEMA_VERSION}"
        )
    pipeline = require_string(config, "pipeline", "root")
    if pipeline != PIPELINE_GENERATE_CHUNKS:
        raise SystemExit("Config error: pipeline must be generate-chunks")

    source = require_object(config, "source", "root")
    destination = require_object(config, "destination", "root")
    naming = require_object(config, "naming", "root")
    chunking = require_object(config, "chunking", "root")

    validate_subject_artifact_storage(source, "source")
    validate_subject_artifact_storage(destination, "destination")

    require_string(naming, "category_code", "naming", r"CAT[0-9]{3}")
    require_string(naming, "subject_code", "naming", r"SUB[0-9]{3}")
    require_string(naming, "title_slug", "naming", r"[A-Za-z0-9][A-Za-z0-9-]*")
    require_string(naming, "version", "naming", r"[0-9]{2}")
    require_string(naming, "subversion", "naming", r"[0-9]{2}")

    chapters = config.get("chapters")
    if chapters is not None:
        if not isinstance(chapters, list) or not chapters:
            raise SystemExit("Config error: chapters must be a non-empty array when present")
        for chapter in chapters:
            if not isinstance(chapter, str) or not re.fullmatch(r"[0-9]{3}", chapter):
                raise SystemExit("Config error: chapters must contain zero-padded chapter numbers like 001")

    try:
        config["_semantic_chunk_config"] = SemanticChunkConfig.from_env(
            provider=require_string(chunking, "provider", "chunking"),
            model_name=require_string(chunking, "model", "chunking"),
            model_revision=optional_string_or_null(chunking, "model_revision", "chunking"),
            embedding_mode=require_string(chunking, "embedding_mode", "chunking"),
            embedding_dimension=require_integer(chunking, "embedding_dimension", "chunking"),
            threshold_percentile=require_number(chunking, "threshold_percentile", "chunking"),
            min_chars=require_integer(chunking, "min_chars", "chunking"),
            window_size=require_integer(chunking, "window_size", "chunking"),
            batch_size=require_integer(chunking, "batch_size", "chunking"),
            normalize_embeddings=require_boolean(chunking, "normalize_embeddings", "chunking"),
            device=optional_string_or_null(chunking, "device", "chunking"),
            local_files_only=require_boolean(chunking, "local_files_only", "chunking"),
        )
    except SemanticChunkConfigError as exc:
        raise SystemExit(f"Config error: {exc}") from exc
    return config
