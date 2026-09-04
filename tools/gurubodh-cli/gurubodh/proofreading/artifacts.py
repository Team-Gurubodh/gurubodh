"""Canonical chapter proofreading artifacts and manifest construction."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

from gurubodh.constants import ENTRY_POINT_PREP_SUBJECT
from gurubodh.content_identity import build_content_identity
from gurubodh.contracts import (
    CheckpointArtifactRecord,
    PrepSubjectJob,
    Proofreader,
    ProofreadingOutcome,
    ProofreadingStatus,
)
from gurubodh.locales import LocaleSpec
from gurubodh.metadata import build_chapter_metadata
from gurubodh.naming import chapter_output_filename
from gurubodh.proofreading.errors import ProofreadingError
from gurubodh.proofreading.settings import ProofreadingSettings
from gurubodh.proofreading.text_comparison import word_level_diff
from gurubodh.schema_validation import write_json_artifact
from gurubodh.storage import destination_artifact_reference
from gurubodh.time_utils import utc_now


PROOFREADING_OUTPUT_DIR = "proofreading"
PROOFREADING_MANIFEST_FILENAME = "proofreading_manifest.json"
PROOFREADING_SCHEMA_VERSION = 2


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (text if text.endswith("\n") else text + "\n").encode("utf-8")
    )


def _proofread_artifact_paths(
    proofreading_dir: Path, text_filename: str
) -> dict[str, Path]:
    stem = Path(text_filename).stem
    return {
        "diff": proofreading_dir / f"{stem}.proofread.diff.txt",
        "json": proofreading_dir / f"{stem}.proofread.json",
    }


def _artifact_integrity(path: Path) -> dict[str, Any]:
    return {
        "algorithm": "sha256",
        "encoding": "UTF-8",
        "line_endings": "LF",
        "scope": "artifact-bytes",
        "value": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _canonical_text_filename(unmodified_source_filename: str) -> str:
    suffix = "_unmodified_source.txt"
    if not unmodified_source_filename.endswith(suffix):
        raise ProofreadingError(
            "invalid_unmodified_source_artifact",
            f"Unmodified source artifact has an unexpected filename: {unmodified_source_filename}",
        )
    return f"{unmodified_source_filename.removesuffix(suffix)}.txt"


def _chapter_file_names(
    config: PrepSubjectJob, chapter_number: int
) -> dict[str, Any]:
    text_name = chapter_output_filename(config, chapter_number, ".txt")
    metadata_name = chapter_output_filename(config, chapter_number, ".json")
    return {
        "metadata": metadata_name,
        "text": text_name,
        "metadata_relative_path": Path("chapters")
        / "text_and_metadata"
        / metadata_name,
        "text_relative_path": Path("chapters")
        / "text_and_metadata"
        / text_name,
    }


def _canonical_text_value(corrected_text: str) -> str:
    """Normalize canonical artifact line endings without identity normalization."""
    return corrected_text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def _validate_provider_locale(
    proofreader: Proofreader, locale: LocaleSpec
) -> None:
    """Reject locale-aware providers whose selected prompt locale disagrees."""
    missing = object()
    selected = getattr(proofreader, "locale", missing)
    if selected is missing:
        # Lightweight fakes need only implement the narrow Proofreader protocol.
        return
    if not isinstance(selected, LocaleSpec) or selected.language != locale.language:
        selected_language = (
            selected.language if isinstance(selected, LocaleSpec) else "none"
        )
        raise ProofreadingError(
            "locale_mismatch",
            f"Selected proofreading language {selected_language!r} does not match chapter metadata language {locale.language!r}.",
        )


def write_canonical_chapter_artifacts(
    config: PrepSubjectJob,
    paths: dict[str, Path],
    chapter_number: int,
    unmodified_source_path: Path,
    *,
    proofreader: Proofreader,
    converter_counts: dict[str, int] | None = None,
    entry_point: str = ENTRY_POINT_PREP_SUBJECT,
    progress: Callable[[str], None] | None = None,
) -> ProofreadingOutcome:
    """Proofread one staged chapter and write its complete artifact set.

    The caller owns checkpointing. This returns only bounded provenance and
    artifact checksums; neither source nor corrected text can enter checkpoints
    or audit records through the typed outcome.
    """
    settings = config.proofreading_settings
    source_bytes = unmodified_source_path.read_bytes()
    source_text = source_bytes.decode("utf-8")
    locale = config.locale
    source_identity = build_content_identity(
        config["naming"]["category_code"],
        config["naming"]["subject_code"],
        locale.language,
        source_text,
    )
    text_filename = _canonical_text_filename(unmodified_source_path.name)
    file_names = _chapter_file_names(config, chapter_number)
    if text_filename != file_names["text"]:
        raise ProofreadingError(
            "invalid_unmodified_source_artifact",
            f"Unmodified source filename does not match chapter {chapter_number:03d}: {unmodified_source_path.name}",
        )

    _validate_provider_locale(proofreader, locale)
    response = proofreader.proofread(source_text, progress=progress)
    canonical_text = _canonical_text_value(response["corrected_text"])
    canonical_text_path = paths["text_and_metadata"] / text_filename
    metadata_path = paths["text_and_metadata"] / file_names["metadata"]
    _write_text(canonical_text_path, canonical_text)
    metadata = build_chapter_metadata(
        config,
        chapter_number,
        file_names,
        canonical_text,
        converter_counts or {},
        utc_now(),
        entry_point,
    )
    write_json_artifact(metadata_path, metadata, "chapter metadata")

    canonical_artifact_text = canonical_text_path.read_text(encoding="utf-8")
    rendered_diff, diff_summary = word_level_diff(
        source_text, canonical_artifact_text
    )
    proof_dir = paths["proofreading"]
    proof_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths = _proofread_artifact_paths(proof_dir, text_filename)
    _write_text(
        artifact_paths["diff"],
        "Word-level proof-reading diff. [-removed-] {+added+}\n\n" + rendered_diff,
    )
    relative_dir = Path("chapters") / PROOFREADING_OUTPUT_DIR
    canonical_integrity = _artifact_integrity(canonical_text_path)
    payload = {
        "schema_version": PROOFREADING_SCHEMA_VERSION,
        "status": "succeeded",
        "created_at": utc_now(),
        "provider": {"name": settings.provider, "model": settings.model},
        "proofreading_locale": locale.proofreading_provenance(),
        "unmodified_source": {
            "text_artifact": destination_artifact_reference(
                config,
                Path("chapters")
                / "unmodified_source_text"
                / unmodified_source_path.name,
            ),
            "text_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "content_identity": source_identity,
        },
        "canonical_corrected": {
            "text_artifact": metadata["storage"]["artifacts"]["text"],
            "text_sha256": canonical_integrity["value"],
            "content_identity": metadata["content_identity"],
        },
        "diff_artifact": destination_artifact_reference(
            config, relative_dir / artifact_paths["diff"].name
        ),
        "integrity": {
            "unmodified_source": _artifact_integrity(unmodified_source_path),
            "canonical_corrected": canonical_integrity,
            "diff": _artifact_integrity(artifact_paths["diff"]),
        },
        "local_diff_summary": diff_summary,
        "gemini_edits": response["edits"],
        "request": {
            **{
                key: response[key]
                for key in (
                    "estimated_input_tokens",
                    "attempts",
                    "throttle_seconds",
                    "usage",
                )
            },
            "diagnostics": response.get("request_diagnostics"),
        },
    }
    write_json_artifact(
        artifact_paths["json"], payload, "chapter proofreading"
    )
    artifact_files = [
        unmodified_source_path,
        canonical_text_path,
        metadata_path,
        artifact_paths["diff"],
        artifact_paths["json"],
    ]
    return ProofreadingOutcome(
        chapter_number=f"{chapter_number:03d}",
        status=ProofreadingStatus.SUCCEEDED,
        correction_count=len(response["edits"]),
        request_attempts=response["attempts"],
        successful_request_attempts=response.get(
            "successful_request_attempts", response["attempts"]
        ),
        request_diagnostics=response.get("request_diagnostics"),
        local_diff_summary=diff_summary,
        unmodified_source_content_key=source_identity["content_key"],
        canonical_content_key=metadata["content_identity"]["content_key"],
        artifacts={
            "unmodified_source": destination_artifact_reference(
                config,
                Path("chapters")
                / "unmodified_source_text"
                / unmodified_source_path.name,
            ),
            "canonical_text": metadata["storage"]["artifacts"]["text"],
            "canonical_metadata": metadata["storage"]["artifacts"]["metadata"],
            **{
                key: destination_artifact_reference(
                    config, relative_dir / path.name
                )
                for key, path in artifact_paths.items()
            },
        },
        checkpoint_artifacts=tuple(
            CheckpointArtifactRecord(
                path=str(path.relative_to(paths["subject"])),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
            for path in artifact_files
            if path.is_file()
        ),
    )


def write_proofreading_manifest(
    paths: dict[str, Path],
    settings: ProofreadingSettings,
    chapters: list[dict[str, Any]],
    locale: LocaleSpec,
) -> Path:
    """Write the final canonical proofreading provenance manifest."""
    manifest = {
        "schema_version": PROOFREADING_SCHEMA_VERSION,
        "provider": {"name": settings.provider, "model": settings.model},
        "proofreading_locale": locale.proofreading_provenance(),
        "counts": {"succeeded": len(chapters), "failed": 0, "skipped": 0},
        "chapters": [
            {
                key: value
                for key, value in chapter.items()
                if key != "checkpoint_artifacts"
            }
            for chapter in chapters
        ],
    }
    manifest_path = paths["proofreading"] / PROOFREADING_MANIFEST_FILENAME
    return write_json_artifact(
        manifest_path, manifest, "proofreading manifest"
    )
