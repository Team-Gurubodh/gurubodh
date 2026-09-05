"""Typed internal workflow contracts.

JSON jobs and artifacts remain dictionaries at their serialization boundaries.
The records in this module make runtime-only values, ownership, and conversion
points explicit while preserving those established payloads.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from re import Pattern
from typing import TYPE_CHECKING, Any, Callable, NotRequired, Protocol, TypedDict

if TYPE_CHECKING:
    from gurubodh.locales import LocaleSpec
    from gurubodh.ml.semantic_chunking.config import SemanticChunkConfig
    from gurubodh.proofreading.settings import ProofreadingSettings


JsonObject = dict[str, Any]
ArtifactReference = dict[str, Any]


class R2Downloader(Protocol):
    """Minimal source-download seam."""

    def download_file(self, bucket: str, key: str, path: Path) -> None: ...


class R2Uploader(Protocol):
    """Minimal artifact-upload seam."""

    def upload_file(self, path: Path, bucket: str, key: str) -> None: ...


class R2Client(R2Downloader, R2Uploader, Protocol):
    """Complete object-store seam used by publication workflows."""

    def exists(self, bucket: str, key: str) -> bool: ...

    def prefix_has_objects(self, bucket: str, prefix: str) -> bool: ...

    def list_keys(self, bucket: str, prefix: str) -> list[str]: ...

    def delete_prefix(self, bucket: str, prefix: str) -> list[str]: ...

    def delete_keys(self, bucket: str, keys: list[str]) -> list[str]: ...

class CleanupResource(Protocol):
    def cleanup(self) -> None: ...


class ProofreadingProviderResponse(TypedDict):
    """Validated provider-neutral proofreading result and bounded request facts."""

    corrected_text: str
    edits: list[dict[str, str]]
    estimated_input_tokens: int
    attempts: int
    successful_request_attempts: NotRequired[int]
    failed_request_attempts: NotRequired[int]
    throttle_seconds: float
    usage: dict[str, int] | None
    request_diagnostics: NotRequired[JsonObject | None]


class Proofreader(Protocol):
    """Provider-neutral seam shared by production providers and test fakes."""

    def proofread(
        self, text: str, progress: Callable[[str], None] | None = None
    ) -> ProofreadingProviderResponse: ...


@dataclass(frozen=True)
class PreparedJob(Mapping[str, Any]):
    """A schema-validated job payload with separately owned runtime values."""

    _payload: JsonObject = field(repr=False)
    locale: LocaleSpec

    def __getitem__(self, key: str) -> Any:
        return self._payload[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._payload)

    def __len__(self) -> int:
        return len(self._payload)

    def get(self, key: str, default: Any = None) -> Any:
        return self._payload.get(key, default)

    def to_payload(self) -> JsonObject:
        """Return an isolated JSON-compatible job payload."""
        return deepcopy(self._payload)


@dataclass(frozen=True)
class PrepSubjectJob(PreparedJob):
    proofreading_settings: ProofreadingSettings
    compiled_chapter_pattern: Pattern[str] | None = field(
        default=None, repr=False, compare=False
    )


@dataclass(frozen=True)
class GenerateChunksJob(PreparedJob):
    semantic_chunk_config: SemanticChunkConfig


@dataclass(frozen=True)
class GenerateDocxJob(PreparedJob):
    pass


@dataclass(frozen=True)
class CandidateChapterBinding(Mapping[str, Any]):
    generated_chapter_number: str
    content_key: str
    normalized_content_sha256: str
    metadata_artifact: ArtifactReference
    text_artifact: ArtifactReference

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> CandidateChapterBinding:
        return cls(
            generated_chapter_number=payload["generated_chapter_number"],
            content_key=payload["content_key"],
            normalized_content_sha256=payload["normalized_content_sha256"],
            metadata_artifact=deepcopy(payload["metadata_artifact"]),
            text_artifact=deepcopy(payload["text_artifact"]),
        )

    def to_payload(self) -> JsonObject:
        return {
            "generated_chapter_number": self.generated_chapter_number,
            "content_key": self.content_key,
            "normalized_content_sha256": self.normalized_content_sha256,
            "metadata_artifact": deepcopy(self.metadata_artifact),
            "text_artifact": deepcopy(self.text_artifact),
        }

    def __getitem__(self, key: str) -> Any:
        return self.to_payload()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_payload())

    def __len__(self) -> int:
        return len(self.to_payload())


@dataclass(frozen=True)
class CandidateManifestBinding(Mapping[str, Any]):
    path: Path
    sha256: str
    reference: ArtifactReference
    chapters: tuple[CandidateChapterBinding, ...]
    selected_chapters: tuple[CandidateChapterBinding, ...]

    @classmethod
    def from_internal_payload(
        cls, payload: Mapping[str, Any]
    ) -> CandidateManifestBinding:
        chapters = tuple(
            CandidateChapterBinding.from_payload(item) for item in payload["chapters"]
        )
        chapters_by_number = {
            item.generated_chapter_number: item for item in chapters
        }
        return cls(
            path=Path(payload["path"]),
            sha256=payload["sha256"],
            reference=deepcopy(payload["reference"]),
            chapters=chapters,
            selected_chapters=tuple(
                chapters_by_number[item["generated_chapter_number"]]
                for item in payload["selected_chapters"]
            ),
        )

    def serialized_binding(self) -> JsonObject:
        return {"reference": deepcopy(self.reference), "sha256": self.sha256}

    def to_internal_payload(self) -> JsonObject:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "reference": deepcopy(self.reference),
            "chapters": [chapter.to_payload() for chapter in self.chapters],
            "selected_chapters": [
                chapter.to_payload() for chapter in self.selected_chapters
            ],
        }

    def __getitem__(self, key: str) -> Any:
        return self.to_internal_payload()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_internal_payload())

    def __len__(self) -> int:
        return len(self.to_internal_payload())

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_internal_payload().get(key, default)


@dataclass(frozen=True)
class MaterializedChapterSource:
    chapter_number: str
    text_path: Path
    metadata_path: Path
    metadata: JsonObject
    text_artifact: ArtifactReference
    text_artifact_sha256: str


@dataclass
class MaterializedSource:
    subject_dir: Path
    candidate_manifest: CandidateManifestBinding
    sources: list[MaterializedChapterSource]
    temporary_resource: CleanupResource | None = field(default=None, repr=False)

    def cleanup(self) -> None:
        if self.temporary_resource is not None:
            self.temporary_resource.cleanup()

    @property
    def chapters(self) -> list[MaterializedChapterSource]:
        return self.sources


@dataclass(frozen=True)
class CheckpointArtifactRecord:
    path: str
    sha256: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> CheckpointArtifactRecord:
        return cls(path=payload["path"], sha256=payload["sha256"])

    def to_payload(self) -> dict[str, str]:
        return {"path": self.path, "sha256": self.sha256}


class ProofreadingStatus(str, Enum):
    SUCCEEDED = "succeeded"


@dataclass(frozen=True)
class ProofreadingOutcome:
    chapter_number: str
    status: ProofreadingStatus
    correction_count: int
    request_attempts: int
    successful_request_attempts: int
    request_diagnostics: JsonObject | None
    local_diff_summary: JsonObject
    unmodified_source_content_key: str
    canonical_content_key: str
    artifacts: JsonObject
    checkpoint_artifacts: tuple[CheckpointArtifactRecord, ...]

    def proofreading_payload(self) -> JsonObject:
        """Convert to the exact persisted per-chapter proofreading record."""
        return {
            "chapter_number": self.chapter_number,
            "status": self.status.value,
            "correction_count": self.correction_count,
            "request_diagnostics": deepcopy(self.request_diagnostics),
            "local_diff_summary": deepcopy(self.local_diff_summary),
            "unmodified_source_content_key": self.unmodified_source_content_key,
            "canonical_content_key": self.canonical_content_key,
            "artifacts": deepcopy(self.artifacts),
        }


class PrepJobStatus(str, Enum):
    RUNNING = "running"
    INCOMPLETE = "incomplete"
    FAILED = "failed"
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHING = "publishing"
    SUCCEEDED = "succeeded"


class ChapterStatus(str, Enum):
    PENDING = "pending"
    FAILED = "failed"
    SUCCEEDED = "succeeded"


class PublicationStatus(str, Enum):
    NOT_READY = "not_ready"
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHING = "publishing"
    SUCCEEDED = "succeeded"


@dataclass
class PrepPublicationState:
    """Typed owner of the checkpoint's extensible publication sub-record."""

    payload: JsonObject

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> PrepPublicationState:
        record = cls(deepcopy(dict(payload)))
        if record.payload.get("state") is not None:
            PublicationStatus(record.payload["state"])
        return record

    @property
    def status(self) -> PublicationStatus:
        return PublicationStatus(self.payload["state"])

    @status.setter
    def status(self, value: PublicationStatus) -> None:
        self.payload["state"] = value.value

    def to_payload(self) -> JsonObject:
        return deepcopy(self.payload)


