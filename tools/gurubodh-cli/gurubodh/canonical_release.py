"""Foundational readiness validation for canonical prepared releases.

This module is intentionally independent of prep-subject orchestration.  Both
the prep workflow and derived-artifact readers depend on these persisted release
constants, never the other way around.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gurubodh.contracts import (
    ChapterStatus,
    PrepCheckpointState,
    PrepJobStatus,
    PublicationStatus,
    R2Client,
)
from gurubodh.errors import SourceValidationError
from gurubodh.storage import R2StorageClient, is_r2, subject_artifact_object_key


LEGACY_CHECKPOINT_SCHEMA_VERSION = 1
CHECKPOINT_SCHEMA_VERSION = 2
CHECKPOINT_CONTRACT_VERSION = 2
RUN_STATE_RELATIVE_DIR = Path("run_state") / "prep-subject"
JOB_STATE_RELATIVE_PATH = RUN_STATE_RELATIVE_DIR / "job-state.json"


def read_checkpoint_state(path: Path) -> PrepCheckpointState:
    """Load a prep checkpoint into its typed runtime representation."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceValidationError(
            f"Prep-subject job state is missing or malformed: {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SourceValidationError(
            f"Prep-subject job state must be a JSON object: {path}"
        )
    try:
        return PrepCheckpointState.from_payload(value)
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceValidationError(
            f"Prep-subject job state is malformed: {path}: {exc}"
        ) from exc


def validate_canonical_release_gate(
    config: dict[str, Any],
    source_subject: Path,
    candidate_manifest: dict[str, Any],
    *,
    command_name: str,
    r2_client: R2Client | None = None,
) -> None:
    """Require a completed, manifest-bound prep release for derived work."""
    source = config["source"]
    state_path = Path(source_subject) / JOB_STATE_RELATIVE_PATH
    if is_r2(source):
        client = r2_client or R2StorageClient.from_env()
        key = subject_artifact_object_key(source, JOB_STATE_RELATIVE_PATH)
        if not client.exists(source["bucket"], key):
            raise SourceValidationError(
                f"{command_name} requires a completed prep-subject job state; "
                "no checkpoint was found."
            )
        client.download_file(source["bucket"], key, state_path)
    elif not state_path.is_file():
        raise SourceValidationError(
            f"{command_name} requires a completed prep-subject job state; "
            "no checkpoint was found."
        )

    state = read_checkpoint_state(state_path)
    if (
        state.get("schema_version")
        not in {LEGACY_CHECKPOINT_SCHEMA_VERSION, CHECKPOINT_SCHEMA_VERSION}
        or state.status is not PrepJobStatus.SUCCEEDED
    ):
        raise SourceValidationError(
            f"{command_name} refuses prepared content while the latest "
            "prep-subject job is not succeeded. Use gurubodh prep-subject "
            "--resume to complete or recover the preparation job first."
        )
    publication = state.get("publication") or {}
    if state.publication_status is not PublicationStatus.SUCCEEDED:
        raise SourceValidationError(
            f"{command_name} refuses prepared content while the latest "
            "prep-subject publication is not succeeded."
        )
    canonical = publication.get("canonical_manifest") or {}
    if canonical.get("sha256") != candidate_manifest.get("sha256"):
        raise SourceValidationError(
            f"{command_name} refuses the candidate manifest because it does "
            "not match the completed prep-subject checkpoint."
        )
    checkpoint_chapters = state.get("chapters")
    if not isinstance(checkpoint_chapters, list) or any(
        chapter.get("state") != ChapterStatus.SUCCEEDED.value
        for chapter in checkpoint_chapters
    ):
        raise SourceValidationError(
            f"{command_name} requires every completed checkpoint chapter to be succeeded."
        )
    expected_numbers = [
        chapter.get("chapter_number") for chapter in checkpoint_chapters
    ]
    manifest_numbers = [
        chapter.get("generated_chapter_number")
        for chapter in candidate_manifest.get("chapters", [])
    ]
    if (
        expected_numbers != manifest_numbers
        or canonical.get("chapter_numbers") != expected_numbers
    ):
        raise SourceValidationError(
            f"{command_name} refuses the candidate manifest because its "
            "chapters do not match the completed checkpoint set."
        )
    checkpoint_keys = {
        chapter["chapter_number"]: (chapter.get("proofreading") or {}).get(
            "canonical_content_key"
        )
        for chapter in checkpoint_chapters
    }
    if any(
        checkpoint_keys.get(chapter["generated_chapter_number"])
        != chapter.get("content_key")
        for chapter in candidate_manifest["chapters"]
    ):
        raise SourceValidationError(
            f"{command_name} refuses the candidate manifest because its "
            "chapter identities do not match the completed checkpoint."
        )
