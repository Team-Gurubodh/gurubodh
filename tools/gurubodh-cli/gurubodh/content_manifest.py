"""Generated manifests for the currently prepared chapter content set."""

import json
from pathlib import Path

from gurubodh.content_identity import validate_content_identity


CHAPTER_CONTENT_MANIFEST_FILENAME = "chapter_content_manifest.json"


def build_chapter_content_manifest(config, text_and_metadata_dir: Path) -> dict:
    chapters = []
    for metadata_path in sorted(text_and_metadata_dir.glob("*.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        document = metadata["document"]
        text_path = text_and_metadata_dir / metadata["files"]["text_filename"]
        if not text_path.is_file():
            raise ValueError(f"Content manifest cannot find chapter text for {metadata_path}")
        identity = validate_content_identity(
            metadata.get("content_identity"),
            document["category_code"],
            document["subject_code"],
            document["language"],
            text_path.read_text(encoding="utf-8"),
        )
        artifacts = metadata["storage"]["artifacts"]
        chapters.append({
            "generated_chapter_number": document["chapter_number"],
            "content_key": identity["content_key"],
            "normalized_content_sha256": identity["normalized_content_sha256"],
            "metadata_artifact": artifacts["metadata"],
            "text_artifact": artifacts["text"],
        })
    chapters.sort(key=lambda chapter: (chapter["generated_chapter_number"], json.dumps(chapter["metadata_artifact"], sort_keys=True)))
    return {
        "schema_version": 1,
        "identity_contract_version": 1,
        "subject": {
            "category_code": config["naming"]["category_code"],
            "subject_code": config["naming"]["subject_code"],
            "language": config["metadata_defaults"]["language"],
        },
        "chapters": chapters,
    }


def write_chapter_content_manifest(config, paths) -> Path:
    path = paths["text_and_metadata"].parent / CHAPTER_CONTENT_MANIFEST_FILENAME
    payload = build_chapter_content_manifest(config, paths["text_and_metadata"])
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
