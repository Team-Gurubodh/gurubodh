import json
import re
from pathlib import PurePosixPath

from gurubodh.constants import (
    CONVERSION_JOB_SCHEMA_VERSION,
    GENERATE_CHUNKS_JOB_SCHEMA_VERSION,
    GENERATE_DOCX_JOB_SCHEMA_VERSION,
    PIPELINE_GENERATE_CHUNKS,
    PIPELINE_GENERATE_DOCX,
    PIPELINE_ENTRY_POINTS,
    PIPELINE_LEGACY_DOCX_TO_UNICODE,
    PIPELINE_UNICODE_DOCX_INGEST,
    SUPPORTED_LEGACY_ENCODINGS,
    SUPPORTED_FONT_ENCODINGS,
)
from gurubodh.ml.semantic_chunking.config import SemanticChunkConfig, SemanticChunkConfigError
from gurubodh.locales import locale_spec
from gurubodh.proofreading import ProofreadingSettings


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


def require_exact_keys(data, required, optional, context):
    keys = set(data)
    missing = sorted(set(required) - keys)
    unknown = sorted(keys - set(required) - set(optional))
    if missing:
        raise SystemExit(f"Config error: {context} is missing required field(s): {', '.join(missing)}")
    if unknown:
        raise SystemExit(f"Config error: {context} has unsupported field(s): {', '.join(unknown)}")


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


def validate_language_partition(subject_dir, language, context):
    if "\\" in subject_dir:
        raise SystemExit(f"Config error: {context}.subject_dir must use POSIX path separators")
    raw_segments = subject_dir.split("/")
    if any(not segment for segment in raw_segments):
        raise SystemExit(f"Config error: {context}.subject_dir must not contain empty path segments")
    if any(segment in {".", ".."} for segment in raw_segments):
        raise SystemExit(f"Config error: {context}.subject_dir must not contain '.' or '..' path segments")
    path = PurePosixPath(subject_dir)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise SystemExit(f"Config error: {context}.subject_dir must be a safe relative path")
    if len(path.parts) < 2:
        raise SystemExit(
            f"Config error: {context}.subject_dir must retain a subject grouping before its language partition"
        )
    if path.parts[-1] != language:
        raise SystemExit(
            f"Config error: {context}.subject_dir final language partition must match {language!r}"
        )
    return str(path)


def validate_safe_posix_prefix(value, context):
    if "\\" in value:
        raise SystemExit(f"Config error: {context} must use POSIX path separators")
    segments = value.split("/")
    if any(not segment for segment in segments):
        raise SystemExit(f"Config error: {context} must not contain empty path segments")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise SystemExit(f"Config error: {context} must be a safe relative path")
    return str(path)


def validate_destination_storage(destination, language):
    backend = storage_backend(destination, "destination")
    if backend == "local":
        require_string(destination, "root_dir", "destination")
    else:
        require_string(destination, "bucket", "destination")
        require_string(destination, "prefix", "destination")
        optional_string_or_null(destination, "url_base", "destination")
    subject_dir = require_string(destination, "subject_dir", "destination")
    validate_language_partition(subject_dir, language, "destination")


def validate_subject_artifact_storage(section, context, language):
    backend = storage_backend(section, context)
    if backend == "local":
        require_string(section, "root_dir", context)
    else:
        require_string(section, "bucket", context)
        require_string(section, "prefix", context)
        optional_string_or_null(section, "url_base", context)
    subject_dir = require_string(section, "subject_dir", context)
    validate_language_partition(subject_dir, language, context)


