import json
import re
from pathlib import PurePosixPath

from gurubodh.ml.semantic_chunking.config import SemanticChunkConfig, SemanticChunkConfigError
from gurubodh.locales import locale_spec
from gurubodh.proofreading import ProofreadingSettings
from gurubodh.schema_validation import validate_job


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


def chapter_split_regex_flags(chapter_split):
    compiled_flags = 0
    for flag in chapter_split.get("flags", []):
        compiled_flags |= REGEX_FLAG_VALUES[flag]
    return compiled_flags


def prepare_chapter_split(chapter_split):
    if chapter_split["pattern_type"] == "literal":
        return

    flags = chapter_split_regex_flags(chapter_split)
    try:
        chapter_split["_compiled_pattern"] = re.compile(chapter_split["pattern"], flags)
    except re.error as exc:
        raise SystemExit(f"Config error: chapter_split.pattern is not a valid regex: {exc}") from exc


def normalized_source_font_encoding(config):
    return config["source"]["font_encoding"].strip().lower()


def source_is_unicode(config):
    return normalized_source_font_encoding(config) == "unicode"


def source_is_legacy(config):
    return normalized_source_font_encoding(config) == "aps"


def storage_backend(section, context):
    return section.get("backend", "local")


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
    validate_language_partition(destination["subject_dir"], language, "destination")


def validate_subject_artifact_storage(section, context, language):
    validate_language_partition(section["subject_dir"], language, context)


def validate_metadata_defaults(config):
    metadata_defaults = config["metadata_defaults"]
    language = metadata_defaults["language"]
    try:
        locale = locale_spec(language)
    except ValueError as exc:
        raise SystemExit(f"Config error: metadata_defaults.language is invalid: {exc}") from exc
    source_script = metadata_defaults["source_script"]
    if source_script != locale.source_script:
        raise SystemExit(
            f"Config error: metadata_defaults.source_script must be {locale.source_script!r} for {language}"
        )
    output_text_encoding = metadata_defaults["output_text_encoding"]
    if output_text_encoding != locale.output_text_encoding:
        raise SystemExit(
            f"Config error: metadata_defaults.output_text_encoding must be {locale.output_text_encoding!r} for {language}"
        )
    return locale


def validate_pipeline_matches_source(config, expected_pipeline=None):
    pipeline = config["pipeline"]
    if expected_pipeline and pipeline != expected_pipeline:
        raise SystemExit(
            f"Config error: pipeline {pipeline!r} cannot be processed by {expected_pipeline!r}"
        )


def proofreading_config(config):
    value = config.get("proofreading")
    if not isinstance(value, dict):
        raise SystemExit("Config error: proofreading is required and must be an object")
    settings = ProofreadingSettings.from_config(value)
    if settings.max_retry_delay_seconds < settings.initial_retry_delay_seconds:
        raise SystemExit("Config error: proofreading.max_retry_delay_seconds must be at least initial_retry_delay_seconds")
    return settings


def load_prep_subject_job(path):
    config = read_json(path)
    validate_job(config, "prep-subject", path)
    destination = config["destination"]
    chapter_split = config["chapter_split"]
    locale = validate_metadata_defaults(config)
    validate_destination_storage(destination, locale.language)
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
    validate_job(config, "generate-chunks", path)
    source = config["source"]
    destination = config["destination"]
    naming = config["naming"]
    chunking = config["chunking"]
    language = naming["language"]
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

    try:
        config["_semantic_chunk_config"] = SemanticChunkConfig.from_env(
            provider=chunking["provider"],
            model_name=chunking["model"],
            model_revision=chunking["model_revision"],
            threshold_percentile=chunking["threshold_percentile"],
            min_chars=chunking["min_chars"],
            window_size=chunking["window_size"],
            batch_size=chunking["batch_size"],
            normalize_contextual_vectors=chunking["normalize_contextual_vectors"],
            device=chunking["device"],
            local_files_only=chunking["local_files_only"],
        )
    except SemanticChunkConfigError as exc:
        raise SystemExit(f"Config error: {exc}") from exc
    return config


def load_generate_docx_job(path):
    config = read_json(path)
    validate_job(config, "generate-docx", path)
    source = config["source"]
    destination = config["destination"]
    naming = config["naming"]
    language = naming["language"]
    try:
        locale_spec(language)
    except ValueError as exc:
        raise SystemExit(f"Config error: naming.language is invalid: {exc}") from exc

    for section, context in ((source, "source"), (destination, "destination")):
        backend = storage_backend(section, context)
        validate_subject_artifact_storage(section, context, language)
        if backend == "r2":
            validate_safe_posix_prefix(section["prefix"], f"{context}.prefix")
    if source["subject_dir"] != destination["subject_dir"]:
        raise SystemExit(
            "Config error: generate-docx source.subject_dir and destination.subject_dir must use the same "
            "language-qualified root"
        )
    return config
