import hashlib
import re
import unicodedata

from gurubodh.constants import CHAPTER_METADATA_SCHEMA_VERSION
from gurubodh.naming import version_label
from gurubodh.storage import destination_artifact_reference, source_reference

SUMMARY_TAG_MARKER = "उपसंहार"
SUMMARY_CHAPTER_TAGS = ["summary_chapter", SUMMARY_TAG_MARKER]


def chapter_storage_references(config, file_names):
    return {
        "source": source_reference(config),
        "artifacts": {
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
        },
    }


def text_stats(text):
    paragraphs = [part for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]
    return {
        "word_count": len(re.findall(r"\S+", text)),
        "character_count": len(text),
        "paragraph_count": len(paragraphs),
    }


def text_artifact_integrity(text):
    artifact_bytes = (text + "\n").encode("utf-8")
    return {
        "artifacts": {
            "text": {
                "algorithm": "sha256",
                "encoding": "UTF-8",
                "line_endings": "LF",
                "scope": "artifact-bytes",
                "value": hashlib.sha256(artifact_bytes).hexdigest(),
            }
        }
    }


def summary_chapter_markers(config):
    defaults = config.get("metadata_defaults", {})
    return defaults.get("summary_chapter_markers", [])


def automated_tags(text, summary_markers=None):
    normalized_text = unicodedata.normalize("NFC", text)
    markers = [] if summary_markers is None else summary_markers
    normalized_markers = [unicodedata.normalize("NFC", marker) for marker in markers]
    if any(marker in normalized_text for marker in normalized_markers):
        return list(SUMMARY_CHAPTER_TAGS)
    return []


def build_chapter_metadata(
    config,
    chapter_number,
    file_names,
    chapter_text_value,
    converter_counts,
    created_at,
    entry_point,
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
        "files": {
            "metadata_filename": file_names["metadata"],
            "text_filename": file_names["text"],
            "msword_filename": file_names["msword"],
        },
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
        "integrity": text_artifact_integrity(chapter_text_value),
        "content_stats": text_stats(chapter_text_value),
        "content": {
            "title": None,
            "summary": None,
            "automated_tags": automated_tags(
                chapter_text_value,
                summary_chapter_markers(config),
            ),
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
