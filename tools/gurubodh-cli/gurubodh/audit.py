"""Shared audit-report context, envelope, serialization, and local writes."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from gurubodh import __version__
from gurubodh.diagnostics import safe_request_diagnostics
from gurubodh.errors import ProcessingError
from gurubodh.schema_validation import validate_artifact
from gurubodh.time_utils import utc_now


AUDIT_REPORT_SCHEMA_NAME = "gurubodh.audit-report"
AUDIT_REPORT_SCHEMA_VERSION = "2.0.0"
AUDIT_ENVELOPE_KEYS = frozenset(
    (
        "schema_name",
        "schema_version",
        "run_identity",
        "job_identity",
        "configuration_snapshot",
        "processing_summary",
        "lifecycle",
        "publication",
        "failure",
        "report_artifacts",
        "command_details",
    )
)
REDACTED = "[redacted]"
CONFIG_SNAPSHOT_KEYS = (
    "schema_version",
    "pipeline",
    "source",
    "destination",
    "naming",
    "chunking",
    "chapters",
    "chapter_split",
    "metadata_defaults",
    "proofreading",
    "locale",
    "lab_root",
)
AUDIT_STATUSES = frozenset(("succeeded", "failed", "incomplete"))


class MarkdownRenderer(Protocol):
    """Narrow command-specific Markdown rendering seam."""

    def __call__(self, report: dict[str, Any]) -> str: ...


class AuditWriteError(ProcessingError):
    """An audit could not be rendered, validated, or written locally."""


@dataclass(frozen=True)
class AuditPaths(Mapping[str, Path]):
    directory: Path
    json: Path
    markdown: Path

    def as_dict(self) -> dict[str, Path]:
        return {
            "directory": self.directory,
            "json": self.json,
            "markdown": self.markdown,
        }

    def __getitem__(self, key: str) -> Path:
        return self.as_dict()[key]

    def __iter__(self):
        return iter(self.as_dict())

    def __len__(self) -> int:
        return len(self.as_dict())


@dataclass(frozen=True)
class LocalAuditWrite:
    path: Path
    bytes_written: int


@dataclass(frozen=True)
class AuditWriteResult:
    """The common result consumed by local and R2 workflow boundaries."""

    report: dict[str, Any]
    paths: dict[str, Path]
    references: dict[str, Any]
    local_writes: dict[str, LocalAuditWrite]


@dataclass(frozen=True)
class AuditContext:
    """Safe, command-independent identity captured once for an audit run."""

    command_name: str
    entry_point: str
    run_id: str
    started_at: str
    filename_timestamp: str
    package_version: str
    config_path: str | None
    job_schema_version: str | int | None
    pipeline: str | None
    source_backend: str | None
    destination_backend: str
    overwrite: bool
    build_provenance: dict[str, Any]
    configuration_snapshot: dict[str, Any]

    @classmethod
    def create(
        cls,
        command_name: str,
        entry_point: str,
        project_root: str | Path,
        *,
        config_path: str | Path | None = None,
        config: Mapping[str, Any] | None = None,
        overwrite: bool = False,
        run_id: str | None = None,
        started_at: str | None = None,
        configuration: Mapping[str, Any] | None = None,
        source_backend: str | None = None,
        destination_backend: str | None = None,
    ) -> AuditContext:
        payload = _config_payload(config)
        source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
        destination = (
            payload.get("destination")
            if isinstance(payload.get("destination"), dict)
            else {}
        )
        now = datetime.now(timezone.utc)
        return cls(
            command_name=command_name,
            entry_point=entry_point,
            run_id=run_id or str(uuid.uuid4()),
            started_at=started_at or now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            filename_timestamp=now.strftime("%Y%m%dT%H%M%S%fZ"),
            package_version=__version__,
            config_path=str(config_path) if config_path is not None else None,
            job_schema_version=payload.get("schema_version"),
            pipeline=payload.get("pipeline"),
            source_backend=source_backend or source.get("backend") or ("local" if source else None),
            destination_backend=(
                destination_backend or destination.get("backend") or "local"
            ),
            overwrite=overwrite,
            build_provenance=resolved_build_provenance(project_root),
            configuration_snapshot=safe_configuration_snapshot(
                configuration if configuration is not None else payload
            ),
        )

    def run_identity(self, status: str) -> dict[str, Any]:
        if status not in AUDIT_STATUSES:
            raise ValueError(f"Unsupported audit status: {status!r}")
        return {
            "run_id": self.run_id,
            "status": status,
            "started_at": self.started_at,
            "completed_at": utc_now(),
            "command": self.command_name,
            "entry_point": self.entry_point,
            "package_version": self.package_version,
            "config_path": self.config_path,
            "job_schema_version": self.job_schema_version,
            "pipeline": self.pipeline,
            "source_backend": self.source_backend,
            "destination_backend": self.destination_backend,
            "overwrite": self.overwrite,
            "build_provenance": deepcopy(self.build_provenance),
        }


class AuditWriter:
    """The only JSON/Markdown serializer and local writer for run audits."""

    def __init__(
        self,
        context: AuditContext,
        paths: AuditPaths | Mapping[str, Path],
        reference_builder: Callable[[AuditPaths], dict[str, Any]] | None = None,
    ):
        self.context = context
        self.audit_paths = (
            paths
            if isinstance(paths, AuditPaths)
            else AuditPaths(
                directory=Path(paths["directory"]),
                json=Path(paths["json"]),
                markdown=Path(paths["markdown"]),
            )
        )
        self.references = (
            deepcopy(reference_builder(self.audit_paths))
            if reference_builder
            else local_report_references(self.audit_paths)
        )

    @property
    def paths(self) -> dict[str, Path]:
        return self.audit_paths.as_dict()

    def build_envelope(
        self,
        *,
        status: str,
        job_identity: dict[str, Any] | None,
        processing_summary: dict[str, Any],
        lifecycle: dict[str, Any] | None,
        publication: dict[str, Any],
        failure: dict[str, Any] | None,
        command_details: dict[str, Any],
    ) -> dict[str, Any]:
        return json_safe(
            {
                "schema_name": AUDIT_REPORT_SCHEMA_NAME,
                "schema_version": AUDIT_REPORT_SCHEMA_VERSION,
                "run_identity": self.context.run_identity(status),
                "job_identity": job_identity,
                "configuration_snapshot": deepcopy(
                    self.context.configuration_snapshot
                ),
                "processing_summary": processing_summary,
                "lifecycle": lifecycle,
                "publication": publication,
                "failure": failure,
                "report_artifacts": deepcopy(self.references),
                "command_details": command_details,
            }
        )

    def write(
        self,
        *,
        status: str,
        job_identity: dict[str, Any] | None,
        processing_summary: dict[str, Any],
        lifecycle: dict[str, Any] | None,
        publication: dict[str, Any],
        failure: dict[str, Any] | None,
        command_details: dict[str, Any],
        renderer: MarkdownRenderer,
        finalize_payload: (
            Callable[[dict[str, Any], AuditPaths], dict[str, Any] | None] | None
        ) = None,
    ) -> AuditWriteResult:
        report = self.build_envelope(
            status=status,
            job_identity=job_identity,
            processing_summary=processing_summary,
            lifecycle=lifecycle,
            publication=publication,
            failure=failure,
            command_details=command_details,
        )
        try:
            validate_artifact(report, "audit report", self.audit_paths.json)
            markdown = renderer(deepcopy(report)).rstrip() + "\n"
            markdown_bytes = markdown.encode("utf-8")
            _write_bytes_atomically(self.audit_paths.markdown, markdown_bytes)
            if finalize_payload is not None:
                finalized = finalize_payload(report, self.audit_paths)
                if finalized is not None:
                    report = json_safe(finalized)
            validate_artifact(report, "audit report", self.audit_paths.json)
            json_bytes = deterministic_json(report).encode("utf-8")
            _write_bytes_atomically(self.audit_paths.json, json_bytes)
        except Exception as exc:
            if isinstance(exc, AuditWriteError):
                raise
            raise AuditWriteError(
                f"Audit report write failed for {self.context.command_name}: {exc}"
            ) from exc
        return AuditWriteResult(
            report=report,
            paths=self.paths,
            references=deepcopy(self.references),
            local_writes={
                "json": LocalAuditWrite(self.audit_paths.json, len(json_bytes)),
                "markdown": LocalAuditWrite(
                    self.audit_paths.markdown, len(markdown_bytes)
                ),
            },
        )


def _config_payload(config: Mapping[str, Any] | None) -> dict[str, Any]:
    if config is None:
        return {}
    converter = getattr(config, "to_payload", None)
    value = converter() if callable(converter) else dict(config)
    return value if isinstance(value, dict) else {}


def _secret_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    return bool(
        re.search(
            r"(?:^|_)(?:api_key|apikey|access_key|secret|secret_key|token|password|credential|credentials|authorization)(?:$|_)",
            normalized,
        )
    )


_OMIT = object()


def _safe_configuration_value(value: Any, key: str | None = None) -> Any:
    if key is not None and _secret_key(key):
        return REDACTED
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if value == value and value not in (float("inf"), float("-inf")) else _OMIT
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for raw_key, item in value.items():
            item_key = str(raw_key)
            if item_key.startswith("_"):
                continue
            safe_item = _safe_configuration_value(item, item_key)
            if safe_item is not _OMIT:
                sanitized[item_key] = safe_item
        return sanitized
    if isinstance(value, (list, tuple)):
        sanitized_items = [_safe_configuration_value(item) for item in value]
        return [item for item in sanitized_items if item is not _OMIT]
    # Paths, compiled expressions, providers, clients, and all other runtime
    # objects are deliberately absent from a configuration snapshot.
    return _OMIT


def safe_configuration_snapshot(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return only schema-shaped, JSON-safe configuration with secrets removed."""
    payload = _config_payload(config)
    selected = {
        key: payload[key]
        for key in CONFIG_SNAPSHOT_KEYS
        if key in payload
    }
    sanitized = _safe_configuration_value(selected)
    return sanitized if isinstance(sanitized, dict) else {}


