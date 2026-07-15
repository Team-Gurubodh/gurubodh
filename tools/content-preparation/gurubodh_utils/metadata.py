import hashlib
import re

from gurubodh_utils.constants import (
    CHAPTER_METADATA_SCHEMA_VERSION,
    DEFAULT_FORMATTING_CONFIG,
)
from gurubodh_utils.naming import version_label
from gurubodh_utils.storage import destination_artifact_reference, source_reference


def chapter_storage_references(config, file_names):
    artifacts = {
        "metadata": destination_artifact_reference(
            config,
            file_names["metadata_relative_path"],
        ),
        "text": destination_artifact_reference(
            config,
            file_names["text_relative_path"],
        ),
        "msword": destination_artifact_reference(
            config,
            file_names["msword_relative_path"],
        ),
        "full_subject_msword": destination_artifact_reference(
            config,
            file_names["full_msword_relative_path"],
        ),
        "full_subject_text": destination_artifact_reference(
            config,
            file_names["full_text_relative_path"],
        ),
    }
    if file_names.get("formatted_json_relative_path"):
        artifacts["formatted_json"] = destination_artifact_reference(
            config,
            file_names["formatted_json_relative_path"],
        )
    if file_names.get("formatted_markdown_relative_path"):
        artifacts["formatted_markdown"] = destination_artifact_reference(
            config,
            file_names["formatted_markdown_relative_path"],
        )

    return {
        "source": source_reference(config),
        "artifacts": artifacts,
    }


def text_stats(text):
    paragraphs = [part for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]
    return {
        "word_count": len(re.findall(r"\S+", text)),
        "character_count": len(text),
        "paragraph_count": len(paragraphs),
    }


def artifact_bytes_integrity(artifact_bytes):
    return {
        "algorithm": "sha256",
        "encoding": "UTF-8",
        "line_endings": "LF",
        "scope": "artifact-bytes",
        "value": hashlib.sha256(artifact_bytes).hexdigest(),
    }


def artifact_path_integrity(path):
    return artifact_bytes_integrity(path.read_bytes())


def source_text_sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def text_artifact_integrity(text):
    return {
        "artifacts": {
            "text": artifact_bytes_integrity((text + "\n").encode("utf-8")),
        }
    }


def formatting_status_metadata(config, formatting_result, chapter_text_value):
    formatting_config = dict(DEFAULT_FORMATTING_CONFIG)
    formatting_config.update(config.get("formatting", {}))
    status = "disabled"
    warning = None
    if formatting_result:
        status = formatting_result.get("status", status)
        warning = formatting_result.get("warning")

    model_used = (
        formatting_config.get("model")
        if status in {"formatted", "skipped-unchanged"}
        else None
    )
    if formatting_result and formatting_result.get("model_used") is not None:
        model_used = formatting_result["model_used"]

    token_usage = {}
    if formatting_result and isinstance(formatting_result.get("token_usage"), dict):
        token_usage = formatting_result["token_usage"]

    return {
        "enabled": bool(formatting_config.get("enabled")),
        "provider": formatting_config.get("provider"),
        "model": formatting_config.get("model"),
        "fallback_model": formatting_config.get("fallback_model"),
        "model_used": model_used,
        "status": status,
        "warning": warning,
        "attempt_count": formatting_result.get("attempt_count", 0)
        if formatting_result
        else 0,
        "retry_count": formatting_result.get("retry_count", 0)
        if formatting_result
        else 0,
        "throttle_sleep_seconds": formatting_result.get("throttle_sleep_seconds", 0)
        if formatting_result
        else 0,
        "source_text_sha256": source_text_sha256(chapter_text_value)
        if formatting_config.get("enabled")
        else None,
        "token_usage": {
            "completion_tokens": token_usage.get("completion_tokens"),
            "prompt_tokens": token_usage.get("prompt_tokens"),
            "total_tokens": token_usage.get("total_tokens"),
        },
    }


def chapter_files(file_names):
    files = {
        "metadata_filename": file_names["metadata"],
        "text_filename": file_names["text"],
        "msword_filename": file_names["msword"],
    }
    if file_names.get("formatted_json"):
        files["formatted_json_filename"] = file_names["formatted_json"]
    if file_names.get("formatted_markdown"):
        files["formatted_markdown_filename"] = file_names["formatted_markdown"]
    return files


def chapter_integrity(chapter_text_value, file_names):
    integrity = text_artifact_integrity(chapter_text_value)
    artifacts = integrity["artifacts"]
    if file_names.get("formatted_json_path"):
        artifacts["formatted_json"] = artifact_path_integrity(
            file_names["formatted_json_path"]
        )
    if file_names.get("formatted_markdown_path"):
        artifacts["formatted_markdown"] = artifact_path_integrity(
            file_names["formatted_markdown_path"]
        )
    return integrity


def build_chapter_metadata(
    config,
    chapter_number,
    file_names,
    chapter_text_value,
    converter_counts,
    created_at,
    entry_point,
    formatting_result=None,
):
    defaults = config.get("metadata_defaults", {})
    return {
        "schema_version": CHAPTER_METADATA_SCHEMA_VERSION,
        "document": {
            "category_code": config["naming"]["category_code"],
            "subject_code": config["naming"]["subject_code"],
            "title_slug": config["naming"]["title_slug"],
            "chapter_number": f"{chapter_number:03d}",
            "version": version_label(config),
            "language": defaults.get("language", "hi-Deva"),
        },
        "files": chapter_files(file_names),
        "storage": chapter_storage_references(config, file_names),
        "processing": {
            "pipeline": config["pipeline"],
            "entry_point": entry_point,
        },
        "conversion": {
            "created_at": created_at,
            "source_font_encoding": config["source"]["font_encoding"],
            "source_file_format": config["source"]["file_format"],
            "output_text_encoding": defaults.get("output_text_encoding", "UTF-8"),
            "converter_counts": converter_counts,
        },
        "integrity": chapter_integrity(chapter_text_value, file_names),
        "formatting": formatting_status_metadata(config, formatting_result, chapter_text_value),
        "content_stats": text_stats(chapter_text_value),
        "content": {
            "title": None,
            "summary": None,
            "automated_tags": [],
            "scriptural_terms": [],
        },
        "annotations": {
            "expert_descriptors": {},
            "user_tags": {
                "labels": [],
                "custom_notes": None,
            },
        },
    }
