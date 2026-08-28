"""Shared staged-publication lifecycle for derived artifact commands."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from gurubodh.canonical_source import revalidate_source_release
from gurubodh.storage import (
    R2StorageClient,
    is_local,
    is_r2,
    r2_existing_artifacts_error,
    subject_artifact_object_key,
    upload_r2_file,
)
from gurubodh.time_utils import utc_now


class LifecycleState(str, Enum):
    PREFLIGHT = "preflight"
    SOURCE_VALIDATION = "source_validation"
    GENERATION = "generation"
    STAGED_VALIDATION = "staged_validation"
    SOURCE_REVALIDATION = "source_revalidation"
    PUBLICATION = "publication"
    SUCCESS_AUDIT = "success_audit"


@dataclass(frozen=True)
class DerivedArtifactDefinition:
    command_name: str
    output_relative_dir: Path
    readiness_manifest_filename: str
    report_relative_dir: Path
    legacy_output_relative_dirs: tuple[Path, ...] = ()


@dataclass
class SourceRelease:
    subject_dir: Path
    candidate_manifest: dict[str, Any]
    sources: list[dict[str, Any]]
    temporary_resource: Any = None

    def cleanup(self) -> None:
        if self.temporary_resource is not None:
            self.temporary_resource.cleanup()


@dataclass
class AuditResult:
    report: dict[str, Any]
    paths: dict[str, Path]


@dataclass
class LifecycleTrace:
    current_state: LifecycleState = LifecycleState.PREFLIGHT
    transitions: list[dict[str, str]] = field(default_factory=list)

    def enter(self, state: LifecycleState) -> None:
        self.current_state = state
        self.transitions.append({"state": state.value, "entered_at": utc_now()})

    def as_dict(self) -> dict[str, Any]:
        return {
            "current_state": self.current_state.value,
            "transitions": list(self.transitions),
        }


@dataclass
class PublicationResult:
    backend: str
    ownership_scope: str
    overwrite_requested: bool
    status: str = "not_started"
    preflight_status: str = "not_started"
    existed_before_run: bool | None = None
    prior_publication_state: str = "unknown"
    replaced_existing_output: bool = False
    output_path: str | None = None
    bucket: str | None = None
    prefix: str | None = None
    readiness_manifest_key: str | None = None
    deleted_for_overwrite: list[str] = field(default_factory=list)
    uploaded_keys: list[str] = field(default_factory=list)
    manifest_published_last: bool = False
    legacy_cleanup: dict[str, Any] = field(
        default_factory=lambda: {
            "status": "not_applicable",
            "paths": [],
            "deleted_identifiers": [],
        }
    )
    readiness_cleanup_error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "status": self.status,
            "preflight_status": self.preflight_status,
            "ownership_scope": self.ownership_scope,
            "overwrite_requested": self.overwrite_requested,
            "existed_before_run": self.existed_before_run,
            "prior_publication_state": self.prior_publication_state,
            "replaced_existing_output": self.replaced_existing_output,
            "output_path": self.output_path,
            "bucket": self.bucket,
            "prefix": self.prefix,
            "readiness_manifest_key": self.readiness_manifest_key,
            "deleted_for_overwrite": list(self.deleted_for_overwrite),
            "uploaded_keys": list(self.uploaded_keys),
            "manifest_published_last": self.manifest_published_last,
            "legacy_cleanup": dict(self.legacy_cleanup),
            "readiness_cleanup_error": self.readiness_cleanup_error,
        }


@dataclass
class LifecycleResult:
    source: SourceRelease
    generation: Any
    publication: dict[str, Any]
    audit_report: dict[str, Any]
    lifecycle: dict[str, Any]


class DerivedArtifactWorkflow(Protocol):
    """Narrow command-specific surface used by the shared lifecycle."""

    def materialize_and_validate_source(
        self, r2_client: Any, progress: Any
    ) -> SourceRelease: ...

    def generate_staged_artifacts(
        self, source: SourceRelease, staged_output: Path, progress: Any
    ) -> Any: ...

    def build_readiness_manifest(
        self, source: SourceRelease, generation: Any
    ) -> dict[str, Any]: ...

    def validate_staged_package(
        self,
        source: SourceRelease,
        generation: Any,
        staged_output: Path,
        readiness_manifest: Path,
    ) -> None: ...

    def write_audit(
        self,
        status: str,
        lifecycle: LifecycleTrace,
        source: SourceRelease | None,
        generation: Any,
        publication: dict[str, Any],
        failure: dict[str, Any] | None,
        announce: bool,
    ) -> AuditResult: ...


def destination_subject_dir(config: dict[str, Any], command_name: str):
    destination = config["destination"]
    if is_local(destination):
        return Path(destination["root_dir"]).expanduser() / destination["subject_dir"], None
    temporary = tempfile.TemporaryDirectory(prefix=f"gurubodh-{command_name}-destination-")
    return Path(temporary.name) / destination["subject_dir"], temporary


def _output_prefix(config: dict[str, Any], definition: DerivedArtifactDefinition) -> str:
    return subject_artifact_object_key(config["destination"], definition.output_relative_dir) + "/"


def _legacy_prefixes(
    config: dict[str, Any], definition: DerivedArtifactDefinition
) -> list[str]:
    return [
        subject_artifact_object_key(config["destination"], path) + "/"
        for path in definition.legacy_output_relative_dirs
    ]


def preflight_destination(
    config: dict[str, Any],
    definition: DerivedArtifactDefinition,
    destination_subject: Path,
    overwrite: bool,
    publication: PublicationResult,
    r2_client: Any = None,
) -> None:
    """Inspect command-owned destinations without modifying them."""
    destination = config["destination"]
    if is_local(destination):
        output = destination_subject / definition.output_relative_dir
        legacy = [destination_subject / path for path in definition.legacy_output_relative_dirs]
        existing = [path for path in (output, *legacy) if path.exists()]
        publication.output_path = str(output)
        publication.existed_before_run = bool(existing)
        if output.exists():
            readiness = output / definition.readiness_manifest_filename
            publication.prior_publication_state = "ready" if readiness.is_file() else "partial"
        elif existing:
            publication.prior_publication_state = "legacy"
        else:
            publication.prior_publication_state = "absent"
        if existing and not overwrite:
            if any(path in existing for path in legacy):
                raise SystemExit(
                    f"Legacy combined {definition.command_name} output exists and is unsupported: "
                    f"{', '.join(str(path) for path in legacy if path.exists())}. "
                    "Re-run with --overwrite only after inspecting it."
                )
            raise SystemExit(
                f"{definition.command_name} output already exists. Re-run with --overwrite "
                f"to replace only: {output}"
            )
        publication.preflight_status = "passed"
        return

    client = r2_client or R2StorageClient.from_env()
    prefix = _output_prefix(config, definition)
    legacy_prefixes = _legacy_prefixes(config, definition)
    existing = [
        candidate
        for candidate in (prefix, *legacy_prefixes)
        if client.prefix_has_objects(destination["bucket"], candidate)
    ]
    publication.bucket = destination["bucket"]
    publication.prefix = prefix
    publication.readiness_manifest_key = subject_artifact_object_key(
        destination,
        definition.output_relative_dir / definition.readiness_manifest_filename,
    )
    publication.existed_before_run = bool(existing)
    if client.exists(destination["bucket"], publication.readiness_manifest_key):
        publication.prior_publication_state = "ready"
    elif existing:
        publication.prior_publication_state = "partial_or_legacy"
    else:
        publication.prior_publication_state = "absent"
    if existing and not overwrite:
        raise SystemExit(
            r2_existing_artifacts_error(
                definition.command_name,
                destination["bucket"],
                existing,
                f"{definition.command_name} output",
            )
        )
    publication.preflight_status = "passed"


def _remove_local_path(path: Path) -> list[str]:
    if path.is_dir():
        identifiers = [str(item) for item in path.rglob("*") if item.is_file()]
        shutil.rmtree(path)
        return identifiers
    if path.exists():
        path.unlink()
        return [str(path)]
    return []


def publish_local(
    definition: DerivedArtifactDefinition,
    staged_output: Path,
    destination_subject: Path,
    overwrite: bool,
    publication: PublicationResult,
) -> None:
    destination_output = destination_subject / definition.output_relative_dir
    destination_output.parent.mkdir(parents=True, exist_ok=True)
    if destination_output.exists() and not overwrite:
        raise SystemExit(
            f"{definition.command_name} output appeared after preflight. Re-run with "
            f"--overwrite only after inspecting: {destination_output}"
        )
    legacy_paths = [destination_subject / path for path in definition.legacy_output_relative_dirs]
    appeared_legacy = [path for path in legacy_paths if path.exists()]
    if appeared_legacy and not overwrite:
        raise SystemExit(
            f"Legacy {definition.command_name} output appeared after preflight. "
            f"Inspect before retrying: {', '.join(str(path) for path in appeared_legacy)}"
        )

    incoming = destination_output.with_name(
        f".{destination_output.name}.incoming-{uuid.uuid4().hex}"
    )
    backup = destination_output.with_name(
        f".{destination_output.name}.backup-{uuid.uuid4().hex}"
    )
    replaced = False
    publication.status = "publishing"
    try:
        shutil.copytree(staged_output, incoming)
        if destination_output.exists():
            os.replace(destination_output, backup)
            replaced = True
        os.replace(incoming, destination_output)
    except BaseException:
        if replaced and backup.exists() and not destination_output.exists():
            os.replace(backup, destination_output)
        raise
    finally:
        if incoming.exists():
            _remove_local_path(incoming)

    publication.output_path = str(destination_output)
    publication.replaced_existing_output = replaced
    publication.status = "succeeded"
    if legacy_paths:
        deleted = []
        for path in legacy_paths:
            deleted.extend(_remove_local_path(path))
        publication.legacy_cleanup = {
            "status": "succeeded",
            "paths": [str(path) for path in legacy_paths],
            "deleted_identifiers": deleted,
        }
        publication.replaced_existing_output = replaced or bool(deleted)
    if backup.exists():
        _remove_local_path(backup)


def _ensure_r2_not_ready(
    publication: PublicationResult, r2_client: Any
) -> None:
    if not publication.readiness_manifest_key or not publication.bucket:
        return
    try:
        if r2_client.exists(publication.bucket, publication.readiness_manifest_key):
            deleted = r2_client.delete_keys(
                publication.bucket, [publication.readiness_manifest_key]
            )
            for key in deleted:
                if key not in publication.deleted_for_overwrite:
                    publication.deleted_for_overwrite.append(key)
        publication.manifest_published_last = False
    except BaseException as cleanup_error:
        publication.readiness_cleanup_error = (
            str(cleanup_error)[:500] or cleanup_error.__class__.__name__
        )


def publish_r2(
    config: dict[str, Any],
    definition: DerivedArtifactDefinition,
    staged_output: Path,
    overwrite: bool,
    publication: PublicationResult,
    r2_client: Any,
    progress: Any,
) -> None:
    destination = config["destination"]
    bucket = destination["bucket"]
    prefix = _output_prefix(config, definition)
    legacy_prefixes = _legacy_prefixes(config, definition)
    manifest_path = staged_output / definition.readiness_manifest_filename
    manifest_key = subject_artifact_object_key(
        destination,
        definition.output_relative_dir / definition.readiness_manifest_filename,
    )
    publication.bucket = bucket
    publication.prefix = prefix
    publication.readiness_manifest_key = manifest_key

    if not overwrite:
        appeared = [
            candidate
            for candidate in (prefix, *legacy_prefixes)
            if r2_client.prefix_has_objects(bucket, candidate)
        ]
        if appeared:
            raise SystemExit(
                r2_existing_artifacts_error(
                    definition.command_name,
                    bucket,
                    appeared,
                    f"{definition.command_name} output that appeared after preflight",
                )
            )

    publication.status = "publishing"
    try:
        if overwrite:
            if r2_client.exists(bucket, manifest_key):
                publication.deleted_for_overwrite.extend(
                    r2_client.delete_keys(bucket, [manifest_key])
                )
            publication.deleted_for_overwrite.extend(
                r2_client.delete_prefix(bucket, prefix)
            )

        artifacts = sorted(
            (
                path
                for path in staged_output.rglob("*")
                if path.is_file() and path != manifest_path
            ),
            key=lambda path: path.relative_to(staged_output).as_posix(),
        )
        progress(
            f"Publishing {len(artifacts)} validated {definition.command_name} artifact(s) "
            f"to r2://{bucket}/{prefix}"
        )
        for index, path in enumerate(artifacts, start=1):
            relative = definition.output_relative_dir / path.relative_to(staged_output)
            key = subject_artifact_object_key(destination, relative)
            upload_r2_file(r2_client, destination, path, key)
            publication.uploaded_keys.append(key)
            progress(f"[{index:02d}/{len(artifacts):02d}] uploaded {path.name}")

        upload_r2_file(r2_client, destination, manifest_path, manifest_key)
        publication.uploaded_keys.append(manifest_key)
        publication.manifest_published_last = True
        publication.replaced_existing_output = bool(
            overwrite and publication.existed_before_run
        )
        publication.status = "succeeded"
        progress(
            f"Published {definition.readiness_manifest_filename} last; "
            f"the {definition.command_name} output is ready."
        )

        if legacy_prefixes:
            deleted = []
            for legacy_prefix in legacy_prefixes:
                deleted.extend(r2_client.delete_prefix(bucket, legacy_prefix))
            publication.legacy_cleanup = {
                "status": "succeeded",
                "paths": legacy_prefixes,
                "deleted_identifiers": deleted,
            }
    except BaseException:
        _ensure_r2_not_ready(publication, r2_client)
        publication.status = "failed"
        raise


def _validate_stage_layout(staged_output: Path, readiness_manifest: Path) -> None:
    staged_root = staged_output.resolve()
    manifest = readiness_manifest.resolve()
    if not staged_output.is_dir():
        raise ValueError("Derived-artifact staged output directory was not created.")
    if manifest.parent != staged_root:
        raise ValueError("Readiness manifest must be located at the staged output root.")
    if not readiness_manifest.is_file():
        raise ValueError(f"Readiness manifest was not written: {readiness_manifest}")
    for path in staged_output.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Staged derived artifacts must not contain symlinks: {path}")
        if not path.resolve().is_relative_to(staged_root):
            raise ValueError(f"Staged derived artifact escapes its workspace: {path}")


def _upload_audit_reports(
    config: dict[str, Any],
    definition: DerivedArtifactDefinition,
    audit: AuditResult,
    r2_client: Any,
) -> None:
    destination = config["destination"]
    for kind in ("json", "markdown"):
        path = audit.paths[kind]
        key = subject_artifact_object_key(
            destination, definition.report_relative_dir / path.name
        )
        upload_r2_file(r2_client, destination, path, key)


def _failure_details(state: LifecycleState, error: BaseException) -> dict[str, Any]:
    return {
        "state": state.value,
        "stage": state.value,
        "error_type": error.__class__.__name__,
        "message": str(error)[:1000] or error.__class__.__name__,
    }


def run_derived_artifact_lifecycle(
    config: dict[str, Any],
    definition: DerivedArtifactDefinition,
    workflow: DerivedArtifactWorkflow,
    overwrite: bool = False,
    r2_client: Any = None,
    progress: Any = print,
    destination_subject: Path | None = None,
    destination_temporary: Any = None,
    source_revalidator: Any = revalidate_source_release,
) -> LifecycleResult:
    """Execute the ordered lifecycle and preserve the original failure."""
    needs_r2 = is_r2(config["source"]) or is_r2(config["destination"])
    client = r2_client if needs_r2 else None
    if client is None and needs_r2:
        client = R2StorageClient.from_env()
    if destination_subject is None:
        destination_subject, destination_temporary = destination_subject_dir(
            config, definition.command_name
        )
    trace = LifecycleTrace()
    source = None
    generation = None
    backend = config["destination"].get("backend", "local")
    publication = PublicationResult(
        backend=backend,
        ownership_scope=definition.output_relative_dir.as_posix(),
        overwrite_requested=overwrite,
    )

    try:
        with tempfile.TemporaryDirectory(
            prefix=f"gurubodh-{definition.command_name}-stage-"
        ) as stage_dir:
            staged_output = Path(stage_dir) / definition.output_relative_dir.name
            trace.enter(LifecycleState.PREFLIGHT)
            preflight_destination(
                config,
                definition,
                destination_subject,
                overwrite,
                publication,
                client,
            )

            trace.enter(LifecycleState.SOURCE_VALIDATION)
            source = workflow.materialize_and_validate_source(client, progress)

            trace.enter(LifecycleState.GENERATION)
            staged_output.mkdir(parents=True, exist_ok=False)
            generation = workflow.generate_staged_artifacts(
                source, staged_output, progress
            )

            trace.enter(LifecycleState.STAGED_VALIDATION)
            manifest_payload = workflow.build_readiness_manifest(source, generation)
            readiness_manifest = staged_output / definition.readiness_manifest_filename
            readiness_manifest.write_text(
                json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            _validate_stage_layout(staged_output, readiness_manifest)
            workflow.validate_staged_package(
                source, generation, staged_output, readiness_manifest
            )

            trace.enter(LifecycleState.SOURCE_REVALIDATION)
            source_revalidator(
                config,
                source.candidate_manifest,
                definition.command_name,
                client,
            )

            trace.enter(LifecycleState.PUBLICATION)
            if is_local(config["destination"]):
                publish_local(
                    definition,
                    staged_output,
                    destination_subject,
                    overwrite,
                    publication,
                )
            else:
                publish_r2(
                    config,
                    definition,
                    staged_output,
                    overwrite,
                    publication,
                    client,
                    progress,
                )

            trace.enter(LifecycleState.SUCCESS_AUDIT)
            audit = workflow.write_audit(
                "succeeded",
                trace,
                source,
                generation,
                publication.as_dict(),
                None,
                announce=is_local(config["destination"]),
            )
            if is_r2(config["destination"]):
                _upload_audit_reports(config, definition, audit, client)
                progress(
                    f"Published {definition.command_name} audit reports under "
                    f"r2://{config['destination']['bucket']}/"
                    f"{subject_artifact_object_key(config['destination'], definition.report_relative_dir)}/"
                )
            return LifecycleResult(
                source=source,
                generation=generation,
                publication=publication.as_dict(),
                audit_report=audit.report,
                lifecycle=trace.as_dict(),
            )
    except BaseException as error:
        if is_r2(config["destination"]) and publication.status in {
            "publishing",
            "failed",
        }:
            _ensure_r2_not_ready(publication, client)
        failure = _failure_details(trace.current_state, error)
        try:
            audit = workflow.write_audit(
                "failed",
                trace,
                source,
                generation,
                publication.as_dict(),
                failure,
                announce=is_local(config["destination"]),
            )
            if is_r2(config["destination"]):
                _upload_audit_reports(config, definition, audit, client)
        except BaseException:
            pass
        raise
    finally:
        if source is not None:
            source.cleanup()
        if destination_temporary is not None:
            destination_temporary.cleanup()
