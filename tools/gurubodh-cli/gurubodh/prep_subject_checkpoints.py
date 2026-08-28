"""Durable, resumable chapter checkpoints for ``gurubodh prep-subject``.

The canonical prepared-content tree is intentionally not used as a work area.
All source snapshots and per-chapter proof-reading artifacts are assembled in a
job-specific workspace, and only a fully validated chapter set is promoted.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import time
import uuid
from typing import Any, Callable

from gurubodh.content_identity import build_content_identity
from gurubodh.content_manifest import write_chapter_content_manifest
from gurubodh.locales import locale_spec
from gurubodh.legacy.font_detection import validate_supported_source_fonts
from gurubodh.naming import chapter_output_filename
from gurubodh.paths import destination_paths_for_subject, ensure_job_dirs
from gurubodh.pipelines.common import validate_and_split
from gurubodh.proofreading import (
    GeminiProofreader,
    ProofreadingError,
    proofread_single_chapter_artifacts,
    write_proofreading_manifest,
)
from gurubodh.storage import (
    CANONICAL_ARTIFACT_FILES,
    PREP_ARTIFACT_DIRS,
    R2StorageClient,
    cleanup_local_legacy_full_subject,
    cleanup_r2_legacy_full_subject,
    destination_artifact_reference,
    destination_object_key,
    invalidate_local_semantic_artifacts,
    invalidate_local_chapter_docx_artifacts,
    invalidate_r2_chapter_docx_artifacts,
    invalidate_r2_semantic_artifacts,
    is_local,
    is_r2,
    materialize_source,
    preflight_relative_paths,
    subject_artifact_object_key,
    subject_artifact_prefix,
    upload_r2_file,
)
from gurubodh.time_utils import timestamp_for_filename, utc_now


CHECKPOINT_SCHEMA_VERSION = 1
CHECKPOINT_CONTRACT_VERSION = 2
RUN_STATE_RELATIVE_DIR = Path("run_state") / "prep-subject"
JOB_STATE_RELATIVE_PATH = RUN_STATE_RELATIVE_DIR / "job-state.json"
WORK_RELATIVE_DIR = Path(".work") / "prep-subject"
PREP_REPORT_RELATIVE_DIR = Path("run_reports") / "prep-subject"
LEASE_SECONDS = 120
INFRASTRUCTURE_FAILURE_CIRCUIT_BREAKER = 2
R2_UPLOAD_BREAKDOWN_DEFINITIONS = {
    "checkpoint_source_snapshots": "Initial retained source snapshots committed with the chapter plan.",
    "checkpoint_chapter_artifacts": "New canonical text, metadata, diff, and provenance artifacts from successful chapters.",
    "checkpoint_state_commits": "Job-state JSON commits for checkpoint, publication, workspace, or advisory-lease transitions.",
    "checkpoint_state_archives": "Prior job-state archives created by --overwrite.",
    "canonical_publication_artifacts": "Final canonical prep artifacts and readiness manifests published from the workspace.",
}


def _attempt_counters() -> dict[str, int]:
    return {"attempts_total": 0, "attempts_succeeded": 0, "attempts_failed": 0}


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{label} is missing or malformed: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"{label} must be a JSON object: {path}")
    return value


def _safe_error(exc: BaseException) -> dict[str, str]:
    code = getattr(exc, "code", "unexpected_error")
    message = " ".join(str(exc).split())[:500] or type(exc).__name__
    return {"code": str(code)[:80], "message": message}


def _safe_config_inputs(config: dict[str, Any]) -> dict[str, Any]:
    """Return only output-affecting inputs; operational pacing is excluded."""
    settings = config["_proofreading_config"]
    locale = config.get("_locale") or locale_spec(config["metadata_defaults"]["language"])
    return {
        "pipeline": config["pipeline"],
        "chapter_split": {
            key: value
            for key, value in config["chapter_split"].items()
            if not key.startswith("_")
        },
        "naming": dict(config["naming"]),
        "metadata_defaults": dict(config.get("metadata_defaults", {})),
        "proofreading": {
            "provider": settings.provider,
            "model": settings.model,
            "max_output_tokens": settings.max_output_tokens,
            "max_input_characters": settings.max_input_characters,
            "response_schema_version": 1,
            "locale": locale.proofreading_provenance(),
        },
        "checkpoint_contract_version": CHECKPOINT_CONTRACT_VERSION,
    }


def compatibility_record(config: dict[str, Any], source_sha256: str) -> dict[str, Any]:
    inputs = _safe_config_inputs(config)
    payload = {
        "source_docx_sha256": source_sha256,
        "output_affecting_inputs": inputs,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return payload | {"fingerprint": hashlib.sha256(encoded).hexdigest()}


def _counts(chapters: list[dict[str, Any]]) -> dict[str, int]:
    return {
        state: sum(1 for chapter in chapters if chapter.get("state") == state)
        for state in ("succeeded", "failed", "pending")
    }


def _workspace_relative_path(job_id: str) -> Path:
    return WORK_RELATIVE_DIR / job_id


class PrepCheckpointManager:
    """Persist job state and workspace to local storage or an R2-compatible API."""

    def __init__(self, config: dict[str, Any], resume: bool, overwrite: bool, r2_client=None):
        self.config = config
        self.resume = resume
        self.overwrite = overwrite
        self.destination = config["destination"]
        self.r2_client = r2_client
        self.state: dict[str, Any] | None = None
        self.metrics = {
            "gemini_generate_content_requests": {
                **_attempt_counters(),
            },
            "r2_object_upload_requests": (
                {
                    **_attempt_counters(),
                    "breakdown": {
                        category: _attempt_counters()
                        for category in R2_UPLOAD_BREAKDOWN_DEFINITIONS
                    },
                }
                if is_r2(self.destination)
                else None
            ),
        }
        self.owner_id = str(uuid.uuid4())
        self.local_lock_path: Path | None = None
        self.local_lock_created = False
        self.workspace_temp_dir: tempfile.TemporaryDirectory | None = None
        self.source_temp_dir: tempfile.TemporaryDirectory | None = None
        if is_local(self.destination):
            self.subject_dir = Path(self.destination["root_dir"]).expanduser() / self.destination["subject_dir"]
            self.state_path = self.subject_dir / JOB_STATE_RELATIVE_PATH
            self.local_workspace_root = self.subject_dir
        else:
            self.workspace_temp_dir = tempfile.TemporaryDirectory(prefix="gurubodh-prep-checkpoint-")
            self.subject_dir = Path(self.workspace_temp_dir.name) / self.destination["subject_dir"]
            self.state_path = self.subject_dir / JOB_STATE_RELATIVE_PATH
            self.local_workspace_root = self.subject_dir

    @property
    def client(self):
        if self.r2_client is None:
            self.r2_client = R2StorageClient.from_env()
        return self.r2_client

    @property
    def is_r2(self) -> bool:
        return is_r2(self.destination)

    @property
    def job_id(self) -> str:
        if not self.state:
            raise RuntimeError("Checkpoint state is not initialized")
        return self.state["job_id"]

    @property
    def workspace_relative(self) -> Path:
        return _workspace_relative_path(self.job_id)

    @property
    def workspace_dir(self) -> Path:
        return self.local_workspace_root / self.workspace_relative

    @property
    def paths(self) -> dict[str, Path]:
        return destination_paths_for_subject(self.workspace_dir)

    def open(self) -> None:
        if is_local(self.destination):
            self.subject_dir.mkdir(parents=True, exist_ok=True)
            self._acquire_local_lock()
            if self.state_path.exists():
                self.state = _read_json(self.state_path, "Prep-subject job state")
            return
        state_key = destination_object_key(self.config, JOB_STATE_RELATIVE_PATH)
        if self.client.exists(self.destination["bucket"], state_key):
            self.client.download_file(self.destination["bucket"], state_key, self.state_path)
            self.state = _read_json(self.state_path, "Prep-subject job state")
            self._restore_r2_workspace()

    def _acquire_local_lock(self) -> None:
        self.local_lock_path = self.subject_dir / RUN_STATE_RELATIVE_DIR / "job.lock"
        self.local_lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.local_lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            if time.time() - self.local_lock_path.stat().st_mtime > LEASE_SECONDS:
                self.local_lock_path.unlink(missing_ok=True)
                return self._acquire_local_lock()
            raise SystemExit(
                f"Another prep-subject writer appears active for {self.subject_dir}; the local advisory lock is not "
                "reliable mutual exclusion. Wait for it to finish, or use --resume after an interrupted writer's "
                "advisory lock has expired."
            ) from exc
        os.write(descriptor, self.owner_id.encode("utf-8"))
        os.close(descriptor)
        self.local_lock_created = True

    def _restore_r2_workspace(self) -> None:
        if not self.state:
            return
        prefix = subject_artifact_object_key(self.destination, self.workspace_relative) + "/"
        for key in self.client.list_keys(self.destination["bucket"], prefix):
            relative = PurePosixPath(key.removeprefix(subject_artifact_prefix(self.destination)))
            if relative.is_absolute() or ".." in relative.parts:
                raise SystemExit("Checkpoint workspace key escapes the destination subject prefix.")
            self.client.download_file(self.destination["bucket"], key, self.subject_dir / Path(*relative.parts))

    def _archive_prior_state(self) -> None:
        if not self.state:
            return
        archive_name = f"{timestamp_for_filename()}-{self.state.get('job_id', 'unknown')}-job-state.json"
        archive_relative = RUN_STATE_RELATIVE_DIR / "archive" / archive_name
        if is_local(self.destination):
            _write_json_atomically(self.subject_dir / archive_relative, self.state)
            workspace = self.workspace_dir
            if workspace.exists():
                shutil.rmtree(workspace)
            return
        archive_path = self.subject_dir / archive_relative
        _write_json_atomically(archive_path, self.state)
        self._upload_r2_file(
            archive_path,
            destination_object_key(self.config, archive_relative),
            category="checkpoint_state_archives",
        )
        self.client.delete_prefix(
            self.destination["bucket"],
            subject_artifact_object_key(self.destination, self.workspace_relative) + "/",
        )

    def _canonical_artifacts_exist(self) -> bool:
        if is_local(self.destination):
            return any(
                (self.subject_dir / relative).exists()
                for relative in preflight_relative_paths("prep-subject")
            )
        for relative in preflight_relative_paths("prep-subject"):
            key = destination_object_key(self.config, relative)
            if relative.suffix:
                if self.client.exists(self.destination["bucket"], key):
                    return True
            elif self.client.list_keys(self.destination["bucket"], key + "/"):
                return True
        return False

    def begin(self, source_sha256: str) -> str:
        compatibility = compatibility_record(self.config, source_sha256)
        if self.state:
            self._validate_loaded_state()
            if self.overwrite:
                self._archive_prior_state()
                self.state = None
            elif not self.resume:
                status = self.state.get("state")
                if status == "succeeded":
                    raise SystemExit(
                        "A completed prep-subject checkpoint already exists. Use --resume to confirm it is complete "
                        "or --overwrite to start a fresh job."
                    )
                raise SystemExit(
                    "An incomplete prep-subject checkpoint already exists. Re-run with --resume to continue it "
                    "or --overwrite to discard its staged workspace and start over."
                )
            elif self.state["compatibility"].get("fingerprint") != compatibility["fingerprint"]:
                raise SystemExit(
                    "The existing prep-subject checkpoint is incompatible with this source or output-affecting "
                    "configuration. Re-run with --overwrite; checkpoints from different inputs are never mixed."
                )
            elif self.state.get("state") == "succeeded":
                self.state["run"] = self.state.get("run", {}) | {
                    "run_id": str(uuid.uuid4()),
                    "last_started_at": utc_now(),
                }
                return "already_complete"
        elif self.resume:
            raise SystemExit("No prep-subject checkpoint exists to resume. Run without --resume to start a new job.")

        if self.state is None:
            if self._canonical_artifacts_exist() and not self.overwrite:
                raise SystemExit(
                    "Canonical prepared artifacts exist without a compatible checkpoint. Re-run with --overwrite "
                    "to create a fresh staged prep-subject job."
                )
            now = utc_now()
            job_id = str(uuid.uuid4())
            self.state = {
                "schema_version": CHECKPOINT_SCHEMA_VERSION,
                "job_id": job_id,
                "state": "running",
                "created_at": now,
                "updated_at": now,
                "run": {"run_id": str(uuid.uuid4()), "started_at": now, "last_started_at": now},
                "lease": {},
                "compatibility": compatibility,
                "chapters": [],
                "counts": {"succeeded": 0, "failed": 0, "pending": 0},
                "publication": {"state": "not_ready", "canonical_manifest": None},
                "run_reports": [],
                "workspace": {"relative_path": str(_workspace_relative_path(job_id)), "status": "active"},
                "failure": None,
                "preparation": None,
            }
        else:
            self.state["state"] = "running"
            self.state["run"] = self.state.get("run", {}) | {
                "run_id": str(uuid.uuid4()), "last_started_at": utc_now(),
            }
            self.state["failure"] = None
        self._claim_lease()
        self.persist()
        return "started"

    def _validate_loaded_state(self) -> None:
        if self.state.get("schema_version") != CHECKPOINT_SCHEMA_VERSION or not isinstance(self.state.get("job_id"), str):
            raise SystemExit("Unsupported or malformed prep-subject checkpoint. Re-run with --overwrite.")
        stored_contract = (
            self.state.get("compatibility", {})
            .get("output_affecting_inputs", {})
            .get("checkpoint_contract_version")
        )
        if stored_contract != CHECKPOINT_CONTRACT_VERSION and not self.overwrite:
            raise SystemExit(
                "The existing prep-subject checkpoint uses an incompatible artifact contract. "
                "It cannot be resumed with the five-file text-only checkpoint; re-run with --overwrite."
            )
        lease = self.state.get("lease") or {}
        if lease.get("active") and lease.get("owner_id") != self.owner_id and lease.get("expires_at_epoch", 0) > time.time():
            raise SystemExit(
                "Another prep-subject process appears to hold an active destination advisory lease. This is not "
                "reliable mutual exclusion; wait for it to finish or resume after its advisory lease expires."
            )

    def _claim_lease(self) -> None:
        now = time.time()
        self.state["lease"] = {
            "owner_id": self.owner_id,
            "active": True,
            "heartbeat_at": utc_now(),
            "expires_at_epoch": int(now + LEASE_SECONDS),
        }

    def heartbeat(self) -> None:
        self._claim_lease()
        if self.local_lock_created and self.local_lock_path:
            os.utime(self.local_lock_path, None)
        # R2 heartbeats are deliberately in-memory only. The lease is advisory,
        # and a progress signal must not become a workspace scan or state commit.

    def persist(
        self,
        checkpoint_artifacts: list[Path] | None = None,
        checkpoint_artifact_category: str | None = None,
        count_r2_uploads: bool = True,
    ) -> None:
        if not self.state:
            return
        self.state["updated_at"] = utc_now()
        self.state["counts"] = _counts(self.state.get("chapters", []))
        _write_json_atomically(self.state_path, self.state)
        if self.is_r2:
            for path in checkpoint_artifacts or []:
                relative = path.relative_to(self.subject_dir)
                self._upload_r2_file(
                    path,
                    destination_object_key(self.config, relative),
                    category=checkpoint_artifact_category,
                    count_r2_uploads=count_r2_uploads,
                )
            # The job state is the commit record, and must be uploaded after all
            # durable workspace artifacts for this checkpoint event.
            self._upload_r2_file(
                self.state_path,
                destination_object_key(self.config, JOB_STATE_RELATIVE_PATH),
                category="checkpoint_state_commits",
                count_r2_uploads=count_r2_uploads,
            )

    def _upload_r2_file(
        self,
        path: Path,
        key: str,
        *,
        category: str | None = None,
        count_r2_uploads: bool = True,
    ) -> None:
        counters = self.metrics["r2_object_upload_requests"]
        if count_r2_uploads and counters is not None:
            if category not in R2_UPLOAD_BREAKDOWN_DEFINITIONS:
                raise RuntimeError(f"Missing or invalid R2 upload metric category: {category!r}")
            counters["attempts_total"] += 1
            counters["breakdown"][category]["attempts_total"] += 1
        try:
            upload_r2_file(self.client, self.destination, path, key)
        except BaseException:
            if count_r2_uploads and counters is not None:
                counters["attempts_failed"] += 1
                counters["breakdown"][category]["attempts_failed"] += 1
            raise
        if count_r2_uploads and counters is not None:
            counters["attempts_succeeded"] += 1
            counters["breakdown"][category]["attempts_succeeded"] += 1

    def materialize_source(self) -> Path:
        path, self.source_temp_dir = materialize_source(
            self.config,
            r2_client=self.client if self.is_r2 else self.r2_client,
        )
        return path

    def set_chapter_plan(self, source_paths: list[Path], preparation: dict[str, Any]) -> None:
        if not source_paths:
            raise SystemExit("No chapters were detected, so prep-subject cannot create a resumable canonical chapter set.")
        chapters = []
        for index, source_path in enumerate(sorted(source_paths), start=1):
            chapters.append(
                {
                    "chapter_number": f"{index:03d}",
                    "source_filename": source_path.name,
                    "source_sha256": _sha256(source_path),
                    "state": "pending",
                    "attempt_count": 0,
                    "created_at": utc_now(),
                    "updated_at": utc_now(),
                    "latest_error": None,
                    "successful_artifacts": [],
                    "proofreading": None,
                }
            )
        self.state["chapters"] = chapters
        self.state["preparation"] = preparation
        self.persist(
            checkpoint_artifacts=source_paths,
            checkpoint_artifact_category="checkpoint_source_snapshots",
        )

    def discard_transient_preparation(self) -> None:
        """Remove a prepared full-subject working DOCX after snapshots are durable."""
        relative = self.workspace_relative / ".transient"
        transient_dir = self.local_workspace_root / relative
        if transient_dir.exists():
            shutil.rmtree(transient_dir)
        if self.is_r2:
            self.client.delete_prefix(
                self.destination["bucket"],
                subject_artifact_object_key(self.destination, relative) + "/",
            )

    def chapter_source_path(self, chapter: dict[str, Any]) -> Path:
        path = self.paths["unmodified_source_text"] / chapter["source_filename"]
        if not path.is_file() or _sha256(path) != chapter["source_sha256"]:
            raise SystemExit(
                f"Checkpointed source snapshot for chapter {chapter['chapter_number']} is missing or changed. "
                "Re-run with --overwrite to build a compatible workspace."
            )
        return path

    def reconcile_successes(self) -> list[str]:
        """Validate saved successes and repair a crash between artifact and state writes."""
        reused = []
        changed = False
        for chapter in self.state.get("chapters", []):
            valid = self._validate_success_artifacts(chapter)
            if chapter.get("state") == "succeeded":
                if valid:
                    reused.append(chapter["chapter_number"])
                else:
                    changed = True
                    chapter["state"] = "pending"
                    chapter["successful_artifacts"] = []
                    chapter["proofreading"] = None
                    chapter["latest_error"] = {
                        "code": "checkpoint_artifacts_invalid",
                        "message": "Saved artifacts were missing or did not pass checksum validation; chapter will be reprocessed.",
                    }
                    chapter["updated_at"] = utc_now()
            elif valid:
                changed = True
                chapter["state"] = "succeeded"
                chapter["successful_artifacts"] = self._expected_artifact_records(chapter)
                chapter["proofreading"] = self._reconciled_proofreading_summary(chapter)
                chapter["latest_error"] = None
                chapter["updated_at"] = utc_now()
                reused.append(chapter["chapter_number"])
        if changed:
            self.persist()
        return reused

    def _expected_artifact_paths(self, chapter: dict[str, Any]) -> list[Path]:
        number = int(chapter["chapter_number"])
        text_name = chapter_output_filename(self.config, number, ".txt")
        metadata_name = chapter_output_filename(self.config, number, ".json")
        stem = Path(text_name).stem
        return [
            self.paths["unmodified_source_text"] / chapter["source_filename"],
            self.paths["text_and_metadata"] / text_name,
            self.paths["text_and_metadata"] / metadata_name,
            self.paths["proofreading"] / f"{stem}.proofread.diff.txt",
            self.paths["proofreading"] / f"{stem}.proofread.json",
        ]

    def _expected_artifact_records(self, chapter: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {"path": str(path.relative_to(self.paths["subject"])), "sha256": _sha256(path)}
            for path in self._expected_artifact_paths(chapter)
        ]

    def _validate_success_artifacts(self, chapter: dict[str, Any]) -> bool:
        try:
            paths = self._expected_artifact_paths(chapter)
            if not all(path.is_file() for path in paths):
                return False
            records = chapter.get("successful_artifacts")
            if records:
                expected = {record.get("path"): record.get("sha256") for record in records}
                current = {
                    str(path.relative_to(self.paths["subject"])): _sha256(path)
                    for path in paths
                }
                if expected != current:
                    return False
            source_sha = _sha256(paths[0])
            text_sha = _sha256(paths[1])
            metadata = _read_json(paths[2], "Checkpointed chapter metadata")
            details = _read_json(paths[4], "Checkpointed proofreading details")
            locale = self.config.get("_locale") or locale_spec(self.config["metadata_defaults"]["language"])
            source_identity = build_content_identity(
                self.config["naming"]["category_code"],
                self.config["naming"]["subject_code"],
                locale.language,
                paths[0].read_text(encoding="utf-8"),
            )
            canonical_identity = build_content_identity(
                self.config["naming"]["category_code"],
                self.config["naming"]["subject_code"],
                locale.language,
                paths[1].read_text(encoding="utf-8"),
            )
            return (
                metadata["integrity"]["artifacts"]["text"]["value"] == text_sha
                and metadata.get("content_identity") == canonical_identity
                and details["canonical_corrected"]["text_sha256"] == text_sha
                and details["canonical_corrected"].get("content_identity") == canonical_identity
                and details["canonical_corrected"].get("text_artifact")
                == metadata.get("storage", {}).get("artifacts", {}).get("text")
                and source_sha == chapter.get("source_sha256")
                and details["unmodified_source"].get("text_sha256") == source_sha
                and details["unmodified_source"].get("content_identity") == source_identity
                and details.get("integrity", {}).get("unmodified_source", {}).get("value") == source_sha
                and details.get("integrity", {}).get("canonical_corrected", {}).get("value") == text_sha
                and details.get("status") == "succeeded"
            )
        except (KeyError, OSError, SystemExit, TypeError, UnicodeDecodeError):
            return False

    def _reconciled_proofreading_summary(self, chapter: dict[str, Any]) -> dict[str, Any]:
        number = int(chapter["chapter_number"])
        text_name = chapter_output_filename(self.config, number, ".txt")
        details = _read_json(
            self.paths["proofreading"] / f"{Path(text_name).stem}.proofread.json",
            "Checkpointed proofreading details",
        )
        metadata = _read_json(self.paths["text_and_metadata"] / chapter_output_filename(self.config, number, ".json"), "Checkpointed chapter metadata")
        return {
            "chapter_number": chapter["chapter_number"],
            "status": "succeeded",
            "correction_count": len(details.get("gemini_edits", [])),
            "local_diff_summary": details.get("local_diff_summary", {}),
            "unmodified_source_content_key": details.get("unmodified_source", {}).get("content_identity", {}).get("content_key"),
            "canonical_content_key": metadata.get("content_identity", {}).get("content_key"),
            "artifacts": {
                "unmodified_source": details.get("unmodified_source", {}).get("text_artifact"),
                "canonical_text": metadata.get("storage", {}).get("artifacts", {}).get("text"),
                "canonical_metadata": metadata.get("storage", {}).get("artifacts", {}).get("metadata"),
                "diff": details.get("diff_artifact"),
                "json": destination_artifact_reference(
                    self.config,
                    Path("chapters") / "proofreading" / f"{Path(text_name).stem}.proofread.json",
                ),
            },
        }

    def mark_chapter_success(self, chapter: dict[str, Any], result: dict[str, Any]) -> None:
        chapter["state"] = "succeeded"
        chapter["attempt_count"] += 1
        chapter["updated_at"] = utc_now()
        chapter["succeeded_at"] = utc_now()
        chapter["latest_error"] = None
        chapter["successful_artifacts"] = result.pop("checkpoint_artifacts")
        request_metrics = {
            "attempts": result.pop("gemini_request_attempts", 0),
            "successful_request_attempts": result.pop("gemini_successful_request_attempts", 0),
        }
        chapter["proofreading"] = result
        self._record_gemini_success(request_metrics)
        self.persist(
            checkpoint_artifacts=[
                self.paths["subject"] / record["path"]
                for record in chapter["successful_artifacts"]
                # Source snapshots are committed once with the chapter plan.
                # A chapter success commits only newly generated durable output.
                if not str(record["path"]).startswith("chapters/unmodified_source_text/")
            ],
            checkpoint_artifact_category="checkpoint_chapter_artifacts",
        )

    def mark_chapter_failure(self, chapter: dict[str, Any], exc: BaseException) -> None:
        chapter["state"] = "failed"
        chapter["attempt_count"] += 1
        chapter["updated_at"] = utc_now()
        chapter["latest_error"] = _safe_error(exc)
        self._record_gemini_failure(exc)
        self.persist()

    def _record_gemini_success(self, result: dict[str, Any]) -> None:
        attempts = int(result.get("attempts", 0))
        succeeded = int(result.get("successful_request_attempts", attempts))
        succeeded = min(max(succeeded, 0), attempts)
        counters = self.metrics["gemini_generate_content_requests"]
        counters["attempts_total"] += attempts
        counters["attempts_succeeded"] += succeeded
        counters["attempts_failed"] += attempts - succeeded

    def _record_gemini_failure(self, exc: BaseException) -> None:
        attempts = int(getattr(exc, "request_attempts", 0))
        succeeded = int(getattr(exc, "successful_request_attempts", 0))
        succeeded = min(max(succeeded, 0), attempts)
        counters = self.metrics["gemini_generate_content_requests"]
        counters["attempts_total"] += attempts
        counters["attempts_succeeded"] += succeeded
        counters["attempts_failed"] += attempts - succeeded

    def mark_global_failure(self, exc: BaseException) -> None:
        self.state["state"] = "failed"
        self.state["failure"] = _safe_error(exc)
        self.persist()

    def mark_incomplete(self) -> None:
        self.state["state"] = "incomplete"
        self.state["failure"] = None
        self.persist()

    def prepare_for_publication(self) -> Path:
        chapters = self.state.get("chapters", [])
        if not chapters or any(chapter.get("state") != "succeeded" for chapter in chapters):
            raise SystemExit("Cannot publish until every expected chapter has a validated successful checkpoint.")
        for chapter in chapters:
            if not self._validate_success_artifacts(chapter):
                raise SystemExit(
                    f"Checkpoint artifacts for chapter {chapter['chapter_number']} are not valid; re-run with --resume "
                    "to reprocess it before publication."
                )
        proofread = [chapter["proofreading"] for chapter in chapters]
        locale = self.config.get("_locale") or locale_spec(self.config["metadata_defaults"]["language"])
        write_proofreading_manifest(self.paths, self.config["_proofreading_config"], proofread, locale)
        manifest = write_chapter_content_manifest(self.config, self.paths)
        self.state["state"] = "ready_to_publish"
        self.state["publication"] = {
            "state": "ready_to_publish",
            "canonical_manifest": {
                "reference": destination_artifact_reference(self.config, Path("chapters") / manifest.name),
                "sha256": _sha256(manifest),
                "chapter_numbers": [chapter["chapter_number"] for chapter in chapters],
            },
        }
        self.persist()
        return manifest

    def publish(self) -> None:
        self.state["state"] = "publishing"
        self.state["publication"]["state"] = "publishing"
        self.persist()
        if is_local(self.destination):
            self._publish_local()
        else:
            self._publish_r2()
        if self.overwrite:
            cleanup = self.state["publication"].setdefault("obsolete_artifact_cleanup", {})
            if is_local(self.destination):
                cleanup["chapter_docx_invalidation"] = invalidate_local_chapter_docx_artifacts(
                    self.subject_dir
                )
                self.persist()
                cleanup["legacy_full_subject_cleanup"] = cleanup_local_legacy_full_subject(self.subject_dir)
                self.persist()
                self.state["publication"]["semantic_invalidation"] = invalidate_local_semantic_artifacts(self.subject_dir)
            else:
                cleanup["chapter_docx_invalidation"] = invalidate_r2_chapter_docx_artifacts(
                    self.config,
                    self.client,
                )
                self.persist()
                cleanup["legacy_full_subject_cleanup"] = cleanup_r2_legacy_full_subject(
                    self.config,
                    self.client,
                )
                self.persist()
                self.state["publication"]["semantic_invalidation"] = invalidate_r2_semantic_artifacts(self.config, self.client)
            self.persist()
            docx_cleanup = cleanup["chapter_docx_invalidation"]
            full_cleanup = cleanup["legacy_full_subject_cleanup"]
            semantic_cleanup = self.state["publication"]["semantic_invalidation"]
            print(
                "[overwrite] Derived chapter DOCX invalidation: "
                f"{'removed' if docx_cleanup['invalidated'] else 'not needed'}."
            )
            print(
                "[overwrite] Legacy full_subject cleanup: "
                f"{'removed' if full_cleanup['invalidated'] else 'not needed'}."
            )
            print(
                "[overwrite] Semantic chunk invalidation: "
                f"{'removed' if semantic_cleanup['invalidated'] else 'not needed'}."
            )
        self.state["state"] = "succeeded"
        self.state["publication"]["state"] = "succeeded"
        self.persist()
        self._remove_completed_workspace()

    def _publish_local(self) -> None:
        promotion_root = self.workspace_dir / ".promotion"
        backup_root = self.workspace_dir / ".publication-backup"
        for relative in (*PREP_ARTIFACT_DIRS,):
            source = self.workspace_dir / relative
            if source.exists():
                self._replace_local_path(source, self.subject_dir / relative, relative, promotion_root, backup_root)
        # The candidate manifest is the downstream readiness marker and must be last.
        for relative in CANONICAL_ARTIFACT_FILES:
            source = self.workspace_dir / relative
            if source.exists():
                self._replace_local_path(source, self.subject_dir / relative, relative, promotion_root, backup_root)

    def _replace_local_path(self, source: Path, target: Path, relative: Path, promotion_root: Path, backup_root: Path) -> None:
        candidate = promotion_root / relative
        candidate.parent.mkdir(parents=True, exist_ok=True)
        if candidate.is_dir():
            shutil.rmtree(candidate)
        elif candidate.exists():
            candidate.unlink()
        if source.is_dir():
            shutil.copytree(source, candidate)
        else:
            shutil.copy2(source, candidate)
        if target.exists():
            backup = backup_root / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            if backup.exists():
                if backup.is_dir():
                    shutil.rmtree(backup)
                else:
                    backup.unlink()
            shutil.move(str(target), str(backup))
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(candidate, target)

    def _publish_r2(self) -> None:
        uploads: list[tuple[Path, str]] = []
        manifest_relative = Path("chapters") / "chapter_content_manifest.json"
        for relative in (*PREP_ARTIFACT_DIRS, *CANONICAL_ARTIFACT_FILES):
            root = self.workspace_dir / relative
            if root.is_file():
                uploads.append((root, destination_object_key(self.config, relative)))
            elif root.is_dir():
                uploads.extend(
                    (path, destination_object_key(self.config, path.relative_to(self.workspace_dir)))
                    for path in sorted(root.rglob("*"))
                    if path.is_file()
                )
        uploads.sort(key=lambda item: item[0].relative_to(self.workspace_dir) == manifest_relative)
        for path, key in uploads:
            self._upload_r2_file(path, key, category="canonical_publication_artifacts")
        if self.overwrite:
            uploaded_keys = {key for _, key in uploads}
            stale_keys = []
            for relative in PREP_ARTIFACT_DIRS:
                prefix = destination_object_key(self.config, relative) + "/"
                stale_keys.extend(
                    key
                    for key in self.client.list_keys(self.destination["bucket"], prefix)
                    if key not in uploaded_keys
                )
            self.client.delete_keys(self.destination["bucket"], stale_keys)
            self.state["publication"]["stale_prep_artifact_cleanup"] = {
                "deleted_keys": stale_keys,
                "deleted_count": len(stale_keys),
            }

    def _remove_completed_workspace(self) -> None:
        if is_local(self.destination):
            if self.workspace_dir.exists():
                shutil.rmtree(self.workspace_dir)
        else:
            self.client.delete_prefix(
                self.destination["bucket"],
                subject_artifact_object_key(self.destination, self.workspace_relative) + "/",
            )
            if self.workspace_dir.exists():
                shutil.rmtree(self.workspace_dir)
        self.state["workspace"]["status"] = "removed_after_success"
        self.persist()

    def write_report(self, config_path, entry_point: str, status: str, failure: dict[str, str] | None, reused: list[str], attempted: list[str]) -> dict[str, Any]:
        """Write immutable, text-free invocation reports at the destination."""
        if self.is_r2 and self.state.get("lease", {}).get("owner_id") == self.owner_id:
            # Release the advisory lease before snapshotting metrics into the
            # immutable report. This is an actual state transition, not a
            # heartbeat, and permits an immediate --resume after an incomplete
            # invocation.
            self.state["lease"] = self.state["lease"] | {"active": False, "released_at": utc_now()}
            self.persist()
        locale = self.config.get("_locale") or locale_spec(self.config["metadata_defaults"]["language"])
        artifact_root = (
            subject_artifact_prefix(self.destination)
            if self.is_r2
            else str(self.subject_dir)
        )
        timestamp = f"{timestamp_for_filename()}-{self.state['run']['run_id'][:8]}"
        base = f"prep-subject-{timestamp}"
        reports_dir = self.subject_dir / PREP_REPORT_RELATIVE_DIR
        reports_dir.mkdir(parents=True, exist_ok=True)
        json_path, markdown_path = reports_dir / f"{base}.json", reports_dir / f"{base}.md"
        report = {
            "schema_version": 1,
            "command": "prep-subject",
            "status": status,
            "created_at": utc_now(),
            "job_id": self.state["job_id"],
            "run_id": self.state["run"]["run_id"],
            "entry_point": entry_point,
            "overwrite": self.overwrite,
            "config_path": str(config_path) if config_path else None,
            "destination_backend": self.destination.get("backend", "local"),
            "subject": {
                "category_code": self.config["naming"]["category_code"],
                "subject_code": self.config["naming"]["subject_code"],
                "language": locale.language,
                "artifact_root": artifact_root,
            },
            "proofreading_locale": locale.proofreading_provenance(),
            "failure_stage": "proofreading" if status == "incomplete" else ("global" if failure else None),
            "failure": failure,
            "counts": self.state["counts"],
            "run_metrics": self._report_metrics(),
            "processing_summary": {
                "source_materialization_status": "succeeded",
                "source_docx_validation_status": (
                    "succeeded" if self.state.get("preparation") else "failed_or_not_completed"
                ),
                "legacy_converter_counts": (self.state.get("preparation") or {}).get("converter_counts", {}),
                "converted_text_nodes": (self.state.get("preparation") or {}).get("total_nodes", 0),
                "converted_or_extracted_character_count": (self.state.get("preparation") or {}).get("total_chars", 0),
                "chapters_detected": (self.state.get("preparation") or {}).get("chapters_detected", 0),
                "unmodified_source_snapshots": len(self.state.get("chapters", [])),
                "canonical_chapters_succeeded": self.state["counts"]["succeeded"],
                "proofreading_manifest_status": (
                    "published" if status == "succeeded" else "not_published"
                ),
                "chapter_content_manifest_status": (
                    "published_last" if status == "succeeded" else "not_published"
                ),
            },
            "chapters": [
                {
                    "chapter_number": chapter["chapter_number"],
                    "state": chapter["state"],
                    "attempt_count": chapter["attempt_count"],
                    "latest_error": chapter.get("latest_error"),
                    "outcome": "reused_checkpoint" if chapter["chapter_number"] in reused else ("attempted" if chapter["chapter_number"] in attempted else "pending"),
                }
                for chapter in self.state.get("chapters", [])
            ],
            "publication": self.state.get("publication"),
            "preparation": self.state.get("preparation"),
            "checkpoint_contract_version": CHECKPOINT_CONTRACT_VERSION,
        }
        _write_json_atomically(json_path, report)
        markdown_path.write_text(_render_report_markdown(report), encoding="utf-8")
        references = {
            "json": destination_artifact_reference(self.config, PREP_REPORT_RELATIVE_DIR / json_path.name),
            "markdown": destination_artifact_reference(self.config, PREP_REPORT_RELATIVE_DIR / markdown_path.name),
        }
        self.state["run_reports"].append(references)
        if self.is_r2:
            for path in (json_path, markdown_path):
                # Audit-report writes do not count as R2 publication or
                # checkpoint upload attempts, so the report is immutable.
                self._upload_r2_file(
                    path,
                    destination_object_key(self.config, PREP_REPORT_RELATIVE_DIR / path.name),
                    count_r2_uploads=False,
                )
        # R2 reports are immutable standalone records. Avoid a follow-up state
        # write solely to index those reports, so audit creation cannot add an
        # uncounted checkpoint upload after the report has captured its metrics.
        if not self.is_r2:
            self.persist()
        return references

    def _report_metrics(self) -> dict[str, Any]:
        return {
            "gemini_generate_content_requests": {
                **self.metrics["gemini_generate_content_requests"],
                "definition": (
                    "Actual Gemini generate_content request attempts in this invocation, including retries and "
                    "terminal failures; excludes reused checkpoints and local pacing waits."
                ),
            },
            "r2_object_upload_requests": (
                {
                    **{
                        key: value
                        for key, value in self.metrics["r2_object_upload_requests"].items()
                        if key != "breakdown"
                    },
                    "definition": (
                        "R2 object-upload request attempts in this invocation caused by checkpoint commits or "
                        "canonical prep publication; excludes reads, lists, deletes, and audit-report uploads."
                    ),
                    "breakdown": {
                        category: {
                            **counters,
                            "definition": R2_UPLOAD_BREAKDOWN_DEFINITIONS[category],
                        }
                        for category, counters in self.metrics["r2_object_upload_requests"]["breakdown"].items()
                    },
                }
                if self.metrics["r2_object_upload_requests"] is not None
                else None
            ),
        }

    def print_metrics_summary(self) -> None:
        gemini = self.metrics["gemini_generate_content_requests"]
        summary = (
            "prep-subject metrics: Gemini generate_content attempts "
            f"{gemini['attempts_total']} ({gemini['attempts_succeeded']} succeeded, "
            f"{gemini['attempts_failed']} failed)"
        )
        r2 = self.metrics["r2_object_upload_requests"]
        if r2 is not None:
            summary += (
                "; R2 object-upload attempts "
                f"{r2['attempts_total']} ({r2['attempts_succeeded']} succeeded, {r2['attempts_failed']} failed)"
            )
        print(summary + ".")

    def close(self) -> None:
        if self.state and self.state.get("lease", {}).get("owner_id") == self.owner_id:
            self.state["lease"] = self.state.get("lease", {}) | {"active": False, "released_at": utc_now()}
            if not self.is_r2:
                self.persist()
        if self.local_lock_created and self.local_lock_path:
            self.local_lock_path.unlink(missing_ok=True)
        if self.source_temp_dir:
            self.source_temp_dir.cleanup()
        if self.workspace_temp_dir:
            self.workspace_temp_dir.cleanup()


def _render_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Gurubodh prep-subject Run Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Job: `{report['job_id']}`",
        f"- Run: `{report['run_id']}`",
        f"- Category: `{report['subject']['category_code']}`",
        f"- Subject: `{report['subject']['subject_code']}`",
        f"- Language: `{report['subject']['language']}`",
        f"- Language-specific artifact root: `{report['subject']['artifact_root']}`",
        f"- Proofreading template: `{report['proofreading_locale']['instruction_template']['id']}` v{report['proofreading_locale']['instruction_template']['version']} (`{report['proofreading_locale']['instruction_template']['sha256']}`)",
        f"- Overwrite: `{report['overwrite']}`",
        f"- Checkpoint artifact contract: `{report['checkpoint_contract_version']}` (five files per chapter)",
        f"- Counts: succeeded `{report['counts']['succeeded']}`, failed `{report['counts']['failed']}`, pending `{report['counts']['pending']}`",
        "",
        "## Processing",
        "",
        f"- Source materialization: `{report['processing_summary']['source_materialization_status']}`",
        f"- Source DOCX validation: `{report['processing_summary']['source_docx_validation_status']}`",
        f"- Legacy converter counts: `{json.dumps(report['processing_summary']['legacy_converter_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Converted text nodes: `{report['processing_summary']['converted_text_nodes']}`",
        f"- Converted or extracted characters: `{report['processing_summary']['converted_or_extracted_character_count']}`",
        f"- Chapters detected: `{report['processing_summary']['chapters_detected']}`",
        f"- Unmodified-source snapshots: `{report['processing_summary']['unmodified_source_snapshots']}`",
        f"- Canonical chapters succeeded: `{report['processing_summary']['canonical_chapters_succeeded']}`",
        f"- Proofreading manifest: `{report['processing_summary']['proofreading_manifest_status']}`",
        f"- Chapter content manifest: `{report['processing_summary']['chapter_content_manifest_status']}`",
        "",
        "## Run metrics",
        "",
    ]
    gemini = report["run_metrics"]["gemini_generate_content_requests"]
    lines.append(
        "- Gemini `generate_content` request attempts: "
        f"`{gemini['attempts_total']}` total, `{gemini['attempts_succeeded']}` succeeded, "
        f"`{gemini['attempts_failed']}` failed. {gemini['definition']}"
    )
    r2 = report["run_metrics"]["r2_object_upload_requests"]
    if r2 is not None:
        lines.append(
            "- R2 object-upload request attempts: "
            f"`{r2['attempts_total']}` total, `{r2['attempts_succeeded']}` succeeded, "
            f"`{r2['attempts_failed']}` failed. {r2['definition']}"
        )
        lines.extend(
            [
                "",
                "### R2 upload breakdown",
                "",
                "| Category | Total | Succeeded | Failed |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        lines.extend(
            f"| {category} — {counters['definition']} | {counters['attempts_total']} | "
            f"{counters['attempts_succeeded']} | {counters['attempts_failed']} |"
            for category, counters in r2["breakdown"].items()
        )
    if report["failure"]:
        lines.extend(["", "## Failure", "", f"- {report['failure']['code']}: {report['failure']['message']}"])
    lines.extend(["", "## Chapters", "", "| Chapter | State | Attempts | Outcome |", "| --- | --- | ---: | --- |"])
    lines.extend(
        f"| {chapter['chapter_number']} | {chapter['state']} | {chapter['attempt_count']} | {chapter['outcome']} |"
        for chapter in report["chapters"]
    )
    publication = report.get("publication") or {}
    lines.extend(["", "## Publication", "", f"- State: `{publication.get('state', 'not_ready')}`"])
    cleanup = publication.get("obsolete_artifact_cleanup") or {}
    if cleanup:
        docx = cleanup.get("chapter_docx_invalidation") or {}
        full_subject = cleanup.get("legacy_full_subject_cleanup") or {}
        lines.extend(
            [
                f"- Derived chapter DOCX invalidated: `{docx.get('invalidated', False)}`",
                f"- Legacy full_subject removed: `{full_subject.get('invalidated', False)}`",
            ]
        )
    semantic = publication.get("semantic_invalidation")
    if semantic:
        lines.append(f"- Semantic chunks invalidated: `{semantic.get('invalidated', False)}`")
    return "\n".join(lines) + "\n"


def _is_global_proofreading_failure(exc: ProofreadingError) -> bool:
    return exc.code in {"missing_credentials", "missing_dependency"}


def validate_canonical_release_gate(
    config: dict[str, Any],
    source_subject: Path,
    candidate_manifest: dict[str, Any],
    *,
    command_name: str,
    r2_client=None,
) -> None:
    """Require a completed prep checkpoint before derived output can mutate.

    The candidate manifest is already parsed here, but no derived-output
    directory has been created or deleted. This is intentionally usable for
    both local and R2 sources so an incomplete overwrite cannot erase a
    previously generated output set.
    """
    source = config["source"]
    state_path = Path(source_subject) / JOB_STATE_RELATIVE_PATH
    if is_r2(source):
        client = r2_client or R2StorageClient.from_env()
        key = subject_artifact_object_key(source, JOB_STATE_RELATIVE_PATH)
        if not client.exists(source["bucket"], key):
            raise SystemExit(f"{command_name} requires a completed prep-subject job state; no checkpoint was found.")
        client.download_file(source["bucket"], key, state_path)
    elif not state_path.is_file():
        raise SystemExit(f"{command_name} requires a completed prep-subject job state; no checkpoint was found.")
    state = _read_json(state_path, "Prep-subject job state")
    if state.get("schema_version") != CHECKPOINT_SCHEMA_VERSION or state.get("state") != "succeeded":
        raise SystemExit(
            f"{command_name} refuses prepared content while the latest prep-subject job is not succeeded. "
            "Use gurubodh prep-subject --resume to complete or recover the preparation job first."
        )
    publication = state.get("publication") or {}
    if publication.get("state") != "succeeded":
        raise SystemExit(
            f"{command_name} refuses prepared content while the latest prep-subject publication is not succeeded."
        )
    canonical = publication.get("canonical_manifest") or {}
    if canonical.get("sha256") != candidate_manifest.get("sha256"):
        raise SystemExit(
            f"{command_name} refuses the candidate manifest because it does not match the completed prep-subject checkpoint."
        )
    checkpoint_chapters = state.get("chapters")
    if not isinstance(checkpoint_chapters, list) or any(chapter.get("state") != "succeeded" for chapter in checkpoint_chapters):
        raise SystemExit(f"{command_name} requires every completed checkpoint chapter to be succeeded.")
    expected_numbers = [chapter.get("chapter_number") for chapter in checkpoint_chapters]
    manifest_numbers = [chapter.get("generated_chapter_number") for chapter in candidate_manifest.get("chapters", [])]
    if expected_numbers != manifest_numbers or canonical.get("chapter_numbers") != expected_numbers:
        raise SystemExit(
            f"{command_name} refuses the candidate manifest because its chapters do not match the completed checkpoint set."
        )
    checkpoint_keys = {
        chapter["chapter_number"]: (chapter.get("proofreading") or {}).get("canonical_content_key")
        for chapter in checkpoint_chapters
    }
    if any(checkpoint_keys.get(chapter["generated_chapter_number"]) != chapter.get("content_key") for chapter in candidate_manifest["chapters"]):
        raise SystemExit(
            f"{command_name} refuses the candidate manifest because its chapter identities do not match the completed checkpoint."
        )


def validate_generate_chunks_gate(
    config: dict[str, Any], source_subject: Path, candidate_manifest: dict[str, Any], r2_client=None
) -> None:
    """Backward-compatible command-specific wrapper for existing callers."""
    validate_canonical_release_gate(
        config,
        source_subject,
        candidate_manifest,
        command_name="generate-chunks",
        r2_client=r2_client,
    )


def run_resumable_prep_job(
    context,
    config: dict[str, Any],
    entry_point: str,
    overwrite: bool,
    resume: bool,
    config_path: Path | None,
    prepare_source_docx: Callable[[Path, Path, Callable[..., None]], dict[str, Any]],
    r2_client=None,
) -> dict[str, Any]:
    """Run either preparation pipeline with checkpointed proof-reading."""
    manager = PrepCheckpointManager(config, resume, overwrite, r2_client=r2_client)
    reused: list[str] = []
    attempted: list[str] = []
    try:
        print(
            "\n".join(
                (
                    "=" * 72,
                    "IMPORTANT: prep-subject is single-writer per destination.",
                    "Run only one local or R2 writer for this subject at a time.",
                    "Concurrent runs can duplicate Gemini calls and overwrite",
                    "checkpoint/workspace artifacts.",
                    "The local advisory lock and R2 advisory lease are guardrails,",
                    "not reliable mutual exclusion.",
                    "=" * 72,
                )
            )
        )
        manager.open()
        source_path = manager.materialize_source()
        validate_supported_source_fonts(source_path)
        outcome = manager.begin(_sha256(source_path))
        if outcome == "already_complete":
            print("prep-subject already complete; the compatible checkpoint is succeeded. No Gemini requests were made.")
            manager.write_report(config_path, entry_point, "succeeded", None, reused, attempted)
            manager.print_metrics_summary()
            return {
                "status": "succeeded",
                "already_complete": True,
                "counts": manager.state["counts"],
                "metrics": manager._report_metrics(),
            }

        paths = manager.paths
        ensure_job_dirs(paths)
        result = manager.state.get("preparation") or {}
        if not manager.state.get("chapters"):
            try:
                print("[prepare] Building chapter source snapshots from the configured DOCX in the checkpoint workspace.")
                transient_dir = manager.workspace_dir / ".transient"
                transient_dir.mkdir(parents=True, exist_ok=True)
                result = prepare_source_docx(
                    source_path,
                    transient_dir / "prepared-source.docx",
                    lambda *_: manager.heartbeat(),
                )
                split_outputs = validate_and_split(
                    config,
                    result,
                    paths,
                    entry_point,
                    progress=lambda *_: manager.heartbeat(),
                )
                manager.set_chapter_plan(
                    sorted(paths["unmodified_source_text"].glob("*_unmodified_source.txt")),
                    {
                        "total_nodes": result.get("total_nodes", 0),
                        "total_chars": result.get("total_chars", 0),
                        "converter_counts": result.get("converter_counts", {}),
                        "chapters_detected": len(split_outputs),
                    },
                )
                manager.discard_transient_preparation()
            except BaseException as exc:
                manager.mark_global_failure(exc)
                manager.write_report(config_path, entry_point, "failed", _safe_error(exc), reused, attempted)
                manager.print_metrics_summary()
                raise

        manager.discard_transient_preparation()
        reused = manager.reconcile_successes()
        consecutive_infrastructure_failures = 0
        locale = config.get("_locale") or locale_spec(config["metadata_defaults"]["language"])
        proofreader = GeminiProofreader(config["_proofreading_config"], locale=locale)
        for chapter in manager.state["chapters"]:
            if chapter["state"] == "succeeded":
                continue
            manager.heartbeat()
            source_snapshot = manager.chapter_source_path(chapter)
            number = int(chapter["chapter_number"])
            attempted.append(chapter["chapter_number"])
            try:
                chapter_result = proofread_single_chapter_artifacts(
                    config,
                    paths,
                    number,
                    source_snapshot,
                    converter_counts=manager.state.get("preparation", {}).get("converter_counts", {}),
                    entry_point=entry_point,
                    proofreader=proofreader,
                    progress=lambda message, n=chapter["chapter_number"]: print(f"[proofread {n}] {message}"),
                )
                manager.mark_chapter_success(chapter, chapter_result)
                consecutive_infrastructure_failures = 0
            except ProofreadingError as exc:
                manager.mark_chapter_failure(chapter, exc)
                if _is_global_proofreading_failure(exc):
                    manager.mark_global_failure(exc)
                    manager.write_report(config_path, entry_point, "failed", _safe_error(exc), reused, attempted)
                    manager.print_metrics_summary()
                    raise SystemExit(str(exc)) from exc
                if exc.code in {"api_error", "rate_limited"}:
                    consecutive_infrastructure_failures += 1
                    if consecutive_infrastructure_failures >= INFRASTRUCTURE_FAILURE_CIRCUIT_BREAKER:
                        print("[proofread] Infrastructure failure circuit breaker opened; remaining chapters remain pending.")
                        break
                continue

        if any(chapter["state"] != "succeeded" for chapter in manager.state["chapters"]):
            manager.mark_incomplete()
            manager.write_report(config_path, entry_point, "incomplete", None, reused, attempted)
            manager.print_metrics_summary()
            raise SystemExit(
                "prep-subject is incomplete; successful chapter checkpoints were retained. "
                "Re-run with --resume to retry failed or pending chapters."
            )

        manager.prepare_for_publication()
        try:
            manager.publish()
        except BaseException as exc:
            manager.state["state"] = "publishing"
            manager.state["publication"]["state"] = "publishing"
            manager.state["failure"] = _safe_error(exc)
            manager.persist()
            manager.write_report(config_path, entry_point, "failed", _safe_error(exc), reused, attempted)
            manager.print_metrics_summary()
            raise
        manager.write_report(config_path, entry_point, "succeeded", None, reused, attempted)
        counts = manager.state["counts"]
        artifact_root = subject_artifact_prefix(manager.destination) if manager.is_r2 else str(manager.subject_dir)
        print(
            "prep-subject complete; canonical artifacts were published successfully to "
            f"{artifact_root}. Chapters: {counts['succeeded']} succeeded, "
            f"{counts['failed']} failed, {counts['pending']} pending."
        )
        manager.print_metrics_summary()
        return {
            "status": "succeeded",
            "already_complete": False,
            "counts": manager.state["counts"],
            "metrics": manager._report_metrics(),
        }
    finally:
        manager.close()