def redact_value(key: str, value: Any) -> Any:
    """Compatibility helper for callers that need the centralized policy."""
    safe = _safe_configuration_value(value, key)
    return None if safe is _OMIT else safe


def redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    sanitized = _safe_configuration_value(data)
    return sanitized if isinstance(sanitized, dict) else {}


def json_safe(data: Any) -> Any:
    if isinstance(data, Path):
        return str(data)
    if isinstance(data, Enum):
        return json_safe(data.value)
    if isinstance(data, Mapping):
        return {str(key): json_safe(value) for key, value in data.items()}
    if isinstance(data, (list, tuple)):
        return [json_safe(value) for value in data]
    return data


def deterministic_json(data: Any) -> str:
    return json.dumps(
        json_safe(data), ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"


def _write_bytes_atomically(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def resolved_build_provenance(path: str | Path) -> dict[str, Any]:
    """Resolve provenance from an image manifest before consulting a checkout."""
    embedded = embedded_build_provenance()
    if embedded:
        return {"source": "embedded-container-manifest", **embedded}
    commit_sha = git_commit_sha(path)
    return {
        "source": "native-git-checkout" if commit_sha else "unavailable",
        "source_revision": commit_sha,
        "image_revision": None,
        "image_version": None,
        "image_created": None,
    }


def embedded_build_provenance() -> dict[str, Any] | None:
    """Return non-secret provenance embedded when a container image is built."""
    manifest_path = os.environ.get(
        "GURUBODH_BUILD_PROVENANCE_FILE",
        str(Path(__file__).with_name("build_provenance.json")),
    )
    try:
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    source_revision = payload.get("source_revision")
    if not isinstance(source_revision, str) or not source_revision:
        return None
    return {
        "source_revision": source_revision,
        "image_revision": payload.get("image_revision") or source_revision,
        "image_version": payload.get("image_version"),
        "image_created": payload.get("image_created"),
    }


def git_commit_sha(path: str | Path) -> str | None:
    previous_tokenizer_parallelism = os.environ.get("TOKENIZERS_PARALLELISM")
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    finally:
        if previous_tokenizer_parallelism is None:
            os.environ.pop("TOKENIZERS_PARALLELISM", None)
        else:
            os.environ["TOKENIZERS_PARALLELISM"] = previous_tokenizer_parallelism
    return result.stdout.strip() or None


def report_paths(
    subject_dir: str | Path,
    basename: str,
    command_name: str | None = None,
) -> AuditPaths:
    report_dir = Path(subject_dir) / "run_reports"
    if command_name:
        report_dir /= command_name
    return AuditPaths(
        directory=report_dir,
        json=report_dir / f"{basename}.json",
        markdown=report_dir / f"{basename}.md",
    )


def report_basename(context: AuditContext) -> str:
    command = re.sub(r"[^a-z0-9]+", "-", context.command_name.lower()).strip("-")
    run_suffix = re.sub(r"[^A-Za-z0-9]+", "", context.run_id)[:8] or "run"
    return f"{command}-{context.filename_timestamp}-{run_suffix}"


def local_report_references(
    paths: AuditPaths, relative_to: str | Path | None = None
) -> dict[str, Any]:
    root = Path(relative_to) if relative_to is not None else None
    return {
        kind: {
            "backend": "local",
            "path": str(
                getattr(paths, kind).relative_to(root)
                if root is not None
                else getattr(paths, kind)
            ),
            "url": None,
        }
        for kind in ("json", "markdown")
    }


def destination_report_references(
    config: Mapping[str, Any], relative_directory: Path, paths: AuditPaths
) -> dict[str, Any]:
    """Build local or R2 references for a subject-scoped report pair."""
    from gurubodh.storage import destination_artifact_reference

    return {
        kind: destination_artifact_reference(
            config, relative_directory / getattr(paths, kind).name
        )
        for kind in ("json", "markdown")
    }


def bounded_failure(error: BaseException, stage: str) -> dict[str, Any]:
    """Return the common, text-bounded failure shape used by every workflow."""
    message = " ".join(str(error).split())[:500] or error.__class__.__name__
    return {
        "stage": str(stage)[:80],
        "code": str(getattr(error, "code", "unexpected_error"))[:80],
        "error_type": error.__class__.__name__[:120],
        "message": message,
        "request_diagnostics": safe_request_diagnostics(error),
    }


def warn_audit_failure(
    command_name: str,
    audit_error: BaseException,
    primary_error: BaseException,
) -> None:
    """Make secondary audit failure visible without replacing the workflow error."""
    message = " ".join(str(audit_error).split())[:500] or audit_error.__class__.__name__
    primary = primary_error.__class__.__name__
    print(
        f"WARNING: {command_name} audit reporting failed while preserving the primary "
        f"{primary}: {message}",
        file=sys.stderr,
    )


def print_report_locations(command_name: str, paths: Mapping[str, Path]) -> None:
    print(f"{command_name} audit reports:")
    print(f"  directory: {paths['directory']}")
    print(f"  {paths['json'].name}")
    print(f"  {paths['markdown'].name}")
