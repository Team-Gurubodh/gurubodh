"""Advisory single-writer coordination for prep-subject.

These guards are deliberately separate from checkpoint state transitions.  The
R2 lease remains advisory and is not claimed as distributed mutual exclusion.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Callable, Protocol

from gurubodh.canonical_release import RUN_STATE_RELATIVE_DIR
from gurubodh.contracts import PrepCheckpointState
from gurubodh.errors import ProcessingError
from gurubodh.time_utils import utc_now


LEASE_SECONDS = 120


class PrepCoordinator(Protocol):
    owner_id: str

    def acquire(self) -> None: ...

    def validate_loaded_state(self, state: PrepCheckpointState) -> None: ...

    def claim(self, state: PrepCheckpointState) -> None: ...

    def heartbeat(self, state: PrepCheckpointState) -> None: ...

    def release(self, state: PrepCheckpointState) -> bool: ...

    def close(self) -> None: ...


class AdvisoryLeaseCoordinator:
    """Own the lease sub-record without persisting checkpoint state."""

    def __init__(
        self,
        *,
        owner_id: str | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.owner_id = owner_id or str(uuid.uuid4())
        self.clock = clock

    def acquire(self) -> None:
        return None

    def validate_loaded_state(self, state: PrepCheckpointState) -> None:
        lease = state.get("lease") or {}
        if (
            lease.get("active")
            and lease.get("owner_id") != self.owner_id
            and lease.get("expires_at_epoch", 0) > self.clock()
        ):
            raise ProcessingError(
                "Another prep-subject process appears to hold an active "
                "destination advisory lease. This is not reliable mutual "
                "exclusion; wait for it to finish or resume after its advisory "
                "lease expires."
            )

    def claim(self, state: PrepCheckpointState) -> None:
        state["lease"] = {
            "owner_id": self.owner_id,
            "active": True,
            "heartbeat_at": utc_now(),
            "expires_at_epoch": int(self.clock() + LEASE_SECONDS),
        }

    def heartbeat(self, state: PrepCheckpointState) -> None:
        self.claim(state)

    def release(self, state: PrepCheckpointState) -> bool:
        lease = state.get("lease", {})
        if lease.get("owner_id") != self.owner_id:
            return False
        state["lease"] = lease | {"active": False, "released_at": utc_now()}
        return True

    def close(self) -> None:
        return None


class LocalAdvisoryCoordinator(AdvisoryLeaseCoordinator):
    """Filesystem lock plus the shared persisted advisory-lease record."""

    def __init__(
        self,
        subject_dir: Path,
        *,
        owner_id: str | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        super().__init__(owner_id=owner_id, clock=clock)
        self.lock_path = subject_dir / RUN_STATE_RELATIVE_DIR / "job.lock"
        self.lock_created = False

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                descriptor = os.open(
                    self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )
            except FileExistsError as exc:
                if self.clock() - self.lock_path.stat().st_mtime > LEASE_SECONDS:
                    self.lock_path.unlink(missing_ok=True)
                    continue
                raise ProcessingError(
                    "Another prep-subject writer appears active for "
                    f"{self.lock_path.parents[2]}; the local advisory lock is "
                    "not reliable mutual exclusion. Wait for it to finish, or "
                    "use --resume after an interrupted writer's advisory lock "
                    "has expired."
                ) from exc
            os.write(descriptor, self.owner_id.encode("utf-8"))
            os.close(descriptor)
            self.lock_created = True
            return

    def heartbeat(self, state: PrepCheckpointState) -> None:
        super().heartbeat(state)
        if self.lock_created:
            os.utime(self.lock_path, None)

    def close(self) -> None:
        if self.lock_created:
            self.lock_path.unlink(missing_ok=True)
            self.lock_created = False


class R2AdvisoryCoordinator(AdvisoryLeaseCoordinator):
    """In-memory lease transitions persisted only by explicit checkpoints."""


def create_prep_coordinator(
    *,
    is_r2: bool,
    subject_dir: Path,
    owner_id: str | None = None,
    clock: Callable[[], float] = time.time,
) -> PrepCoordinator:
    if is_r2:
        return R2AdvisoryCoordinator(owner_id=owner_id, clock=clock)
    return LocalAdvisoryCoordinator(
        subject_dir,
        owner_id=owner_id,
        clock=clock,
    )