@dataclass
class PrepCheckpointState:
    """Typed owner of the schema-governed prep checkpoint payload."""

    payload: JsonObject

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> PrepCheckpointState:
        isolated = deepcopy(dict(payload))
        if (
            "replacement_authorized" in isolated
            and not isinstance(isolated["replacement_authorized"], bool)
        ):
            raise TypeError("replacement_authorized must be a boolean")
        state = isolated.get("state")
        if state is not None:
            PrepJobStatus(state)
        for chapter in isolated.get("chapters", []):
            ChapterStatus(chapter["state"])
        publication = isolated.get("publication") or {}
        if publication.get("state") is not None:
            PublicationStatus(publication["state"])
        return cls(isolated)

    def to_payload(self) -> JsonObject:
        return deepcopy(self.payload)

    @property
    def status(self) -> PrepJobStatus:
        return PrepJobStatus(self.payload["state"])

    @status.setter
    def status(self, value: PrepJobStatus) -> None:
        self.payload["state"] = value.value

    @property
    def replacement_authorized(self) -> bool:
        value = self.payload["replacement_authorized"]
        if not isinstance(value, bool):
            raise TypeError("replacement_authorized must be a boolean")
        return value

    @property
    def publication_status(self) -> PublicationStatus:
        return self.publication.status

    @publication_status.setter
    def publication_status(self, value: PublicationStatus) -> None:
        publication = self.publication
        publication.status = value
        self.publication = publication

    @property
    def publication(self) -> PrepPublicationState:
        record = PrepPublicationState(self.payload["publication"])
        PublicationStatus(record.payload["state"])
        return record

    @publication.setter
    def publication(self, value: PrepPublicationState) -> None:
        self.payload["publication"] = value.to_payload()

    def __getitem__(self, key: str) -> Any:
        return self.payload[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.payload[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.payload.get(key, default)


class GenerationStatus(str, Enum):
    RUNNING = "running"
    FAILED = "failed"
    SUCCEEDED = "succeeded"


@dataclass
class ChunkChapterSummary:
    chapter_number: str
    status: GenerationStatus
    source_text_filename: str
    source_metadata_filename: str
    chunk_filename: str
    source_text_artifact: ArtifactReference
    source_metadata_artifact: ArtifactReference
    content_key: str
    normalized_content_sha256: str
    chunk_count: int = 0
    estimated_token_count: int = 0
    error: str | None = None
    chunk_artifact: ArtifactReference | None = None
    chunk_artifact_sha256: str | None = None
    source_text_checksum: JsonObject | None = None
    breakpoint_threshold: float | None = None

    def to_payload(self) -> JsonObject:
        if self.status is GenerationStatus.SUCCEEDED:
            return {
                "chapter_number": self.chapter_number,
                "status": self.status.value,
                "source_text_filename": self.source_text_filename,
                "source_metadata_filename": self.source_metadata_filename,
                "chunk_filename": self.chunk_filename,
                "source_text_artifact": deepcopy(self.source_text_artifact),
                "source_metadata_artifact": deepcopy(
                    self.source_metadata_artifact
                ),
                "chunk_artifact": deepcopy(self.chunk_artifact),
                "chunk_artifact_sha256": self.chunk_artifact_sha256,
                "source_text_checksum": deepcopy(self.source_text_checksum),
                "content_key": self.content_key,
                "normalized_content_sha256": self.normalized_content_sha256,
                "chunk_count": self.chunk_count,
                "estimated_token_count": self.estimated_token_count,
                "breakpoint_threshold": self.breakpoint_threshold,
                "error": self.error,
            }
        payload = {
            "chapter_number": self.chapter_number,
            "status": self.status.value,
            "source_text_filename": self.source_text_filename,
            "source_metadata_filename": self.source_metadata_filename,
            "chunk_filename": self.chunk_filename,
            "source_text_artifact": deepcopy(self.source_text_artifact),
            "source_metadata_artifact": deepcopy(self.source_metadata_artifact),
            "content_key": self.content_key,
            "normalized_content_sha256": self.normalized_content_sha256,
            "chunk_count": self.chunk_count,
            "estimated_token_count": self.estimated_token_count,
            "error": self.error,
        }
        return payload


@dataclass(frozen=True)
class ChunkGenerationPaths:
    source_subject: Path
    source_text_and_metadata: Path
    candidate_manifest: Path
    destination_subject: Path
    semantic_chunks: Path
    final_semantic_chunks: Path
    chunk_manifest: Path


@dataclass(frozen=True)
class ChunkGenerationJob:
    paths: ChunkGenerationPaths
    candidate_sources: tuple[MaterializedChapterSource, ...]
    candidate_manifest: CandidateManifestBinding
    destination_output_prefix: str | None


@dataclass
class ChunkGenerationSummary(Mapping[str, Any]):
    source_chapter_count: int
    processed_chapter_count: int = 0
    skipped_chapter_count: int = 0
    failed_chapter_count: int = 0
    chunk_artifacts_written: int = 0
    chunk_manifest_written: bool = False
    total_chunk_count: int = 0
    total_estimated_token_count: int = 0
    chapters: list[ChunkChapterSummary] = field(default_factory=list)
    audit_report_references: JsonObject | None = None
    publication: JsonObject | None = None
    audit_report: JsonObject | None = None
    lifecycle: JsonObject | None = None

    def to_payload(self) -> JsonObject:
        payload = {
            "source_chapter_count": self.source_chapter_count,
            "processed_chapter_count": self.processed_chapter_count,
            "skipped_chapter_count": self.skipped_chapter_count,
            "failed_chapter_count": self.failed_chapter_count,
            "chunk_artifacts_written": self.chunk_artifacts_written,
            "chunk_manifest_written": self.chunk_manifest_written,
            "total_chunk_count": self.total_chunk_count,
            "total_estimated_token_count": self.total_estimated_token_count,
            "chapters": [chapter.to_payload() for chapter in self.chapters],
            "audit_report_references": deepcopy(self.audit_report_references),
        }
        if self.publication is not None:
            payload["publication"] = deepcopy(self.publication)
        if self.audit_report is not None:
            payload["audit_report"] = deepcopy(self.audit_report)
        if self.lifecycle is not None:
            payload["lifecycle"] = deepcopy(self.lifecycle)
        return payload

    def __getitem__(self, key: str) -> Any:
        return self.to_payload()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_payload())

    def __len__(self) -> int:
        return len(self.to_payload())


@dataclass
class DocxChapterSummary:
    chapter_number: str
    content_key: str
    normalized_content_sha256: str
    source_text: JsonObject
    generated_title: str
    docx_filename: str
    docx_artifact: ArtifactReference
    docx_sha256: str | None = None
    status: GenerationStatus = GenerationStatus.RUNNING
    error: str | None = None

    def manifest_payload(self) -> JsonObject:
        return {
            "chapter_number": self.chapter_number,
            "content_key": self.content_key,
            "normalized_content_sha256": self.normalized_content_sha256,
            "source_text": deepcopy(self.source_text),
            "generated_title": self.generated_title,
            "docx_artifact": deepcopy(self.docx_artifact),
            "docx_sha256": self.docx_sha256,
        }

    def to_payload(self) -> JsonObject:
        return {
            "chapter_number": self.chapter_number,
            "content_key": self.content_key,
            "normalized_content_sha256": self.normalized_content_sha256,
            "source_text": deepcopy(self.source_text),
            "generated_title": self.generated_title,
            "docx_filename": self.docx_filename,
            "docx_artifact": deepcopy(self.docx_artifact),
            "docx_sha256": self.docx_sha256,
            "status": self.status.value,
            "error": self.error,
        }


@dataclass
class DocxGenerationSummary(Mapping[str, Any]):
    chapters: list[DocxChapterSummary] = field(default_factory=list)
    docx_manifest: ArtifactReference | None = None
    publication: JsonObject | None = None
    audit_report: JsonObject | None = None
    lifecycle: JsonObject | None = None

    @property
    def processed_chapter_count(self) -> int:
        return sum(
            1
            for chapter in self.chapters
            if chapter.status is GenerationStatus.SUCCEEDED
        )

    def to_payload(self) -> JsonObject:
        payload = {
            "processed_chapter_count": self.processed_chapter_count,
            "chapters": [chapter.to_payload() for chapter in self.chapters],
        }
        if self.docx_manifest is not None:
            payload["docx_manifest"] = deepcopy(self.docx_manifest)
        if self.publication is not None:
            payload["publication"] = deepcopy(self.publication)
        if self.audit_report is not None:
            payload["audit_report"] = deepcopy(self.audit_report)
        if self.lifecycle is not None:
            payload["lifecycle"] = deepcopy(self.lifecycle)
        return payload

    def __getitem__(self, key: str) -> Any:
        return self.to_payload()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_payload())

    def __len__(self) -> int:
        return len(self.to_payload())
