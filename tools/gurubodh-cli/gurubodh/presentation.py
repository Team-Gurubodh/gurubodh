"""Small, stateless terminal presentation helpers for operator commands."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
import os
import sys
from typing import Any


_GREEN = "\033[32m"
_RED = "\033[31m"
_RESET = "\033[0m"


def bounded_reason(error: BaseException) -> str:
    """Return one safe, single-line reason suitable for terminal output."""
    return " ".join(str(error).split())[:500] or error.__class__.__name__


def artifact_location(reference: Mapping[str, Any] | None) -> str | None:
    """Render an existing local or R2 artifact reference without inventing one."""
    if not reference:
        return None
    if reference.get("backend") == "local":
        return reference.get("path")
    bucket = reference.get("bucket")
    key = reference.get("key") or reference.get("prefix")
    if bucket and key:
        return f"r2://{bucket}/{str(key).lstrip('/')}"
    return reference.get("url")


class CommandPresentation:
    """Format command facts supplied by workflows; owns no workflow state."""

    def __init__(
        self,
        command: str,
        progress: Callable[[str], None] = print,
        *,
        color: bool | None = None,
    ) -> None:
        self.command = command
        self.progress = progress
        self.color = self._detect_color(progress) if color is None else color

    @staticmethod
    def _detect_color(progress: Callable[[str], None]) -> bool:
        return (
            progress is print
            and "NO_COLOR" not in os.environ
            and bool(getattr(sys.stdout, "isatty", lambda: False)())
        )

    def _emit(self, message: str, color: str | None = None) -> None:
        if color and self.color:
            message = f"{color}{message}{_RESET}"
        self.progress(message)

    def stage(self, stage: str, message: str) -> None:
        self._emit(f"[{self.command} {stage}] {message}")

    def chapter(
        self,
        chapter: str | int,
        message: str,
        *,
        position: int | None = None,
        total: int | None = None,
    ) -> None:
        count = f" {position:02d}/{total:02d}" if position is not None and total else ""
        self._emit(f"[{self.command}{count} chapter {chapter}] {message}")

    def failure(
        self,
        stage: str,
        error: BaseException,
        *,
        chapter: str | int | None = None,
        position: int | None = None,
        total: int | None = None,
    ) -> None:
        reason = bounded_reason(error)
        if chapter is None:
            message = f"[{self.command} {stage}] failed: {reason}"
        else:
            count = (
                f" {position:02d}/{total:02d}"
                if position is not None and total
                else ""
            )
            message = (
                f"[{self.command}{count} chapter {chapter} {stage}] failed: {reason}"
            )
        self._emit(message, _RED)

    def summary(
        self,
        outcome: str,
        detail: str,
        lines: Iterable[str],
        locations: Iterable[tuple[str, str | None]] = (),
    ) -> None:
        color = _GREEN if outcome == "succeeded" else _RED
        suffix = f" — {detail}" if detail else ""
        self._emit(f"{self.command}: {outcome}{suffix}", color)
        for line in lines:
            self._emit(line)
        for label, location in locations:
            if location:
                self._emit(f"{label}: {location}")


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    noun = singular if count == 1 else (plural_form or singular + "s")
    return f"{count} {noun}"


def publication_location(publication: Mapping[str, Any]) -> str | None:
    if publication.get("status") != "succeeded":
        return None
    if publication.get("backend") == "local":
        return publication.get("output_path")
    bucket = publication.get("bucket")
    prefix = publication.get("prefix")
    if bucket and prefix:
        return f"r2://{bucket}/{str(prefix).lstrip('/')}"
    return None


def present_derived_summary(
    presentation: CommandPresentation,
    *,
    outcome: str,
    generation: Any,
    source_count: int | None,
    publication: Mapping[str, Any],
    report_references: Mapping[str, Any] | None,
    failure_stage: str | None = None,
) -> None:
    """Render common derived-command outcomes from lifecycle-owned facts."""
    succeeded = getattr(generation, "processed_chapter_count", 0)
    failed = getattr(generation, "failed_chapter_count", None)
    if failed is None:
        failed = sum(
            1
            for chapter in getattr(generation, "chapters", ())
            if getattr(getattr(chapter, "status", None), "value", None) == "failed"
        )
    skipped = getattr(generation, "skipped_chapter_count", 0)
    pending = (
        max(source_count - succeeded - failed - skipped, 0)
        if source_count is not None
        else None
    )
    unit = "DOCX generation" if presentation.command == "generate-docx" else "Chunk generation"

    lines: list[str] = []
    if source_count is None:
        lines.append(f"{unit}: counts unavailable; source validation did not complete.")
    else:
        lines.append(
            f"{unit}: {plural(succeeded, 'chapter')} succeeded, {failed} failed."
        )
        if skipped:
            lines.append(f"Skipped: {plural(skipped, 'chapter')} not selected.")
        if pending:
            lines.append(f"Pending/not attempted: {plural(pending, 'chapter')}.")

    publication_status = publication.get("status", "not_started")
    if publication_status == "succeeded":
        lines.append("Final publication: succeeded; output is ready.")
    elif publication_status in {"publishing", "failed"}:
        lines.append("Final publication: failed; output is not ready.")
    else:
        lines.append("Final publication: not performed; processing did not complete.")

    if outcome == "succeeded":
        detail = f"{plural(succeeded, 'chapter')} processed"
    elif failed:
        detail = f"{plural(failed, 'chapter')} failed"
    else:
        detail = f"{(failure_stage or 'command').replace('_', ' ')} failed"

    locations = [("Output", publication_location(publication))]
    if report_references:
        locations.extend(
            (
                f"Report ({kind})",
                artifact_location(report_references.get(kind)),
            )
            for kind in ("json", "markdown")
        )
    presentation.summary(outcome, detail, lines, locations)


def present_prep_summary(
    presentation: CommandPresentation,
    *,
    outcome: str,
    state: Mapping[str, Any] | None,
    metrics: Mapping[str, Any],
    reused_count: int,
    report_references: Mapping[str, Any] | None,
    artifact_root: str | None = None,
    failure_stage: str | None = None,
) -> None:
    """Render prep-subject facts without deriving or storing workflow state."""
    lines: list[str] = []
    counts = state.get("counts") if state else None
    if counts is None:
        succeeded = failed = pending = None
        lines.append("Proofreading: chapter counts unavailable.")
    else:
        succeeded = int(counts["succeeded"])
        failed = int(counts["failed"])
        pending = int(counts["pending"])
        lines.append(
            f"Proofreading: {plural(succeeded, 'chapter')} succeeded, {failed} failed."
        )
        if reused_count:
            lines.append(
                f"Reused: {plural(reused_count, 'successful chapter checkpoint')}."
            )
        if pending:
            lines.append(f"Pending/not attempted: {plural(pending, 'chapter')}.")

    gemini = metrics.get("gemini_generate_content_requests")
    if gemini is not None:
        lines.append(
            "Gemini requests: "
            f"{gemini['attempts_succeeded']} completed, "
            f"{gemini['attempts_failed']} request failures."
        )

    r2 = metrics.get("r2_object_upload_requests")
    if r2 is not None:
        breakdown = r2["breakdown"]
        canonical = breakdown["canonical_publication_artifacts"]
        checkpoint_categories = (
            "checkpoint_source_snapshots",
            "checkpoint_chapter_artifacts",
            "checkpoint_state_commits",
            "checkpoint_state_archives",
        )
        checkpoint_succeeded = sum(
            breakdown[name]["attempts_succeeded"] for name in checkpoint_categories
        )
        checkpoint_failed = sum(
            breakdown[name]["attempts_failed"] for name in checkpoint_categories
        )
        lines.append(
            "R2 upload operations: "
            f"{checkpoint_succeeded} succeeded, {checkpoint_failed} failed "
            "(checkpoint data; excludes audit reports)."
        )
        if canonical["attempts_total"]:
            lines.append(
                "R2 canonical-publication upload operations: "
                f"{canonical['attempts_succeeded']} succeeded, "
                f"{canonical['attempts_failed']} failed "
                "(excludes audit reports)."
            )

    publication_status = (
        (state.get("publication") or {}).get("state", "not_ready")
        if state
        else "not_ready"
    )
    if publication_status == "succeeded":
        lines.append("Final publication: succeeded; canonical artifacts are ready.")
    elif publication_status == "publishing":
        lines.append(
            "Final publication: failed; canonical artifacts are not confirmed ready."
        )
    else:
        reason = "preparation incomplete" if outcome == "incomplete" else "processing failed"
        lines.append(f"Final publication: not performed; {reason}.")

    if outcome == "succeeded":
        detail = f"{plural(succeeded or 0, 'chapter')} prepared"
    elif outcome == "incomplete" and failed:
        detail = f"{plural(failed, 'chapter')} failed"
    elif outcome == "incomplete" and pending:
        detail = f"{plural(pending, 'chapter')} pending"
    else:
        detail = f"{(failure_stage or 'command').replace('_', ' ')} failed"

    locations = [("Output", artifact_root if publication_status == "succeeded" else None)]
    if report_references:
        locations.extend(
            (
                f"Report ({kind})",
                artifact_location(report_references.get(kind)),
            )
            for kind in ("json", "markdown")
        )
    presentation.summary(outcome, detail, lines, locations)


def present_lab_summary(
    presentation: CommandPresentation,
    *,
    outcome: str,
    failure_stage: str | None,
    source_validated: bool,
    proofreading_succeeded: bool,
    response: Mapping[str, Any] | None,
    error: BaseException | None,
    run_directory: str,
    report_reference: Mapping[str, Any] | None,
    output_available: bool,
) -> None:
    lines: list[str] = []
    if proofreading_succeeded:
        lines.append("Proofreading: 1 document succeeded, 0 failed.")
    elif failure_stage == "proofreading":
        lines.append("Proofreading: 0 documents succeeded, 1 failed.")
    elif source_validated:
        lines.append("Proofreading: not attempted or not completed.")
    else:
        lines.append("Proofreading: not attempted; source validation failed.")

    attempts = None
    completed = None
    if response is not None:
        attempts = int(response.get("attempts", 0))
        completed = int(response.get("successful_request_attempts", attempts))
    elif error is not None and hasattr(error, "request_attempts"):
        attempts = int(getattr(error, "request_attempts", 0))
        completed = int(getattr(error, "successful_request_attempts", 0))
    if attempts is not None:
        lines.append(
            f"Gemini requests: {completed} completed, "
            f"{attempts - completed} request failures."
        )

    if output_available:
        lines.append("Local output: succeeded; non-canonical lab output is available.")
    else:
        lines.append("Local output: not available; the lab run did not complete.")

    if outcome == "succeeded":
        detail = "proofreading completed"
    else:
        detail = f"{(failure_stage or 'command').replace('_', ' ')} failed"
    presentation.summary(
        outcome,
        detail,
        lines,
        (
            ("Output", run_directory if output_available else None),
            ("Run directory", run_directory),
            ("Report", artifact_location(report_reference)),
        ),
    )
