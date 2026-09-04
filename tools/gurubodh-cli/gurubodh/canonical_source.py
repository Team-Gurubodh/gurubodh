"""Shared materialization and validation for canonical prepared chapters."""

import hashlib
import json
import tempfile
from copy import deepcopy
from pathlib import Path, PurePosixPath

from gurubodh.contracts import (
    CandidateChapterBinding,
    CandidateManifestBinding,
    MaterializedChapterSource,
    R2Client,
)
from gurubodh.content_identity import validate_content_identity
from gurubodh.errors import (
    GurubodhError,
    ProcessingError,
    SourceValidationError,
    StorageError,
)
from gurubodh.prep_subject_checkpoints import validate_canonical_release_gate
from gurubodh.schema_validation import validate_artifact
from gurubodh.storage import (
    R2StorageClient,
    is_local,
    is_r2,
    optional_url,
    subject_artifact_object_key,
    subject_artifact_prefix,
)


TEXT_AND_METADATA_RELATIVE_DIR = Path("chapters") / "text_and_metadata"
CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH = Path("chapters") / "chapter_content_manifest.json"
SUPPORTED_CHAPTER_METADATA_SCHEMA_VERSIONS = {"1.3.0", "1.4.0"}


def materialize_source_subject(
    config, command_name, r2_client: R2Client | None = None, progress=print
):
    """Read the authoritative manifest, then only its selected artifacts."""
    source = config["source"]
    if is_local(source):
        subject_dir = Path(source["root_dir"]).expanduser() / source["subject_dir"]
        if not subject_dir.is_dir():
            raise SourceValidationError(f"Configured source subject directory does not exist: {subject_dir}")
        manifest = read_candidate_manifest(config, subject_dir / CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH, command_name)
        return subject_dir, None, manifest

    temp_dir = tempfile.TemporaryDirectory(prefix=f"gurubodh-{command_name}-source-")
    subject_dir = Path(temp_dir.name) / source["subject_dir"]
    client = r2_client or R2StorageClient.from_env()
    manifest_key = subject_artifact_object_key(source, CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH)
    manifest_path = subject_dir / CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH
    progress("Reading canonical chapter manifest from:")
    progress(f"  r2://{source['bucket']}/{manifest_key}")
    try:
        client.download_file(source["bucket"], manifest_key, manifest_path)
        manifest = read_candidate_manifest(config, manifest_path, command_name)
        selected = manifest.selected_chapters
        width = max(2, len(str(len(selected))))
        for index, candidate in enumerate(selected, start=1):
            for kind in ("metadata", "text"):
                reference = getattr(candidate, f"{kind}_artifact")
                relative_path, key = artifact_relative_path(source, reference, kind)
                client.download_file(source["bucket"], key, subject_dir / relative_path)
            progress(
                f"[{index:0{width}d}/{len(selected):0{width}d}] "
                f"chapter {candidate.generated_chapter_number} (metadata, text)"
            )
    except GurubodhError:
        temp_dir.cleanup()
        raise
    except Exception as exc:
        temp_dir.cleanup()
        raise StorageError(f"R2 source materialization failed: {exc}") from exc
    return subject_dir, temp_dir, manifest


def read_candidate_manifest(
    config, manifest_path, command_name
) -> CandidateManifestBinding:
    try:
        raw = Path(manifest_path).read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceValidationError(f"Candidate chapter manifest is missing or malformed: {manifest_path}: {exc}") from exc
    try:
        validate_artifact(manifest, "chapter content manifest", manifest_path)
    except ProcessingError as exc:
        raise SourceValidationError(str(exc)) from exc
    expected_subject = {
        "category_code": config["naming"]["category_code"],
        "subject_code": config["naming"]["subject_code"],
        "language": config["naming"]["language"],
    }
    if manifest.get("subject") != expected_subject:
        raise SourceValidationError(
            f"Candidate chapter manifest subject identity does not match the {command_name} job configuration."
        )
    entries = manifest.get("chapters")
    if not isinstance(entries, list) or not entries:
        raise SourceValidationError("Candidate chapter manifest must contain a non-empty chapters array.")
    candidates, numbers = [], set()
    for entry in entries:
        number = entry.get("generated_chapter_number") if isinstance(entry, dict) else None
        if not isinstance(number, str) or len(number) != 3 or not number.isdigit():
            raise SourceValidationError("Candidate chapter manifest has an invalid generated_chapter_number.")
        if number in numbers:
            raise SourceValidationError(f"Candidate chapter manifest contains duplicate chapter number: {number}")
        numbers.add(number)
        if not isinstance(entry.get("content_key"), str) or not isinstance(
            entry.get("normalized_content_sha256"), str
        ):
            raise SourceValidationError(f"Candidate chapter manifest entry {number} is missing content identity fields.")
        metadata_artifact, text_artifact = entry.get("metadata_artifact"), entry.get("text_artifact")
        artifact_relative_path(config["source"], metadata_artifact, "metadata")
        artifact_relative_path(config["source"], text_artifact, "text")
        candidates.append(
            CandidateChapterBinding.from_payload(
                {
                    "generated_chapter_number": number,
                    "content_key": entry["content_key"],
                    "normalized_content_sha256": entry[
                        "normalized_content_sha256"
                    ],
                    "metadata_artifact": metadata_artifact,
                    "text_artifact": text_artifact,
                }
            )
        )
    requested = set(config.get("chapters") or [])
    missing = sorted(requested - numbers)
    if missing:
        raise SourceValidationError(f"Requested chapter number(s) are absent from the candidate manifest: {', '.join(missing)}")
    return CandidateManifestBinding(
        path=Path(manifest_path),
        sha256=hashlib.sha256(raw).hexdigest(),
        reference=source_manifest_reference(config),
        chapters=tuple(candidates),
        selected_chapters=tuple(
            candidate
            for candidate in candidates
            if not requested or candidate.generated_chapter_number in requested
        ),
    )


