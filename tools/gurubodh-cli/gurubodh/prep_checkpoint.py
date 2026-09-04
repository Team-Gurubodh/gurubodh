"""Backend-neutral checkpoint domain and resumable prep session facade."""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from gurubodh.audit import bounded_failure
from gurubodh.canonical_release import (
    CHECKPOINT_CONTRACT_VERSION,
    CHECKPOINT_SCHEMA_VERSION,
)
from gurubodh.contracts import (
    ChapterStatus,
    PrepCheckpointState,
    PrepJobStatus,
    PrepPublicationState,
    PrepSubjectJob,
    ProofreadingOutcome,
    PublicationStatus,
    R2Client,
)
from gurubodh.content_identity import build_content_identity
from gurubodh.content_manifest import write_chapter_content_manifest
from gurubodh.errors import ProcessingError, PublicationError, SourceValidationError
from gurubodh.naming import chapter_output_filename
from gurubodh.paths import destination_paths_for_subject
from gurubodh.prep_checkpoint_store import (
    CheckpointStore,
    create_checkpoint_store,
    read_json_object,
    workspace_relative_path,
)
from gurubodh.prep_coordination import (
    PrepCoordinator,
    create_prep_coordinator,
)
from gurubodh.prep_metrics import PrepMetrics
from gurubodh.prep_publication import PrepPublisher, create_prep_publisher
from gurubodh.proofreading.artifacts import (
    write_proofreading_manifest,
)
from gurubodh.storage import (
    R2StorageClient,
    destination_artifact_reference,
    is_r2,
    materialize_source,
)
from gurubodh.time_utils import utc_now


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_error(exc: BaseException) -> dict[str, Any]:
    failure = bounded_failure(exc, "checkpoint")
    error = {key: failure[key] for key in ("code", "message")}
    if failure["request_diagnostics"] is not None:
        error["request_diagnostics"] = failure["request_diagnostics"]
    return error


