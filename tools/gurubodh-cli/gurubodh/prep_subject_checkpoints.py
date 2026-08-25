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

from gurubodh.content_manifest import write_chapter_content_manifest
from gurubodh.naming import chapter_output_filename, full_subject_output_filename
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
    destination_artifact_reference,
    destination_object_key,
    invalidate_local_semantic_artifacts,
    invalidate_r2_semantic_artifacts,
    is_local,
    is_r2,
    materialize_source,
    subject_artifact_object_key,
    subject_artifact_prefix,
    upload_r2_file,
)
from gurubodh.time_utils import timestamp_for_filename, utc_now


CHECKPOINT_SCHEMA_VERSION = 1
CHECKPOINT_CONTRACT_VERSION = 1
PROMPT_CONTRACT_VERSION = 1
RUN_STATE_RELATIVE_DIR = Path("run_state") / "prep-subject"
JOB_STATE_RELATIVE_PATH = RUN_STATE_RELATIVE_DIR / "job-state.json"
WORK_RELATIVE_DIR = Path(".work") / "prep-subject"
PREP_REPORT_RELATIVE_DIR = Path("run_reports") / "prep-subject"
LEASE_SECONDS = 120
INFRASTRUCTURE_FAILURE_CIRCUIT_BREAKER = 2


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
            "prompt_contract_version": PROMPT_CONTRACT_VERSION,
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
                f"Another prep-subject writer is active for {self.subject_dir}. "
                "Wait for it to finish, or use --resume after an interrupted writer's lease has expired."
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
        upload_r2_file(
            self.client,
            self.destination,
            archive_path,
            destination_object_key(self.config, archive_relative),
        )
        self.client.delete_prefix(
            self.destination["bucket"],
            subject_artifact_object_key(self.destination, self.workspace_relative) + "/",
        )

    def _canonical_artifacts_exist(self) -> bool:
        if is_local(self.destination):
            return any((self.subject_dir / relative).exists() for relative in (*PREP_ARTIFACT_DIRS, *CANONICAL_ARTIFACT_FILES))
        for relative in (*PREP_ARTIFACT_DIRS, *CANONICAL_ARTIFACT_FILES):
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
        lease = self.state.get("lease") or {}
        if lease.get("active") and lease.get("owner_id") != self.owner_id and lease.get("expires_at_epoch", 0) > time.time():
            raise SystemExit(
                "Another prep-subject process holds an active destination lease. Wait for it to finish or resume "
                "after its lease expires."
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
        self.persist()

    def persist(self) -> None:
        if not self.state:
            return
        self.state["updated_at"] = utc_now()
        self.state["counts"] = _counts(self.state.get("chapters", []))
        _write_json_atomically(self.state_path, self.state)
        if self.is_r2:
            self._sync_workspace_to_r2()
            upload_r2_file(
                self.client,
                self.destination,
                self.state_path,
                destination_object_key(self.config, JOB_STATE_RELATIVE_PATH),
            )

    def _sync_workspace_to_r2(self) -> None:
        if not self.workspace_dir.exists():
            return
        for path in sorted(item for item in self.workspace_dir.rglob("*") if item.is_file()):
            relative = path.relative_to(self.subject_dir)
            upload_r2_file(
                self.client,
                self.destination,
                path,
                destination_object_key(self.config, relative),
            )

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
        self.persist()

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
        for chapter in self.state.get("chapters", []):
            valid = self._validate_success_artifacts(chapter)
            if chapter.get("state") == "succeeded":
                if valid:
                    reused.append(chapter["chapter_number"])
                else:
                    chapter["state"] = "pending"
                    chapter["successful_artifacts"] = []
                    chapter["proofreading"] = None
                    chapter["latest_error"] = {
                        "code": "checkpoint_artifacts_invalid",
                        "message": "Saved artifacts were missing or did not pass checksum validation; chapter will be reprocessed.",
                    }
                    chapter["updated_at"] = utc_now()
            elif valid:
                chapter["state"] = "succeeded"
                chapter["successful_artifacts"] = self._expected_artifact_records(chapter)
                chapter["proofreading"] = self._reconciled_proofreading_summary(chapter)
                chapter["latest_error"] = None
                chapter["updated_at"] = utc_now()
                reused.append(chapter["chapter_number"])
        self.persist()
        return reused

    def _expected_artifact_paths(self, chapter: dict[str, Any]) -> list[Path]:
        number = int(chapter["chapter_number"])
        text_name = chapter_output_filename(self.config, number, ".txt")
        metadata_name = chapter_output_filename(self.config, number, ".json")
        stem = Path(text_name).stem
        return [
            self.paths["chapter_msword"] / chapter_output_filename(self.config, number, ".docx"),
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
            metadata = _read_json(paths[3], "Checkpointed chapter metadata")
            details = _read_json(paths[5], "Checkpointed proofreading details")
            text_sha = _sha256(paths[2])
            return (
                metadata["integrity"]["artifacts"]["text"]["value"] == text_sha
                and details["canonical_corrected"]["text_sha256"] == text_sha
                and details.get("status") == "succeeded"
            )
        except (KeyError, OSError, SystemExit, TypeError):
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
        chapter["proofreading"] = result
        self.persist()

    def mark_chapter_failure(self, chapter: dict[str, Any], exc: BaseException) -> None:
        chapter["state"] = "failed"
        chapter["attempt_count"] += 1
        chapter["updated_at"] = utc_now()
        chapter["latest_error"] = _safe_error(exc)
        self.persist()

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
        write_proofreading_manifest(self.paths, self.config["_proofreading_config"], proofread)
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
        self.state["state"] = "succeeded"
        self.state["publication"]["state"] = "succeeded"
        if self.overwrite:
            if is_local(self.destination):
                self.state["publication"]["semantic_invalidation"] = invalidate_local_semantic_artifacts(self.subject_dir)
            else:
                self.state["publication"]["semantic_invalidation"] = invalidate_r2_semantic_artifacts(self.config, self.client)
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
            upload_r2_file(self.client, self.destination, path, key)

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
            "config_path": str(config_path) if config_path else None,
            "destination_backend": self.destination.get("backend", "local"),
            "failure_stage": "proofreading" if status == "incomplete" else ("global" if failure else None),
            "failure": failure,
            "counts": self.state["counts"],
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
                upload_r2_file(
                    self.client,
                    self.destination,
                    path,
                    destination_object_key(self.config, PREP_REPORT_RELATIVE_DIR / path.name),
                )
        self.persist()
        return references

    def close(self) -> None:
        if self.state and self.state.get("lease", {}).get("owner_id") == self.owner_id:
            self.state["lease"] = self.state.get("lease", {}) | {"active": False, "released_at": utc_now()}
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
        f"- Counts: succeeded `{report['counts']['succeeded']}`, failed `{report['counts']['failed']}`, pending `{report['counts']['pending']}`",
    ]
    if report["failure"]:
        lines.extend(["", "## Failure", "", f"- {report['failure']['code']}: {report['failure']['message']}"])
    lines.extend(["", "## Chapters", "", "| Chapter | State | Attempts | Outcome |", "| --- | --- | ---: | --- |"])
    lines.extend(
        f"| {chapter['chapter_number']} | {chapter['state']} | {chapter['attempt_count']} | {chapter['outcome']} |"
        for chapter in report["chapters"]
    )
    return "\n".join(lines) + "\n"


def _is_global_proofreading_failure(exc: ProofreadingError) -> bool:
    return exc.code in {"missing_credentials", "missing_dependency"}


def validate_generate_chunks_gate(config: dict[str, Any], source_subject: Path, candidate_manifest: dict[str, Any], r2_client=None) -> None:
    """Require a completed prep checkpoint before semantic output can mutate.

    The candidate manifest is already parsed here, but no chunk directory has
    been created or deleted.  This is intentionally usable for both local and
    R2 sources so an incomplete overwrite cannot erase previously generated
    chunks.
    """
    source = config["source"]
    state_path = Path(source_subject) / JOB_STATE_RELATIVE_PATH
    if is_r2(source):
        client = r2_client or R2StorageClient.from_env()
        key = subject_artifact_object_key(source, JOB_STATE_RELATIVE_PATH)
        if not client.exists(source["bucket"], key):
            raise SystemExit("generate-chunks requires a completed prep-subject job state; no checkpoint was found.")
        client.download_file(source["bucket"], key, state_path)
    elif not state_path.is_file():
        raise SystemExit("generate-chunks requires a completed prep-subject job state; no checkpoint was found.")
    state = _read_json(state_path, "Prep-subject job state")
    if state.get("schema_version") != CHECKPOINT_SCHEMA_VERSION or state.get("state") != "succeeded":
        raise SystemExit(
            "generate-chunks refuses prepared content while the latest prep-subject job is not succeeded. "
            "Use gurubodh prep-subject --resume to complete or recover the preparation job first."
        )
    publication = state.get("publication") or {}
    canonical = publication.get("canonical_manifest") or {}
    if canonical.get("sha256") != candidate_manifest.get("sha256"):
        raise SystemExit(
            "generate-chunks refuses the candidate manifest because it does not match the completed prep-subject checkpoint."
        )
    checkpoint_chapters = state.get("chapters")
    if not isinstance(checkpoint_chapters, list) or any(chapter.get("state") != "succeeded" for chapter in checkpoint_chapters):
        raise SystemExit("generate-chunks requires every completed checkpoint chapter to be succeeded.")
    expected_numbers = [chapter.get("chapter_number") for chapter in checkpoint_chapters]
    manifest_numbers = [chapter.get("generated_chapter_number") for chapter in candidate_manifest.get("chapters", [])]
    if expected_numbers != manifest_numbers or canonical.get("chapter_numbers") != expected_numbers:
        raise SystemExit(
            "generate-chunks refuses the candidate manifest because its chapters do not match the completed checkpoint set."
        )
    checkpoint_keys = {
        chapter["chapter_number"]: (chapter.get("proofreading") or {}).get("canonical_content_key")
        for chapter in checkpoint_chapters
    }
    if any(checkpoint_keys.get(chapter["generated_chapter_number"]) != chapter.get("content_key") for chapter in candidate_manifest["chapters"]):
        raise SystemExit(
            "generate-chunks refuses the candidate manifest because its chapter identities do not match the completed checkpoint."
        )


def run_resumable_prep_job(
    context,
    config: dict[str, Any],
    entry_point: str,
    overwrite: bool,
    resume: bool,
    config_path: Path | None,
    prepare_full_subject: Callable[[Path, Path, Path, Callable[..., None]], dict[str, Any]],
    r2_client=None,
) -> dict[str, Any]:
    """Run either preparation pipeline with checkpointed proof-reading."""
    manager = PrepCheckpointManager(config, resume, overwrite, r2_client=r2_client)
    reused: list[str] = []
    attempted: list[str] = []
    try:
        manager.open()
        source_path = manager.materialize_source()
        outcome = manager.begin(_sha256(source_path))
        if outcome == "already_complete":
            print("prep-subject already complete; the compatible checkpoint is succeeded. No Gemini requests were made.")
            return {"status": "succeeded", "already_complete": True, "counts": manager.state["counts"]}

        paths = manager.paths
        ensure_job_dirs(paths)
        result = manager.state.get("preparation") or {}
        if not manager.state.get("chapters"):
            try:
                print("[prepare] Building the full-subject source and chapter snapshots in the checkpoint workspace.")
                result = prepare_full_subject(
                    source_path,
                    paths["full_subject"] / full_subject_output_filename(config, ".docx"),
                    paths["full_subject"] / full_subject_output_filename(config, ".txt"),
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
            except BaseException as exc:
                manager.mark_global_failure(exc)
                manager.write_report(config_path, entry_point, "failed", _safe_error(exc), reused, attempted)
                raise

        reused = manager.reconcile_successes()
        consecutive_infrastructure_failures = 0
        proofreader = GeminiProofreader(config["_proofreading_config"])
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
            raise
        manager.write_report(config_path, entry_point, "succeeded", None, reused, attempted)
        return {"status": "succeeded", "already_complete": False, "counts": manager.state["counts"]}
    finally:
        manager.close()
