"""Persistence ports and local/R2 stores for prep-subject checkpoints."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from gurubodh.canonical_release import JOB_STATE_RELATIVE_PATH
from gurubodh.contracts import PrepCheckpointState, PrepSubjectJob, R2Client
from gurubodh.errors import SourceValidationError
from gurubodh.prep_metrics import PrepMetrics
from gurubodh.schema_validation import validated_artifact_json
from gurubodh.storage import (
    R2StorageClient,
    destination_object_key,
    is_r2,
    preflight_relative_paths,
    subject_artifact_object_key,
    subject_artifact_prefix,
)
from gurubodh.time_utils import timestamp_for_filename


WORK_RELATIVE_DIR = Path(".work") / "prep-subject"


def workspace_relative_path(job_id: str) -> Path:
    return WORK_RELATIVE_DIR / job_id


def write_json_atomically(
    path: Path,
    payload: dict[str, Any],
    artifact_name: str | None = None,
) -> None:
    """Write a JSON object through a same-directory atomic replacement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    serialized = (
        validated_artifact_json(payload, artifact_name, path)
        if artifact_name
        else json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )
    temporary.write_text(serialized, encoding="utf-8")
    os.replace(temporary, path)


def read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceValidationError(
            f"{label} is missing or malformed: {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SourceValidationError(f"{label} must be a JSON object: {path}")
    return value


class CheckpointStore(Protocol):
    """Backend-neutral persistence required by checkpoint state transitions."""

    destination: dict[str, Any]
    subject_dir: Path
    state_path: Path
    is_r2: bool
    client: R2Client | None

    def load(self) -> PrepCheckpointState | None: ...

    def restore_workspace(self, relative_path: Path) -> None: ...

    def commit(
        self,
        state: PrepCheckpointState,
        checkpoint_artifacts: list[Path] | None = None,
        checkpoint_artifact_category: str | None = None,
        count_r2_uploads: bool = True,
    ) -> None: ...

    def archive_prior_state(
        self, state: PrepCheckpointState, workspace_relative: Path
    ) -> None: ...

    def prep_artifacts_exist(self) -> bool: ...

    def discard_workspace_path(self, relative_path: Path) -> None: ...

    def remove_workspace(self, relative_path: Path) -> None: ...

    def close(self) -> None: ...


class LocalCheckpointStore:
    """Atomic filesystem implementation of the checkpoint store contract."""

    is_r2 = False
    client = None

    def __init__(self, config: PrepSubjectJob, metrics: PrepMetrics) -> None:
        self.config = config
        self.metrics = metrics
        self.destination = config["destination"]
        self.subject_dir = (
            Path(self.destination["root_dir"]).expanduser()
            / self.destination["subject_dir"]
        )
        self.state_path = self.subject_dir / JOB_STATE_RELATIVE_PATH

    def load(self) -> PrepCheckpointState | None:
        self.subject_dir.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            return None
        try:
            return PrepCheckpointState.from_payload(
                read_json_object(self.state_path, "Prep-subject job state")
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceValidationError(
                f"Unsupported or malformed prep-subject checkpoint state: {exc}"
            ) from exc

    def restore_workspace(self, relative_path: Path) -> None:
        del relative_path

    def commit(
        self,
        state: PrepCheckpointState,
        checkpoint_artifacts: list[Path] | None = None,
        checkpoint_artifact_category: str | None = None,
        count_r2_uploads: bool = True,
    ) -> None:
        del checkpoint_artifacts, checkpoint_artifact_category, count_r2_uploads
        write_json_atomically(
            self.state_path,
            state.to_payload(),
            "prep-subject job state",
        )

    def archive_prior_state(
        self, state: PrepCheckpointState, workspace_relative: Path
    ) -> None:
        archive_name = (
            f"{timestamp_for_filename()}-{state.get('job_id', 'unknown')}"
            "-job-state.json"
        )
        archive = (
            self.subject_dir
            / JOB_STATE_RELATIVE_PATH.parent
            / "archive"
            / archive_name
        )
        # Archives preserve earlier checkpoint contracts verbatim.
        write_json_atomically(archive, state.to_payload())
        self.remove_workspace(workspace_relative)

    def prep_artifacts_exist(self) -> bool:
        return any(
            (self.subject_dir / relative).exists()
            for relative in preflight_relative_paths("prep-subject")
        )

    def discard_workspace_path(self, relative_path: Path) -> None:
        target = self.subject_dir / relative_path
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()

    def remove_workspace(self, relative_path: Path) -> None:
        self.discard_workspace_path(relative_path)

    def close(self) -> None:
        return None


class R2CheckpointStore:
    """R2 implementation that commits artifacts before the job-state record."""

    is_r2 = True

    def __init__(
        self,
        config: PrepSubjectJob,
        metrics: PrepMetrics,
        r2_client: R2Client | None = None,
    ) -> None:
        self.config = config
        self.metrics = metrics
        self.destination = config["destination"]
        self.client = r2_client or R2StorageClient.from_env()
        self._temporary = tempfile.TemporaryDirectory(
            prefix="gurubodh-prep-checkpoint-"
        )
        self.subject_dir = (
            Path(self._temporary.name) / self.destination["subject_dir"]
        )
        self.state_path = self.subject_dir / JOB_STATE_RELATIVE_PATH

    def load(self) -> PrepCheckpointState | None:
        state_key = destination_object_key(self.config, JOB_STATE_RELATIVE_PATH)
        if not self.client.exists(self.destination["bucket"], state_key):
            return None
        self.client.download_file(
            self.destination["bucket"], state_key, self.state_path
        )
        try:
            return PrepCheckpointState.from_payload(
                read_json_object(self.state_path, "Prep-subject job state")
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceValidationError(
                f"Unsupported or malformed prep-subject checkpoint state: {exc}"
            ) from exc

    def restore_workspace(self, relative_path: Path) -> None:
        prefix = subject_artifact_object_key(self.destination, relative_path) + "/"
        subject_prefix = subject_artifact_prefix(self.destination)
        for key in self.client.list_keys(self.destination["bucket"], prefix):
            relative = PurePosixPath(key.removeprefix(subject_prefix))
            if relative.is_absolute() or ".." in relative.parts:
                raise SourceValidationError(
                    "Checkpoint workspace key escapes the destination subject prefix."
                )
            self.client.download_file(
                self.destination["bucket"],
                key,
                self.subject_dir / Path(*relative.parts),
            )

    def commit(
        self,
        state: PrepCheckpointState,
        checkpoint_artifacts: list[Path] | None = None,
        checkpoint_artifact_category: str | None = None,
        count_r2_uploads: bool = True,
    ) -> None:
        write_json_atomically(
            self.state_path,
            state.to_payload(),
            "prep-subject job state",
        )
        for path in checkpoint_artifacts or []:
            relative = path.relative_to(self.subject_dir)
            self.metrics.upload(
                self.client,
                self.destination,
                path,
                destination_object_key(self.config, relative),
                category=checkpoint_artifact_category,
                count=count_r2_uploads,
            )
        # Job state is the checkpoint commit record and is always uploaded last.
        self.metrics.upload(
            self.client,
            self.destination,
            self.state_path,
            destination_object_key(self.config, JOB_STATE_RELATIVE_PATH),
            category="checkpoint_state_commits",
            count=count_r2_uploads,
        )

    def archive_prior_state(
        self, state: PrepCheckpointState, workspace_relative: Path
    ) -> None:
        archive_name = (
            f"{timestamp_for_filename()}-{state.get('job_id', 'unknown')}"
            "-job-state.json"
        )
        archive_relative = (
            JOB_STATE_RELATIVE_PATH.parent / "archive" / archive_name
        )
        archive_path = self.subject_dir / archive_relative
        write_json_atomically(archive_path, state.to_payload())
        self.metrics.upload(
            self.client,
            self.destination,
            archive_path,
            destination_object_key(self.config, archive_relative),
            category="checkpoint_state_archives",
        )
        self.remove_workspace(workspace_relative)

    def prep_artifacts_exist(self) -> bool:
        for relative in preflight_relative_paths("prep-subject"):
            key = destination_object_key(self.config, relative)
            if relative.suffix:
                if self.client.exists(self.destination["bucket"], key):
                    return True
            elif self.client.list_keys(self.destination["bucket"], key + "/"):
                return True
        return False

    def discard_workspace_path(self, relative_path: Path) -> None:
        local = self.subject_dir / relative_path
        if local.is_dir():
            shutil.rmtree(local)
        elif local.exists():
            local.unlink()
        self.client.delete_prefix(
            self.destination["bucket"],
            subject_artifact_object_key(self.destination, relative_path) + "/",
        )

    def remove_workspace(self, relative_path: Path) -> None:
        self.discard_workspace_path(relative_path)

    def close(self) -> None:
        self._temporary.cleanup()


def create_checkpoint_store(
    config: PrepSubjectJob,
    metrics: PrepMetrics,
    r2_client: R2Client | None = None,
) -> CheckpointStore:
    if is_r2(config["destination"]):
        return R2CheckpointStore(config, metrics, r2_client)
    return LocalCheckpointStore(config, metrics)
