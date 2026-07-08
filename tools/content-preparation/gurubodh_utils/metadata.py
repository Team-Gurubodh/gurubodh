import re

from gurubodh_utils.constants import CHAPTER_METADATA_SCHEMA_VERSION
from gurubodh_utils.naming import version_label
from gurubodh_utils.storage import destination_artifact_reference, source_reference


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
