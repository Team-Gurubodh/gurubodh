"""Small application orchestrator for resumable ``prep-subject`` jobs.

The public imports in this module are retained for pipeline compatibility.  The
checkpoint domain, stores, coordination, publication, and canonical release
gate live in independently testable modules.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from gurubodh.audit import bounded_failure, warn_audit_failure
from gurubodh.canonical_release import (
    CHECKPOINT_CONTRACT_VERSION,
    CHECKPOINT_SCHEMA_VERSION,
    JOB_STATE_RELATIVE_PATH,
    RUN_STATE_RELATIVE_DIR,
    validate_canonical_release_gate,
)
from gurubodh.contracts import ChapterStatus, PrepSubjectJob, Proofreader
from gurubodh.errors import ProcessingError
from gurubodh.legacy.font_detection import validate_supported_source_fonts
from gurubodh.paths import ensure_job_dirs
from gurubodh.pipelines.common import validate_and_split
from gurubodh.prep_checkpoint import (
    PrepCheckpointManager,
    compatibility_record_from_inputs as _compatibility_record_from_inputs,
    safe_config_inputs as _base_safe_config_inputs,
    sha256_file,
)
from gurubodh.prep_checkpoint_store import WORK_RELATIVE_DIR
from gurubodh.prep_subject_audit import (
    PREP_REPORT_RELATIVE_DIR,
    PrepSubjectAuditWriter,
)
from gurubodh.proofreading.artifacts import write_canonical_chapter_artifacts
from gurubodh.proofreading.errors import ProofreadingError
from gurubodh.proofreading.gemini import GeminiProofreader
from gurubodh.storage import destination_object_key, subject_artifact_prefix


INFRASTRUCTURE_FAILURE_CIRCUIT_BREAKER = 2


def _safe_config_inputs(config: PrepSubjectJob) -> dict[str, Any]:
    """Compatibility wrapper around the checkpoint-domain fingerprint input."""
    inputs = _base_safe_config_inputs(config)
    # Keep this public compatibility seam patchable by older focused tests.
    inputs["checkpoint_contract_version"] = CHECKPOINT_CONTRACT_VERSION
    return inputs


def compatibility_record(
    config: PrepSubjectJob, source_sha256: str
) -> dict[str, Any]:
    return _compatibility_record_from_inputs(
        _safe_config_inputs(config), source_sha256
    )


def _is_global_proofreading_failure(exc: ProofreadingError) -> bool:
    return exc.code in {"missing_credentials", "missing_dependency"}


def _write_prep_audit(
    manager: PrepCheckpointManager,
    project_root: Path,
    config_path: Path | None,
    entry_point: str,
    status: str,
    reused: list[str],
    attempted: list[str],
    *,
    failure_error: BaseException | None = None,
    failure_stage: str | None = None,
):
    """Write and optionally upload one prep audit at the application boundary."""
    try:
        manager.release_lease_for_audit()
        writer = PrepSubjectAuditWriter(
            project_root,
            manager.config,
            config_path,
            entry_point,
            manager.overwrite,
            manager.state.to_payload(),
            manager.subject_dir,
        )
        failure = (
            bounded_failure(failure_error, failure_stage or "unknown")
            if failure_error is not None
            else None
        )
        result = writer.write(
            status,
            failure,
            reused,
            attempted,
            manager.report_metrics(),
            CHECKPOINT_CONTRACT_VERSION,
        )
        manager.state["run_reports"].append(result.references)
        if manager.is_r2:
            for kind in ("json", "markdown"):
                path = result.paths[kind]
                manager.upload_audit_file(
                    path,
                    destination_object_key(
                        manager.config, PREP_REPORT_RELATIVE_DIR / path.name
                    ),
                )
        else:
            manager.persist()
        return result
    except BaseException as audit_error:
        if failure_error is None:
            raise
        warn_audit_failure("prep-subject", audit_error, failure_error)
        return None


def run_resumable_prep_job(
    config: PrepSubjectJob,
    entry_point: str,
    overwrite: bool,
    resume: bool,
    config_path: Path | None,
    prepare_source_docx: Callable[
        [Path, Path, Callable[..., None]], dict[str, Any]
    ],
    r2_client=None,
    context=None,
    *,
    proofreader: Proofreader | None = None,
    progress: Callable[[str], None] = print,
    clock: Callable[[], float] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Orchestrate preparation over narrow checkpoint and provider interfaces."""
    manager = PrepCheckpointManager(
        config,
        resume,
        overwrite,
        r2_client=r2_client,
        clock=clock or time.time,
        sleeper=sleeper or time.sleep,
        progress=progress,
    )
    project_root = Path(getattr(context, "root", Path.cwd()))
    reused: list[str] = []
    attempted: list[str] = []
    try:
        progress(
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
        outcome = manager.begin(sha256_file(source_path))
        if outcome == "already_complete":
            progress(
                "prep-subject already complete; the compatible checkpoint is "
                "succeeded. No Gemini requests were made."
            )
            _write_prep_audit(
                manager,
                project_root,
                config_path,
                entry_point,
                "succeeded",
                reused,
                attempted,
            )
            manager.print_metrics_summary()
            return {
                "status": "succeeded",
                "already_complete": True,
                "counts": manager.state["counts"],
                "metrics": manager.report_metrics(),
            }

        paths = manager.paths
        ensure_job_dirs(paths)
        if not manager.state.get("chapters"):
            try:
                progress(
                    "[prepare] Building chapter source snapshots from the "
                    "configured DOCX in the checkpoint workspace."
                )
                transient_dir = manager.workspace_dir / ".transient"
                transient_dir.mkdir(parents=True, exist_ok=True)
                preparation = prepare_source_docx(
                    source_path,
                    transient_dir / "prepared-source.docx",
                    lambda *_: manager.heartbeat(),
                )
                split_outputs = validate_and_split(
                    config,
                    preparation,
                    paths,
                    progress=lambda *_: manager.heartbeat(),
                )
                manager.set_chapter_plan(
                    sorted(
                        paths["unmodified_source_text"].glob(
                            "*_unmodified_source.txt"
                        )
                    ),
                    {
                        "total_nodes": preparation.get("total_nodes", 0),
                        "total_chars": preparation.get("total_chars", 0),
                        "converter_counts": preparation.get(
                            "converter_counts", {}
                        ),
                        "chapters_detected": len(split_outputs),
                    },
                )
                manager.discard_transient_preparation()
            except BaseException as exc:
                manager.mark_global_failure(exc)
                _write_prep_audit(
                    manager,
                    project_root,
                    config_path,
                    entry_point,
                    "failed",
                    reused,
                    attempted,
                    failure_error=exc,
                    failure_stage="preparation",
                )
                manager.print_metrics_summary()
                raise

        manager.discard_transient_preparation()
        reused = manager.reconcile_successes()
        consecutive_infrastructure_failures = 0
        chapter_proofreader = proofreader or GeminiProofreader(
            config.proofreading_settings, locale=config.locale
        )
        for chapter in manager.state["chapters"]:
            if chapter["state"] == ChapterStatus.SUCCEEDED.value:
                continue
            manager.wait_for_proofreading_cooldown()
            manager.heartbeat()
            source_snapshot = manager.chapter_source_path(chapter)
            number = int(chapter["chapter_number"])
            attempted.append(chapter["chapter_number"])
            try:
                chapter_result = write_canonical_chapter_artifacts(
                    config,
                    paths,
                    number,
                    source_snapshot,
                    proofreader=chapter_proofreader,
                    converter_counts=manager.state.get("preparation", {}).get(
                        "converter_counts", {}
                    ),
                    entry_point=entry_point,
                    progress=lambda message, n=chapter["chapter_number"]: progress(
                        f"[proofread {n}] {message}"
                    ),
                )
                manager.mark_chapter_success(chapter, chapter_result)
                consecutive_infrastructure_failures = 0
            except ProofreadingError as exc:
                manager.mark_chapter_failure(chapter, exc)
                if _is_global_proofreading_failure(exc):
                    manager.mark_global_failure(exc)
                    _write_prep_audit(
                        manager,
                        project_root,
                        config_path,
                        entry_point,
                        "failed",
                        reused,
                        attempted,
                        failure_error=exc,
                        failure_stage="proofreading",
                    )
                    manager.print_metrics_summary()
                    raise
                if exc.code == "service_unavailable":
                    manager.impose_service_unavailable_cooldown(
                        config.proofreading_settings.unavailable_cooldown_seconds
                    )
                if exc.code in {
                    "api_error",
                    "rate_limited",
                    "request_timeout",
                    "service_unavailable",
                }:
                    consecutive_infrastructure_failures += 1
                    if (
                        consecutive_infrastructure_failures
                        >= INFRASTRUCTURE_FAILURE_CIRCUIT_BREAKER
                    ):
                        progress(
                            "[proofread] Infrastructure failure circuit breaker "
                            "opened; remaining chapters remain pending."
                        )
                        break

        if any(
            chapter["state"] != ChapterStatus.SUCCEEDED.value
            for chapter in manager.state["chapters"]
        ):
            manager.mark_incomplete()
            incomplete_error = ProcessingError(
                "prep-subject is incomplete; successful chapter checkpoints "
                "were retained. Re-run with --resume to retry failed or pending "
                "chapters."
            )
            _write_prep_audit(
                manager,
                project_root,
                config_path,
                entry_point,
                "incomplete",
                reused,
                attempted,
                failure_error=incomplete_error,
                failure_stage="proofreading",
            )
            manager.print_metrics_summary()
            raise incomplete_error

        manager.prepare_for_publication()
        try:
            manager.publish()
        except BaseException as exc:
            manager.mark_publication_failure(exc)
            _write_prep_audit(
                manager,
                project_root,
                config_path,
                entry_point,
                "failed",
                reused,
                attempted,
                failure_error=exc,
                failure_stage="publication",
            )
            manager.print_metrics_summary()
            raise
        _write_prep_audit(
            manager,
            project_root,
            config_path,
            entry_point,
            "succeeded",
            reused,
            attempted,
        )
        counts = manager.state["counts"]
        artifact_root = (
            subject_artifact_prefix(manager.destination)
            if manager.is_r2
            else str(manager.subject_dir)
        )
        progress(
            "prep-subject complete; canonical artifacts were published "
            f"successfully to {artifact_root}. Chapters: "
            f"{counts['succeeded']} succeeded, {counts['failed']} failed, "
            f"{counts['pending']} pending."
        )
        manager.print_metrics_summary()
        return {
            "status": "succeeded",
            "already_complete": False,
            "counts": manager.state["counts"],
            "metrics": manager.report_metrics(),
        }
    finally:
        manager.close()