def validate_metadata_defaults(config):
    metadata_defaults = require_object(config, "metadata_defaults", "root")
    language = require_string(metadata_defaults, "language", "metadata_defaults")
    try:
        locale = locale_spec(language)
    except ValueError as exc:
        raise SystemExit(f"Config error: metadata_defaults.language is invalid: {exc}") from exc
    source_script = require_string(metadata_defaults, "source_script", "metadata_defaults")
    if source_script != locale.source_script:
        raise SystemExit(
            f"Config error: metadata_defaults.source_script must be {locale.source_script!r} for {language}"
        )
    output_text_encoding = require_string(metadata_defaults, "output_text_encoding", "metadata_defaults")
    if output_text_encoding != locale.output_text_encoding:
        raise SystemExit(
            f"Config error: metadata_defaults.output_text_encoding must be {locale.output_text_encoding!r} for {language}"
        )
    optional_string_array(metadata_defaults, "summary_chapter_markers", "metadata_defaults")
    return locale


def validate_pipeline_matches_source(config, expected_pipeline=None):
    pipeline = config["pipeline"]
    if expected_pipeline and pipeline != expected_pipeline:
        raise SystemExit(
            f"Config error: pipeline {pipeline!r} cannot be processed by {expected_pipeline!r}"
        )
    if pipeline == PIPELINE_UNICODE_DOCX_INGEST and not source_is_unicode(config):
        raise SystemExit("Config error: unicode-docx-ingest requires source.font_encoding=unicode")
    if pipeline == PIPELINE_LEGACY_DOCX_TO_UNICODE and not source_is_legacy(config):
        raise SystemExit("Config error: legacy-docx-to-unicode requires source.font_encoding=aps")


def proofreading_config(config):
    value = config.get("proofreading")
    if not isinstance(value, dict):
        raise SystemExit("Config error: proofreading is required and must be an object")
    allowed = set(ProofreadingSettings.__dataclass_fields__) | {"enabled", "continue_on_error"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise SystemExit(f"Config error: unsupported proofreading option(s): {', '.join(unknown)}")
    if "enabled" in value and value["enabled"] is not True:
        raise SystemExit("Config error: proofreading.enabled must be true; proofreading is mandatory")
    if "continue_on_error" in value and value["continue_on_error"] is not False:
        raise SystemExit("Config error: proofreading.continue_on_error must be false; proofread failures are strict")
    settings = ProofreadingSettings.from_config(value)
    if settings.provider != "google-ai-studio":
        raise SystemExit("Config error: proofreading.provider must be google-ai-studio")
    if not isinstance(settings.model, str) or not settings.model:
        raise SystemExit("Config error: proofreading.model must be a non-empty string")
    integer_fields = ("max_output_tokens", "max_input_characters", "max_retries", "max_requests_per_minute", "max_estimated_input_tokens_per_minute")
    for field in integer_fields:
        if not isinstance(getattr(settings, field), int) or isinstance(getattr(settings, field), bool) or getattr(settings, field) < 1:
            raise SystemExit(f"Config error: proofreading.{field} must be a positive integer")
    for field in ("initial_retry_delay_seconds", "max_retry_delay_seconds", "min_request_interval_seconds"):
        if not isinstance(getattr(settings, field), (int, float)) or isinstance(getattr(settings, field), bool) or getattr(settings, field) < 0:
            raise SystemExit(f"Config error: proofreading.{field} must be a non-negative number")
    if settings.max_retry_delay_seconds < settings.initial_retry_delay_seconds:
        raise SystemExit("Config error: proofreading.max_retry_delay_seconds must be at least initial_retry_delay_seconds")
    return settings


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
    locale = validate_metadata_defaults(config)
    validate_destination_storage(destination, locale.language)

    require_string(naming, "category_code", "naming", r"CAT[0-9]{3}")
    require_string(naming, "subject_code", "naming", r"SUB[0-9]{3}")
    require_string(naming, "title_slug", "naming", r"[A-Za-z0-9][A-Za-z0-9-]*")
    require_string(naming, "version", "naming", r"[0-9]{2}")
    require_string(naming, "subversion", "naming", r"[0-9]{2}")

    if not isinstance(chapter_split.get("enabled"), bool):
        raise SystemExit("Config error: chapter_split.enabled must be true or false")
    if chapter_split.get("enabled"):
        prepare_chapter_split(chapter_split)

    config["_locale"] = locale
    config["_proofreading_config"] = proofreading_config(config)
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

    require_string(naming, "category_code", "naming", r"CAT[0-9]{3}")
    require_string(naming, "subject_code", "naming", r"SUB[0-9]{3}")
    require_string(naming, "title_slug", "naming", r"[A-Za-z0-9][A-Za-z0-9-]*")
    require_string(naming, "version", "naming", r"[0-9]{2}")
    require_string(naming, "subversion", "naming", r"[0-9]{2}")
    language = require_string(naming, "language", "naming")
    try:
        locale_spec(language)
    except ValueError as exc:
        raise SystemExit(f"Config error: naming.language is invalid: {exc}") from exc
    validate_subject_artifact_storage(source, "source", language)
    validate_subject_artifact_storage(destination, "destination", language)
    if source["subject_dir"] != destination["subject_dir"]:
        raise SystemExit(
            "Config error: generate-chunks source.subject_dir and destination.subject_dir must use the same language-qualified root"
        )

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
            model_revision=require_string(
                chunking,
                "model_revision",
                "chunking",
                r"[0-9a-f]{40}",
            ),
            threshold_percentile=require_number(chunking, "threshold_percentile", "chunking"),
            min_chars=require_integer(chunking, "min_chars", "chunking"),
            window_size=require_integer(chunking, "window_size", "chunking"),
            batch_size=require_integer(chunking, "batch_size", "chunking"),
            normalize_contextual_vectors=require_boolean(chunking, "normalize_contextual_vectors", "chunking"),
            device=optional_string_or_null(chunking, "device", "chunking"),
            local_files_only=require_boolean(chunking, "local_files_only", "chunking"),
        )
    except SemanticChunkConfigError as exc:
        raise SystemExit(f"Config error: {exc}") from exc
    return config


