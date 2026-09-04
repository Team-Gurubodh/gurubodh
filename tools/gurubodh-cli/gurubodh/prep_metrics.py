"""Invocation-scoped metrics for the resumable prep-subject workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from gurubodh.contracts import R2Client
from gurubodh.storage import upload_r2_file


R2_UPLOAD_BREAKDOWN_DEFINITIONS = {
    "checkpoint_source_snapshots": (
        "Initial retained source snapshots committed with the chapter plan."
    ),
    "checkpoint_chapter_artifacts": (
        "New canonical text, metadata, diff, and provenance artifacts from "
        "successful chapters."
    ),
    "checkpoint_state_commits": (
        "Job-state JSON commits for checkpoint, publication, workspace, or "
        "advisory-lease transitions."
    ),
    "checkpoint_state_archives": (
        "Prior job-state archives created by --overwrite."
    ),
    "canonical_publication_artifacts": (
        "Final canonical prep artifacts and readiness manifests published "
        "from the workspace."
    ),
}


def _attempt_counters() -> dict[str, int]:
    return {"attempts_total": 0, "attempts_succeeded": 0, "attempts_failed": 0}


class PrepMetrics:
    """Own metric transitions without owning checkpoint or publication state."""

    def __init__(self, track_r2: bool) -> None:
        self.values = {
            "gemini_generate_content_requests": _attempt_counters(),
            "r2_object_upload_requests": (
                {
                    **_attempt_counters(),
                    "breakdown": {
                        category: _attempt_counters()
                        for category in R2_UPLOAD_BREAKDOWN_DEFINITIONS
                    },
                }
                if track_r2
                else None
            ),
        }

    def record_proofreading_success(self, result: dict[str, Any]) -> None:
        attempts = int(result.get("attempts", 0))
        succeeded = int(result.get("successful_request_attempts", attempts))
        self._record_proofreading_attempts(attempts, succeeded)

    def record_proofreading_failure(self, exc: BaseException) -> None:
        self._record_proofreading_attempts(
            int(getattr(exc, "request_attempts", 0)),
            int(getattr(exc, "successful_request_attempts", 0)),
        )

    def _record_proofreading_attempts(self, attempts: int, succeeded: int) -> None:
        succeeded = min(max(succeeded, 0), attempts)
        counters = self.values["gemini_generate_content_requests"]
        counters["attempts_total"] += attempts
        counters["attempts_succeeded"] += succeeded
        counters["attempts_failed"] += attempts - succeeded

    def upload(
        self,
        client: R2Client,
        destination: dict[str, Any],
        path: Path,
        key: str,
        *,
        category: str | None = None,
        count: bool = True,
    ) -> None:
        counters = self.values["r2_object_upload_requests"]
        if count and counters is not None:
            if category not in R2_UPLOAD_BREAKDOWN_DEFINITIONS:
                raise RuntimeError(
                    f"Missing or invalid R2 upload metric category: {category!r}"
                )
            counters["attempts_total"] += 1
            counters["breakdown"][category]["attempts_total"] += 1
        try:
            upload_r2_file(client, destination, path, key)
        except BaseException:
            if count and counters is not None:
                counters["attempts_failed"] += 1
                counters["breakdown"][category]["attempts_failed"] += 1
            raise
        if count and counters is not None:
            counters["attempts_succeeded"] += 1
            counters["breakdown"][category]["attempts_succeeded"] += 1

    def report(self) -> dict[str, Any]:
        return {
            "gemini_generate_content_requests": {
                **self.values["gemini_generate_content_requests"],
                "definition": (
                    "Actual Gemini generate_content request attempts in this "
                    "invocation, including retries and terminal failures; excludes "
                    "reused checkpoints and local pacing waits."
                ),
            },
            "r2_object_upload_requests": (
                {
                    **{
                        key: value
                        for key, value in self.values[
                            "r2_object_upload_requests"
                        ].items()
                        if key != "breakdown"
                    },
                    "definition": (
                        "R2 object-upload request attempts in this invocation "
                        "caused by checkpoint commits or canonical prep "
                        "publication; excludes reads, lists, deletes, and "
                        "audit-report uploads."
                    ),
                    "breakdown": {
                        category: {
                            **counters,
                            "definition": R2_UPLOAD_BREAKDOWN_DEFINITIONS[category],
                        }
                        for category, counters in self.values[
                            "r2_object_upload_requests"
                        ]["breakdown"].items()
                    },
                }
                if self.values["r2_object_upload_requests"] is not None
                else None
            ),
        }

    def print_summary(self, progress: Callable[[str], None] = print) -> None:
        gemini = self.values["gemini_generate_content_requests"]
        summary = (
            "prep-subject metrics: Gemini generate_content attempts "
            f"{gemini['attempts_total']} ({gemini['attempts_succeeded']} "
            f"succeeded, {gemini['attempts_failed']} failed)"
        )
        r2 = self.values["r2_object_upload_requests"]
        if r2 is not None:
            summary += (
                "; R2 object-upload attempts "
                f"{r2['attempts_total']} ({r2['attempts_succeeded']} succeeded, "
                f"{r2['attempts_failed']} failed)"
            )
        progress(summary + ".")