def safe_relative_path(value, context):
    if not isinstance(value, str) or not value or "\\" in value:
        raise SourceValidationError(f"{context} must be a non-empty POSIX relative path.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise SourceValidationError(f"{context} must not escape the subject artifact tree.")
    return Path(*path.parts)


def artifact_relative_path(source, reference, kind):
    if not isinstance(reference, dict):
        raise SourceValidationError(f"Candidate manifest {kind}_artifact must be an object.")
    suffix = ".json" if kind == "metadata" else ".txt"
    if is_local(source):
        if (
            reference.get("backend") != "local"
            or not isinstance(reference.get("path"), str)
            or set(reference) != {"backend", "path", "url"}
        ):
            raise SourceValidationError(f"Candidate manifest {kind}_artifact must be a local storage reference.")
        relative_path = safe_relative_path(reference["path"], f"candidate manifest {kind}_artifact.path")
        if relative_path.parent != TEXT_AND_METADATA_RELATIVE_DIR or relative_path.suffix != suffix:
            raise SourceValidationError(
                f"Candidate manifest {kind}_artifact must reference chapters/text_and_metadata/*{suffix}."
            )
        return relative_path, None
    if (
        reference.get("backend") != "r2"
        or reference.get("bucket") != source["bucket"]
        or not isinstance(reference.get("key"), str)
        or set(reference) != {"backend", "bucket", "key", "url"}
    ):
        raise SourceValidationError(
            f"Candidate manifest {kind}_artifact must be an R2 reference in the configured source bucket."
        )
    key, prefix = reference["key"], subject_artifact_prefix(source)
    if not key.startswith(prefix):
        raise SourceValidationError(f"Candidate manifest {kind}_artifact escapes the configured source subject prefix.")
    relative_path = safe_relative_path(key.removeprefix(prefix), f"candidate manifest {kind}_artifact.key")
    if (
        key != subject_artifact_object_key(source, relative_path)
        or relative_path.parent != TEXT_AND_METADATA_RELATIVE_DIR
        or relative_path.suffix != suffix
    ):
        raise SourceValidationError(
            f"Candidate manifest {kind}_artifact must reference chapters/text_and_metadata/*{suffix}."
        )
    return relative_path, key


def source_manifest_reference(config):
    source = config["source"]
    if is_local(source):
        return {"backend": "local", "path": str(CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH), "url": None}
    key = subject_artifact_object_key(source, CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH)
    return {
        "backend": "r2",
        "bucket": source["bucket"],
        "key": key,
        "url": optional_url(source.get("url_base"), key),
    }


def subject_artifact_path(subject_dir, relative_path, context):
    root = Path(subject_dir).resolve()
    target = (root / relative_path).resolve()
    if not target.is_relative_to(root):
        raise SourceValidationError(f"{context} escapes the source subject artifact tree.")
    return target


def validate_materialized_candidates(
    config, source_subject, candidate_manifest: CandidateManifestBinding
) -> list[MaterializedChapterSource]:
    """Verify every selected manifest entry, metadata document, and text artifact."""
    sources = []
    expected_document = {
        "category_code": config["naming"]["category_code"],
        "subject_code": config["naming"]["subject_code"],
        "title_slug": config["naming"]["title_slug"],
        "language": config["naming"]["language"],
    }
    for candidate in candidate_manifest.selected_chapters:
        number = candidate.generated_chapter_number
        metadata_relative, _ = artifact_relative_path(config["source"], candidate.metadata_artifact, "metadata")
        text_relative, _ = artifact_relative_path(config["source"], candidate.text_artifact, "text")
        metadata_path = subject_artifact_path(source_subject, metadata_relative, "Candidate metadata artifact")
        text_path = subject_artifact_path(source_subject, text_relative, "Candidate text artifact")
        if not metadata_path.is_file() or not text_path.is_file():
            raise SourceValidationError(f"Candidate chapter {number} has a missing manifest-referenced artifact.")
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            text_bytes = text_path.read_bytes()
            text = text_bytes.decode("utf-8")
            document = metadata["document"]
            storage = metadata["storage"]["artifacts"]
            integrity = metadata["integrity"]["artifacts"]["text"]
        except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise SourceValidationError(f"Candidate chapter {number} has malformed prepared metadata or text: {exc}") from exc
        if metadata.get("schema_version") not in SUPPORTED_CHAPTER_METADATA_SCHEMA_VERSIONS:
            raise SourceValidationError(
                f"Candidate chapter {number} uses unsupported chapter metadata schema_version: "
                f"{metadata.get('schema_version')!r}."
            )
        if {key: document.get(key) for key in expected_document} != expected_document:
            raise SourceValidationError(f"Candidate chapter {number} metadata subject identity does not match the job.")
        if document.get("chapter_number") != number:
            raise SourceValidationError(f"Candidate manifest and metadata disagree on chapter number for {number}.")
        files = metadata.get("files", {})
        if files.get("metadata_filename") != metadata_path.name or files.get("text_filename") != text_path.name:
            raise SourceValidationError(f"Candidate chapter {number} metadata filenames disagree with manifest references.")
        if metadata_path.stem != text_path.stem:
            raise SourceValidationError(f"Candidate chapter {number} metadata and text filenames do not share a canonical stem.")
        if storage.get("metadata") != candidate.metadata_artifact or storage.get("text") != candidate.text_artifact:
            raise SourceValidationError(f"Candidate chapter {number} metadata storage references disagree with the manifest.")
        expected_checksum = hashlib.sha256(text_bytes).hexdigest()
        if (
            not isinstance(integrity, dict)
            or integrity.get("algorithm") != "sha256"
            or integrity.get("encoding") != "UTF-8"
            or integrity.get("line_endings") != "LF"
            or integrity.get("scope") != "artifact-bytes"
            or integrity.get("value") != expected_checksum
            or "\r" in text
        ):
            raise SourceValidationError(f"Candidate chapter {number} source text checksum does not match metadata.")
        try:
            identity = validate_content_identity(
                metadata.get("content_identity"),
                document["category_code"],
                document["subject_code"],
                document["language"],
                text,
            )
        except (KeyError, ValueError) as exc:
            raise SourceValidationError(f"Prepared chapter {metadata_path} has missing or invalid content_identity: {exc}") from exc
        if (
            identity["content_key"] != candidate.content_key
            or identity["normalized_content_sha256"] != candidate.normalized_content_sha256
        ):
            raise SourceValidationError(f"Candidate manifest and metadata content identity disagree for chapter {number}.")
        sources.append(
            MaterializedChapterSource(
                chapter_number=number,
                text_path=text_path,
                metadata_path=metadata_path,
                metadata=deepcopy(metadata),
                text_artifact=deepcopy(candidate.text_artifact),
                text_artifact_sha256=expected_checksum,
            )
        )
    return sources


def validate_materialized_release(config, source_subject, candidate_manifest, command_name, r2_client=None):
    sources = validate_materialized_candidates(config, source_subject, candidate_manifest)
    validate_canonical_release_gate(
        config,
        source_subject,
        candidate_manifest.to_internal_payload(),
        command_name=command_name,
        r2_client=r2_client,
    )
    return sources


def revalidate_source_release(config, expected_manifest, command_name, r2_client=None):
    """Re-read source readiness and manifest binding immediately before publication."""
    source = config["source"]
    if is_local(source):
        source_subject = Path(source["root_dir"]).expanduser() / source["subject_dir"]
        manifest_path = source_subject / CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH
        current = read_candidate_manifest(config, manifest_path, command_name)
    else:
        client = r2_client or R2StorageClient.from_env()
        temp_dir = tempfile.TemporaryDirectory(prefix=f"gurubodh-{command_name}-revalidate-")
        try:
            source_subject = Path(temp_dir.name) / source["subject_dir"]
            manifest_path = source_subject / CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH
            client.download_file(
                source["bucket"],
                subject_artifact_object_key(source, CHAPTER_CONTENT_MANIFEST_RELATIVE_PATH),
                manifest_path,
            )
            current = read_candidate_manifest(config, manifest_path, command_name)
            validate_canonical_release_gate(
                config,
                source_subject,
                current.to_internal_payload(),
                command_name=command_name,
                r2_client=client,
            )
        finally:
            temp_dir.cleanup()
        if current.sha256 != expected_manifest.sha256:
            raise SourceValidationError(
                f"{command_name} aborted because the canonical chapter manifest changed before publication."
            )
        return
    validate_canonical_release_gate(
        config,
        source_subject,
        current.to_internal_payload(),
        command_name=command_name,
        r2_client=r2_client,
    )
    if current.sha256 != expected_manifest.sha256:
        raise SourceValidationError(f"{command_name} aborted because the canonical chapter manifest changed before publication.")