def load_generate_docx_job(path):
    config = read_json(path)
    if not isinstance(config, dict):
        raise SystemExit("Config error: root must be an object")
    require_exact_keys(
        config,
        {"schema_version", "pipeline", "source", "destination", "naming"},
        set(),
        "root",
    )
    if config.get("schema_version") != GENERATE_DOCX_JOB_SCHEMA_VERSION:
        raise SystemExit(f"Config error: schema_version must be {GENERATE_DOCX_JOB_SCHEMA_VERSION}")
    if require_string(config, "pipeline", "root") != PIPELINE_GENERATE_DOCX:
        raise SystemExit("Config error: pipeline must be generate-docx")

    source = require_object(config, "source", "root")
    destination = require_object(config, "destination", "root")
    naming = require_object(config, "naming", "root")
    require_exact_keys(
        naming,
        {"category_code", "subject_code", "title_slug", "language"},
        set(),
        "naming",
    )
    require_string(naming, "category_code", "naming", r"CAT[0-9]{3}")
    require_string(naming, "subject_code", "naming", r"SUB[0-9]{3}")
    require_string(naming, "title_slug", "naming", r"[A-Za-z0-9][A-Za-z0-9-]*")
    language = require_string(naming, "language", "naming")
    try:
        locale_spec(language)
    except ValueError as exc:
        raise SystemExit(f"Config error: naming.language is invalid: {exc}") from exc

    for section, context in ((source, "source"), (destination, "destination")):
        backend = storage_backend(section, context)
        expected = {"backend", "root_dir", "subject_dir"} if backend == "local" else {
            "backend", "bucket", "prefix", "subject_dir", "url_base"
        }
        require_exact_keys(section, expected, set(), context)
        validate_subject_artifact_storage(section, context, language)
        if backend == "r2":
            prefix = require_string(section, "prefix", context)
            validate_safe_posix_prefix(prefix, f"{context}.prefix")
    if source["subject_dir"] != destination["subject_dir"]:
        raise SystemExit(
            "Config error: generate-docx source.subject_dir and destination.subject_dir must use the same "
            "language-qualified root"
        )
    return config