def safe_config_inputs(config: PrepSubjectJob) -> dict[str, Any]:
    """Return only output-affecting inputs; operational pacing is excluded."""
    settings = config.proofreading_settings
    locale = config.locale
    chapter_split = {
        key: value
        for key, value in config["chapter_split"].items()
        if not key.startswith("_")
    }
    if chapter_split.get("pattern_type") == "regex":
        chapter_split["flags"] = sorted(chapter_split.get("flags", []))
    return {
        "pipeline": config["pipeline"],
        "chapter_split": chapter_split,
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


def compatibility_record(
    config: PrepSubjectJob, source_sha256: str
) -> dict[str, Any]:
    return compatibility_record_from_inputs(safe_config_inputs(config), source_sha256)


def compatibility_record_from_inputs(
    output_affecting_inputs: dict[str, Any], source_sha256: str
) -> dict[str, Any]:
    payload = {
        "source_docx_sha256": source_sha256,
        "output_affecting_inputs": output_affecting_inputs,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return payload | {"fingerprint": hashlib.sha256(encoded).hexdigest()}


def _canonicalize_legacy_compatibility(
    record: dict[str, Any],
) -> dict[str, Any] | None:
    source_sha256 = record.get("source_docx_sha256")
    inputs = record.get("output_affecting_inputs")
    fingerprint = record.get("fingerprint")
    if (
        not isinstance(source_sha256, str)
        or not isinstance(inputs, dict)
        or not isinstance(fingerprint, str)
    ):
        return None
    if (
        compatibility_record_from_inputs(inputs, source_sha256)["fingerprint"]
        != fingerprint
    ):
        return None
    canonical_inputs = dict(inputs)
    chapter_split = canonical_inputs.get("chapter_split")
    if isinstance(chapter_split, dict) and chapter_split.get("pattern_type") == "regex":
        canonical_chapter_split = dict(chapter_split)
        flags = canonical_chapter_split.get("flags", [])
        if not isinstance(flags, list) or not all(
            isinstance(flag, str) for flag in flags
        ):
            return None
        canonical_chapter_split["flags"] = sorted(flags)
        canonical_inputs["chapter_split"] = canonical_chapter_split
    return compatibility_record_from_inputs(canonical_inputs, source_sha256)


def compatibility_matches(
    stored: dict[str, Any], current: dict[str, Any]
) -> bool:
    canonical_stored = _canonicalize_legacy_compatibility(stored)
    return (
        canonical_stored is not None
        and canonical_stored["fingerprint"] == current["fingerprint"]
    )


def chapter_counts(chapters: list[dict[str, Any]]) -> dict[str, int]:
    return {
        state: sum(1 for chapter in chapters if chapter.get("state") == state)
        for state in (
            ChapterStatus.SUCCEEDED.value,
            ChapterStatus.FAILED.value,
            ChapterStatus.PENDING.value,
        )
    }


class PrepCheckpointManager:
    """Cohesive session facade over checkpoint, coordination, and publication ports."""

    def __init__(
        self,
        config: PrepSubjectJob,
        resume: bool,
        overwrite: bool,
        r2_client: R2Client | None = None,
        *,
        store: CheckpointStore | None = None,
        coordinator: PrepCoordinator | None = None,
        publisher: PrepPublisher | None = None,
        metrics: PrepMetrics | None = None,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
        progress: Callable[[str], None] = print,
    ) -> None:
        self.config = config
        self.resume = resume
        self.overwrite = overwrite
        self.destination = config["destination"]
        self.r2_client = r2_client
        self.clock = clock
        self.sleeper = sleeper
        self.progress = progress
        self._state: PrepCheckpointState | None = None
        self.metrics_service = metrics or PrepMetrics(is_r2(self.destination))
        self.store = store or create_checkpoint_store(
            config, self.metrics_service, r2_client
        )
        self.subject_dir = self.store.subject_dir
        self.state_path = self.store.state_path
        self.coordinator = coordinator or create_prep_coordinator(
            is_r2=self.store.is_r2,
            subject_dir=self.subject_dir,
            clock=clock,
        )
        self.publisher = publisher or create_prep_publisher(
            config,
            self.subject_dir,
            self.metrics_service,
            self.store.client,
        )
        self.source_temp_dir: tempfile.TemporaryDirectory | None = None

    @property
    def state(self) -> PrepCheckpointState | None:
        return self._state

    @state.setter
    def state(self, value: PrepCheckpointState | dict[str, Any] | None) -> None:
        if value is None or isinstance(value, PrepCheckpointState):
            self._state = value
            return
        try:
            self._state = PrepCheckpointState.from_payload(value)
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceValidationError(
                f"Unsupported or malformed prep-subject checkpoint state: {exc}"
            ) from exc

    @property
    def client(self) -> R2Client:
        if self.r2_client is not None:
            return self.r2_client
        if self.store.client is not None:
            return self.store.client
        self.r2_client = R2StorageClient.from_env()
        return self.r2_client

    @property
    def is_r2(self) -> bool:
        return self.store.is_r2

    @property
    def owner_id(self) -> str:
        return self.coordinator.owner_id

    @property
    def job_id(self) -> str:
        if not self.state:
            raise RuntimeError("Checkpoint state is not initialized")
        return self.state["job_id"]

    @property
    def workspace_relative(self) -> Path:
        return workspace_relative_path(self.job_id)

    @property
    def workspace_dir(self) -> Path:
        return self.subject_dir / self.workspace_relative

    @property
    def paths(self) -> dict[str, Path]:
        return destination_paths_for_subject(self.workspace_dir)

    def open(self) -> None:
        self.coordinator.acquire()
        self.state = self.store.load()
        if self.state:
            self.store.restore_workspace(self.workspace_relative)

    def begin(self, source_sha256: str) -> str:
        compatibility = compatibility_record(self.config, source_sha256)
        if self.state:
            self._validate_loaded_state()
            if self.overwrite:
                self.store.archive_prior_state(self.state, self.workspace_relative)
                self.state = None
            elif not self.resume:
                if self.state.status is PrepJobStatus.SUCCEEDED:
                    raise ProcessingError(
                        "A completed prep-subject checkpoint already exists. "
                        "Use --resume to confirm it is complete or --overwrite "
                        "to start a fresh job."
                    )
                raise ProcessingError(
                    "An incomplete prep-subject checkpoint already exists. "
                    "Re-run with --resume to continue it or --overwrite to "
                    "discard its staged workspace and start over."
                )
            elif not compatibility_matches(
                self.state["compatibility"], compatibility
            ):
                raise ProcessingError(
                    "The existing prep-subject checkpoint is incompatible with "
                    "this source or output-affecting configuration. Re-run with "
                    "--overwrite; checkpoints from different inputs are never mixed."
                )
            elif self.state.status is PrepJobStatus.SUCCEEDED:
                self.state["run"] = self.state.get("run", {}) | {
                    "run_id": str(uuid.uuid4()),
                    "last_started_at": utc_now(),
                }
                return "already_complete"
        elif self.resume:
            raise ProcessingError(
                "No prep-subject checkpoint exists to resume. Run without "
                "--resume to start a new job."
            )

        if self.state is None:
            if self.store.prep_artifacts_exist() and not self.overwrite:
                raise PublicationError(
                    "Canonical prepared artifacts exist without a compatible "
                    "checkpoint. Re-run with --overwrite to create a fresh "
                    "staged prep-subject job."
                )
            now = utc_now()
            job_id = str(uuid.uuid4())
            self.state = PrepCheckpointState.from_payload(
                {
                    "schema_version": CHECKPOINT_SCHEMA_VERSION,
                    "job_id": job_id,
                    "state": PrepJobStatus.RUNNING.value,
                    "created_at": now,
                    "updated_at": now,
                    "run": {
                        "run_id": str(uuid.uuid4()),
                        "started_at": now,
                        "last_started_at": now,
                    },
                    "lease": {},
                    "compatibility": compatibility,
                    "chapters": [],
                    "counts": {"succeeded": 0, "failed": 0, "pending": 0},
                    "publication": {
                        "state": PublicationStatus.NOT_READY.value,
                        "canonical_manifest": None,
                    },
                    "run_reports": [],
                    "workspace": {
                        "relative_path": str(workspace_relative_path(job_id)),
                        "status": "active",
                    },
                    "failure": None,
                    "preparation": None,
                }
            )
        else:
            self.state.status = PrepJobStatus.RUNNING
            self.state["run"] = self.state.get("run", {}) | {
                "run_id": str(uuid.uuid4()),
                "last_started_at": utc_now(),
            }
            self.state["failure"] = None
        self.coordinator.claim(self.state)
        self.persist()
        return "started"

    def _validate_loaded_state(self) -> None:
        if (
            self.state.get("schema_version") != CHECKPOINT_SCHEMA_VERSION
            or not isinstance(self.state.get("job_id"), str)
        ):
            raise SourceValidationError(
                "Unsupported or malformed prep-subject checkpoint. Re-run "
                "with --overwrite."
            )
        stored_contract = (
            self.state.get("compatibility", {})
            .get("output_affecting_inputs", {})
            .get("checkpoint_contract_version")
        )
        if stored_contract != CHECKPOINT_CONTRACT_VERSION and not self.overwrite:
            raise SourceValidationError(
                "The existing prep-subject checkpoint uses an incompatible "
                "artifact contract. It cannot be resumed with the five-file "
                "text-only checkpoint; re-run with --overwrite."
            )
        self.coordinator.validate_loaded_state(self.state)

    def heartbeat(self) -> None:
        self.coordinator.heartbeat(self.state)

    def persist(
        self,
        checkpoint_artifacts: list[Path] | None = None,
        checkpoint_artifact_category: str | None = None,
        count_r2_uploads: bool = True,
    ) -> None:
        if not self.state:
            return
        self.state["updated_at"] = utc_now()
        self.state["counts"] = chapter_counts(self.state.get("chapters", []))
        self.store.commit(
            self.state,
            checkpoint_artifacts,
            checkpoint_artifact_category,
            count_r2_uploads,
        )

    def materialize_source(self) -> Path:
        path, self.source_temp_dir = materialize_source(
            self.config,
            r2_client=self.r2_client or self.store.client,
        )
        return path

    def set_chapter_plan(
        self, source_paths: list[Path], preparation: dict[str, Any]
    ) -> None:
        if not source_paths:
            raise ProcessingError(
                "No chapters were detected, so prep-subject cannot create a "
                "resumable canonical chapter set."
            )
        chapters = []
        for index, source_path in enumerate(sorted(source_paths), start=1):
            chapters.append(
                {
                    "chapter_number": f"{index:03d}",
                    "source_filename": source_path.name,
                    "source_sha256": sha256_file(source_path),
                    "state": ChapterStatus.PENDING.value,
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
        self.store.discard_workspace_path(self.workspace_relative / ".transient")

    def chapter_source_path(self, chapter: dict[str, Any]) -> Path:
        path = self.paths["unmodified_source_text"] / chapter["source_filename"]
        if not path.is_file() or sha256_file(path) != chapter["source_sha256"]:
            raise SourceValidationError(
                "Checkpointed source snapshot for chapter "
                f"{chapter['chapter_number']} is missing or changed. Re-run "
                "with --overwrite to build a compatible workspace."
            )
        return path

    def reconcile_successes(self) -> list[str]:
        reused: list[str] = []
        changed = False
        for chapter in self.state.get("chapters", []):
            valid = self._validate_success_artifacts(chapter)
            if chapter.get("state") == ChapterStatus.SUCCEEDED.value:
                if valid:
                    reused.append(chapter["chapter_number"])
                else:
                    changed = True
                    chapter["state"] = ChapterStatus.PENDING.value
                    chapter["successful_artifacts"] = []
                    chapter["proofreading"] = None
                    chapter["latest_error"] = {
                        "code": "checkpoint_artifacts_invalid",
                        "message": (
                            "Saved artifacts were missing or did not pass "
                            "checksum validation; chapter will be reprocessed."
                        ),
                    }
                    chapter["updated_at"] = utc_now()
            elif valid:
                changed = True
                chapter["state"] = ChapterStatus.SUCCEEDED.value
                chapter["successful_artifacts"] = self._expected_artifact_records(
                    chapter
                )
                chapter["proofreading"] = self._reconciled_proofreading_summary(
                    chapter
                )
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

    def _expected_artifact_records(
        self, chapter: dict[str, Any]
    ) -> list[dict[str, str]]:
        return [
            {
                "path": str(path.relative_to(self.paths["subject"])),
                "sha256": sha256_file(path),
            }
            for path in self._expected_artifact_paths(chapter)
        ]

    def _validate_success_artifacts(self, chapter: dict[str, Any]) -> bool:
        try:
            paths = self._expected_artifact_paths(chapter)
            if not all(path.is_file() for path in paths):
                return False
            records = chapter.get("successful_artifacts")
            if records:
                expected = {
                    record.get("path"): record.get("sha256")
                    for record in records
                }
                current = {
                    str(path.relative_to(self.paths["subject"])): sha256_file(path)
                    for path in paths
                }
                if expected != current:
                    return False
            source_sha = sha256_file(paths[0])
            text_sha = sha256_file(paths[1])
            metadata = read_json_object(
                paths[2], "Checkpointed chapter metadata"
            )
            details = read_json_object(
                paths[4], "Checkpointed proofreading details"
            )
            locale = self.config.locale
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
                and details["canonical_corrected"].get("content_identity")
                == canonical_identity
                and details["canonical_corrected"].get("text_artifact")
                == metadata.get("storage", {}).get("artifacts", {}).get("text")
                and source_sha == chapter.get("source_sha256")
                and details["unmodified_source"].get("text_sha256") == source_sha
                and details["unmodified_source"].get("content_identity")
                == source_identity
                and details.get("integrity", {})
                .get("unmodified_source", {})
                .get("value")
                == source_sha
                and details.get("integrity", {})
                .get("canonical_corrected", {})
                .get("value")
                == text_sha
                and details.get("status") == "succeeded"
            )
        except (
            KeyError,
            OSError,
            SourceValidationError,
            TypeError,
            UnicodeDecodeError,
        ):
            return False

    def _reconciled_proofreading_summary(
        self, chapter: dict[str, Any]
    ) -> dict[str, Any]:
        number = int(chapter["chapter_number"])
        text_name = chapter_output_filename(self.config, number, ".txt")
        details = read_json_object(
            self.paths["proofreading"]
            / f"{Path(text_name).stem}.proofread.json",
            "Checkpointed proofreading details",
        )
        metadata = read_json_object(
            self.paths["text_and_metadata"]
            / chapter_output_filename(self.config, number, ".json"),
            "Checkpointed chapter metadata",
        )
        return {
            "chapter_number": chapter["chapter_number"],
            "status": "succeeded",
            "correction_count": len(details.get("gemini_edits", [])),
            "local_diff_summary": details.get("local_diff_summary", {}),
            "unmodified_source_content_key": details.get(
                "unmodified_source", {}
            )
            .get("content_identity", {})
            .get("content_key"),
            "canonical_content_key": metadata.get("content_identity", {}).get(
                "content_key"
            ),
            "artifacts": {
                "unmodified_source": details.get("unmodified_source", {}).get(
                    "text_artifact"
                ),
                "canonical_text": metadata.get("storage", {})
                .get("artifacts", {})
                .get("text"),
                "canonical_metadata": metadata.get("storage", {})
                .get("artifacts", {})
                .get("metadata"),
                "diff": details.get("diff_artifact"),
                "json": destination_artifact_reference(
                    self.config,
                    Path("chapters")
                    / "proofreading"
                    / f"{Path(text_name).stem}.proofread.json",
                ),
            },
        }

    def mark_chapter_success(
        self, chapter: dict[str, Any], result: ProofreadingOutcome
    ) -> None:
        chapter["state"] = ChapterStatus.SUCCEEDED.value
        chapter["attempt_count"] += 1
        chapter["updated_at"] = utc_now()
        chapter["succeeded_at"] = utc_now()
        chapter["latest_error"] = None
        chapter["successful_artifacts"] = [
            artifact.to_payload() for artifact in result.checkpoint_artifacts
        ]
        chapter["proofreading"] = result.proofreading_payload()
        self.metrics_service.record_proofreading_success(
            {
                "attempts": result.request_attempts,
                "successful_request_attempts": result.successful_request_attempts,
            }
        )
        self.persist(
            checkpoint_artifacts=[
                self.paths["subject"] / record["path"]
                for record in chapter["successful_artifacts"]
                if not str(record["path"]).startswith(
                    "chapters/unmodified_source_text/"
                )
            ],
            checkpoint_artifact_category="checkpoint_chapter_artifacts",
        )

    def mark_chapter_failure(
        self, chapter: dict[str, Any], exc: BaseException
    ) -> None:
        chapter["state"] = ChapterStatus.FAILED.value
        chapter["attempt_count"] += 1
        chapter["updated_at"] = utc_now()
        chapter["latest_error"] = safe_error(exc)
        self.metrics_service.record_proofreading_failure(exc)
        self.persist()

    def impose_service_unavailable_cooldown(self, seconds: float) -> None:
        self.state["proofreading_cooldown"] = {
            "reason": "service_unavailable",
            "duration_seconds": round(seconds, 3),
            "not_before_epoch": self.clock() + seconds,
        }
        self.persist()

    def wait_for_proofreading_cooldown(self) -> None:
        cooldown = self.state.get("proofreading_cooldown")
        if (
            not isinstance(cooldown, dict)
            or cooldown.get("reason") != "service_unavailable"
        ):
            return
        not_before = cooldown.get("not_before_epoch")
        if not isinstance(not_before, (int, float)):
            self.state["proofreading_cooldown"] = None
            self.persist()
            return
        remaining = max(0.0, not_before - self.clock())
        if remaining:
            self.progress(
                "[proofread] Gemini service-capacity cooldown is active; "
                f"waiting {remaining:.1f} seconds before another chapter request."
            )
            self.sleeper(remaining)
        self.state["proofreading_cooldown"] = None
        self.persist()

    def mark_global_failure(self, exc: BaseException) -> None:
        self.state.status = PrepJobStatus.FAILED
        self.state["failure"] = safe_error(exc)
        self.persist()

    def mark_incomplete(self) -> None:
        self.state.status = PrepJobStatus.INCOMPLETE
        self.state["failure"] = None
        self.persist()

    def prepare_for_publication(self) -> Path:
        chapters = self.state.get("chapters", [])
        if not chapters or any(
            chapter.get("state") != ChapterStatus.SUCCEEDED.value
            for chapter in chapters
        ):
            raise PublicationError(
                "Cannot publish until every expected chapter has a validated "
                "successful checkpoint."
            )
        for chapter in chapters:
            if not self._validate_success_artifacts(chapter):
                raise PublicationError(
                    "Checkpoint artifacts for chapter "
                    f"{chapter['chapter_number']} are not valid; re-run with "
                    "--resume to reprocess it before publication."
                )
        proofread = [chapter["proofreading"] for chapter in chapters]
        write_proofreading_manifest(
            self.paths,
            self.config.proofreading_settings,
            proofread,
            self.config.locale,
        )
        manifest = write_chapter_content_manifest(self.config, self.paths)
        self.state.status = PrepJobStatus.READY_TO_PUBLISH
        self.state.publication = PrepPublicationState.from_payload(
            {
                "state": PublicationStatus.READY_TO_PUBLISH.value,
                "canonical_manifest": {
                    "reference": destination_artifact_reference(
                        self.config, Path("chapters") / manifest.name
                    ),
                    "sha256": sha256_file(manifest),
                    "chapter_numbers": [
                        chapter["chapter_number"] for chapter in chapters
                    ],
                },
            }
        )
        self.persist()
        return manifest

    def publish(self) -> None:
        self.state.status = PrepJobStatus.PUBLISHING
        self.state.publication_status = PublicationStatus.PUBLISHING
        self.persist()
        publication_updates = self.publisher.publish_canonical(
            self.workspace_dir, self.overwrite
        )
        if publication_updates:
            publication = self.state.publication
            publication.payload.update(publication_updates)
            self.state.publication = publication
        if self.overwrite:
            self._perform_overwrite_cleanup()
        self.state.status = PrepJobStatus.SUCCEEDED
        self.state.publication_status = PublicationStatus.SUCCEEDED
        self.persist()
        self.store.remove_workspace(self.workspace_relative)
        self.state["workspace"]["status"] = "removed_after_success"
        self.persist()

    def _perform_overwrite_cleanup(self) -> None:
        publication = self.state.publication
        cleanup = publication.payload.setdefault(
            "obsolete_artifact_cleanup", {}
        )
        cleanup["chapter_docx_invalidation"] = (
            self.publisher.invalidate_chapter_docx()
        )
        self.state.publication = publication
        self.persist()
        cleanup["legacy_full_subject_cleanup"] = (
            self.publisher.cleanup_legacy_full_subject()
        )
        self.state.publication = publication
        self.persist()
        publication.payload["semantic_invalidation"] = (
            self.publisher.invalidate_semantic_artifacts()
        )
        self.state.publication = publication
        self.persist()
        docx_cleanup = cleanup["chapter_docx_invalidation"]
        full_subject_cleanup = cleanup["legacy_full_subject_cleanup"]
        semantic_cleanup = publication.payload["semantic_invalidation"]
        self.progress(
            "[overwrite] Derived chapter DOCX invalidation: "
            f"{'removed' if docx_cleanup['invalidated'] else 'not needed'}."
        )
        self.progress(
            "[overwrite] Legacy full_subject cleanup: "
            f"{'removed' if full_subject_cleanup['invalidated'] else 'not needed'}."
        )
        self.progress(
            "[overwrite] Semantic chunk invalidation: "
            f"{'removed' if semantic_cleanup['invalidated'] else 'not needed'}."
        )

    def mark_publication_failure(self, exc: BaseException) -> None:
        self.state.status = PrepJobStatus.PUBLISHING
        self.state.publication_status = PublicationStatus.PUBLISHING
        self.state["failure"] = safe_error(exc)
        self.persist()

    def release_lease_for_audit(self) -> None:
        if self.is_r2 and self.coordinator.release(self.state):
            self.persist()

    def upload_audit_file(self, path: Path, key: str) -> None:
        self.metrics_service.upload(
            self.client,
            self.destination,
            path,
            key,
            count=False,
        )

    def report_metrics(self) -> dict[str, Any]:
        return self.metrics_service.report()

    def print_metrics_summary(self) -> None:
        self.metrics_service.print_summary(self.progress)

    def close(self) -> None:
        if self.state and self.coordinator.release(self.state):
            if not self.is_r2:
                self.persist()
        self.coordinator.close()
        if self.source_temp_dir:
            self.source_temp_dir.cleanup()
        self.store.close()
