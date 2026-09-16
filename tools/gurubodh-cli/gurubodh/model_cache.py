"""Explicit preparation and offline verification of pinned model caches."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Callable

from gurubodh.errors import ConfigurationError, ProcessingError
from gurubodh.job_components import ComponentCatalog
from gurubodh.ml.embeddings import SentenceTransformerEmbeddingHelper
from gurubodh.ml.errors import ModelCacheConfigError
from gurubodh.ml.semantic_chunking.config import (
    SUPPORTED_MODEL_NAME,
    SUPPORTED_PROVIDER,
    SemanticChunkConfig,
    SemanticChunkConfigError,
)


MODEL_CACHE_CONTRACT_VERSION = "1.0.0"
MODEL_CACHE_CONTRACT_FILENAME = ".gurubodh-model-cache-contract.json"
IMMUTABLE_REVISION_PATTERN = re.compile(r"[0-9a-f]{40}")

# This is the complete SentenceTransformer runtime surface for the maintained
# BGE-M3 profile. Keep the weights choice singular: alternate formats and
# exports are deliberately excluded.
REQUIRED_RUNTIME_FILES = (
    "1_Pooling/config.json",
    "config.json",
    "config_sentence_transformers.json",
    "modules.json",
    "pytorch_model.bin",
    "sentence_bert_config.json",
    "sentencepiece.bpe.model",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
)


class ModelCacheError(ProcessingError):
    """A pinned model cache could not be prepared or verified."""


@dataclass(frozen=True)
class ResolvedModelProfile:
    """Validated chunking profile inputs needed by model-cache commands."""

    profile_id: str
    config: SemanticChunkConfig
    cache_dir: Path

    @property
    def model(self) -> str:
        return self.config.model_name

    @property
    def revision(self) -> str:
        assert self.config.model_revision is not None
        return self.config.model_revision


@dataclass(frozen=True)
class RequiredArtifact:
    """Integrity metadata reported by the selected immutable revision."""

    path: str
    size: int
    hash_algorithm: str
    digest: str

    def to_payload(self) -> dict[str, object]:
        return {
            "path": self.path,
            "size": self.size,
            "hash": {"algorithm": self.hash_algorithm, "digest": self.digest},
        }


def resolve_model_profile(catalog: ComponentCatalog, profile_id: str) -> ResolvedModelProfile:
    """Resolve a chunking profile through the normal component catalog."""
    snapshot = catalog.load("chunking-profile", profile_id)
    settings = dict(snapshot.to_payload()["chunking"])
    settings["model_name"] = settings.pop("model")
    try:
        config = SemanticChunkConfig.from_env(**settings)
        cache_dir = config.resolved_cache_dir()
    except (SemanticChunkConfigError, ModelCacheConfigError) as exc:
        raise ConfigurationError(f"Model-cache profile {profile_id!r} is invalid: {exc}") from exc

    if config.provider != SUPPORTED_PROVIDER or config.model_name != SUPPORTED_MODEL_NAME:
        raise ConfigurationError(
            f"Model-cache profile {profile_id!r} is unsupported. Only the maintained "
            f"{SUPPORTED_MODEL_NAME} SentenceTransformer runtime is supported."
        )
    if not config.local_files_only:
        raise ConfigurationError(
            f"Model-cache profile {profile_id!r} is unsupported: local_files_only must be true "
            "so ordinary chunk generation remains cached-only."
        )
    if not isinstance(config.model_revision, str) or IMMUTABLE_REVISION_PATTERN.fullmatch(
        config.model_revision
    ) is None:
        raise ConfigurationError(
            f"Model-cache profile {profile_id!r} must pin a full 40-character lowercase commit revision."
        )
    return ResolvedModelProfile(profile_id, config, cache_dir)


def prepare_model_cache(
    catalog: ComponentCatalog,
    profile_id: str,
    *,
    progress: Callable[[str], None] = print,
) -> None:
    """Download or repair only the required files, then verify offline."""
    profile = resolve_model_profile(catalog, profile_id)
    artifacts = _fetch_required_artifacts(profile)
    states = {artifact.path: _artifact_cache_state(profile, artifact) for artifact in artifacts}
    total_bytes = sum(artifact.size for artifact in artifacts)
    remaining_bytes = sum(
        artifact.size for artifact in artifacts if states[artifact.path] == "download"
    )

    _report_plan(profile, artifacts, total_bytes, remaining_bytes, progress)
    for artifact in artifacts:
        state = states[artifact.path]
        if state == "ready":
            continue
        _download_artifact(profile, artifact, force_download=state == "download")

    _write_contract(profile, artifacts, total_bytes)
    _verify_resolved_model_cache(profile, progress=progress)
    progress(
        f"Model-cache preparation succeeded for {profile.model} at {profile.revision}."
    )


def verify_model_cache(
    catalog: ComponentCatalog,
    profile_id: str,
    *,
    progress: Callable[[str], None] = print,
) -> None:
    """Verify artifact integrity and the real embedding runtime without repairs."""
    profile = resolve_model_profile(catalog, profile_id)
    _verify_resolved_model_cache(profile, progress=progress)


def _fetch_required_artifacts(profile: ResolvedModelProfile) -> tuple[RequiredArtifact, ...]:
    try:
        from huggingface_hub import HfApi

        info = HfApi().model_info(
            profile.model,
            revision=profile.revision,
            files_metadata=True,
        )
    except Exception as exc:
        raise ModelCacheError(
            f"Could not read metadata for {profile.model} at pinned revision {profile.revision}. "
            "Check network access and the model/revision, and ensure HF_HUB_OFFLINE is not set "
            "while running `gurubodh models prepare`."
        ) from exc

    if getattr(info, "sha", None) != profile.revision:
        raise ModelCacheError(
            f"Upstream metadata did not resolve to the requested immutable revision {profile.revision}; "
            "no artifact content was downloaded."
        )
    siblings = {sibling.rfilename: sibling for sibling in getattr(info, "siblings", ())}
    missing = [path for path in REQUIRED_RUNTIME_FILES if path not in siblings]
    if missing:
        raise ModelCacheError(
            f"Pinned revision {profile.revision} is missing required runtime files: "
            f"{', '.join(missing)}. No artifact content was downloaded and no whole-repository "
            "fallback was attempted."
        )

    artifacts = []
    for path in REQUIRED_RUNTIME_FILES:
        sibling = siblings[path]
        size = getattr(sibling, "size", None)
        blob_id = getattr(sibling, "blob_id", None)
        lfs = getattr(sibling, "lfs", None)
        lfs_sha256 = getattr(lfs, "sha256", None) if lfs is not None else None
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ModelCacheError(
                f"Pinned revision metadata does not provide a valid size for required file {path}; "
                "no artifact content was downloaded."
            )
        if lfs is not None:
            algorithm, digest = "sha256", lfs_sha256
            valid_digest = isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)
        else:
            algorithm, digest = "git-sha1", blob_id
            valid_digest = isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{40}", digest)
        if not valid_digest:
            raise ModelCacheError(
                f"Pinned revision metadata does not provide a valid content digest for required file {path}; "
                "no artifact content was downloaded."
            )
        artifacts.append(RequiredArtifact(path, size, algorithm, digest))
    return tuple(artifacts)


def _report_plan(profile, artifacts, total_bytes, remaining_bytes, progress) -> None:
    progress(f"Model: {profile.model}")
    progress(f"Revision: {profile.revision}")
    progress(f"Selected runtime files ({len(artifacts)}):")
    for artifact in artifacts:
        progress(f"- {artifact.path} ({artifact.size} bytes)")
    progress(f"Total required artifact bytes: {total_bytes} ({_format_bytes(total_bytes)})")
    progress(f"Remaining download bytes: {remaining_bytes} ({_format_bytes(remaining_bytes)})")


def _download_artifact(
    profile: ResolvedModelProfile,
    artifact: RequiredArtifact,
    *,
    force_download: bool,
) -> None:
    snapshot_file = _snapshot_dir(profile) / artifact.path
    # A damaged pointer must not keep referring to the wrong blob after a forced
    # download. Only the selected snapshot entry is removed; its blob and every
    # unrelated cache entry remain untouched.
    if snapshot_file.is_symlink() or snapshot_file.exists():
        snapshot_file.unlink()
    try:
        from huggingface_hub import hf_hub_download

        hf_hub_download(
            repo_id=profile.model,
            filename=artifact.path,
            revision=profile.revision,
            cache_dir=profile.cache_dir,
            force_download=force_download,
            local_files_only=False,
        )
    except Exception as exc:
        raise ModelCacheError(
            f"Failed to download required file {artifact.path} for {profile.model} at "
            f"{profile.revision}. The cache is not ready; rerun `gurubodh models prepare "
            f"--profile {profile.profile_id}` to resume or repair it."
        ) from exc
    if not _path_matches_artifact(snapshot_file, artifact):
        raise ModelCacheError(
            f"Downloaded file {artifact.path} failed its size or digest check. The cache is not ready; "
            f"rerun `gurubodh models prepare --profile {profile.profile_id}`."
        )


def _verify_resolved_model_cache(
    profile: ResolvedModelProfile,
    *,
    progress: Callable[[str], None],
) -> None:
    artifacts, total_bytes = _read_contract(profile)
    invalid = [artifact.path for artifact in artifacts if not _artifact_is_valid(profile, artifact)]
    if invalid:
        raise ModelCacheError(
            f"Model cache has missing or damaged required files: {', '.join(invalid)}. "
            f"Run `gurubodh models prepare --profile {profile.profile_id}` with network access to repair them."
        )

    progress(
        f"Verified {len(artifacts)} required files ({total_bytes} bytes) for "
        f"{profile.model} at {profile.revision}."
    )
    try:
        _run_embedding_smoke(profile)
    except Exception as exc:
        raise ModelCacheError(
            f"Required files passed integrity checks, but the pinned model could not complete the offline "
            f"embedding smoke check: {exc}. Run `gurubodh models prepare --profile {profile.profile_id}`; "
            "if the failure remains, check the installed CLI dependencies and configured device."
        ) from exc
    progress("Offline embedding smoke check succeeded.")
    progress(f"Model cache is ready for profile {profile.profile_id}.")


def _run_embedding_smoke(profile: ResolvedModelProfile) -> None:
    """Load and encode through the same helper used by semantic chunking."""
    helper = SentenceTransformerEmbeddingHelper(
        provider=profile.config.provider,
        model_name=profile.model,
        model_revision=profile.revision,
        cache_dir_resolver=profile.config.resolved_cache_dir,
        local_files_only=True,
        device=profile.config.device,
    )
    embeddings = helper.encode_texts(
        ["गुरुबोध"],
        batch_size=1,
        normalize=profile.config.normalize_contextual_vectors,
    )
    try:
        import numpy as np

        array = np.asarray(embeddings)
        valid = (
            array.ndim == 2
            and array.shape[0] == 1
            and array.shape[1] > 0
            and np.isfinite(array).all()
        )
    except Exception as exc:
        raise RuntimeError("embedding output could not be validated") from exc
    if not valid:
        raise RuntimeError("embedding runtime returned an invalid smoke-check vector")


def _write_contract(
    profile: ResolvedModelProfile,
    artifacts: tuple[RequiredArtifact, ...],
    total_bytes: int,
) -> None:
    payload = {
        "schema_version": MODEL_CACHE_CONTRACT_VERSION,
        "model": profile.model,
        "revision": profile.revision,
        "artifacts": [artifact.to_payload() for artifact in artifacts],
        "total_artifact_bytes": total_bytes,
    }
    destination = _contract_path(profile)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=destination.parent, prefix=f".{destination.name}.", delete=False
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
    except OSError as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise ModelCacheError(f"Could not write model-cache contract at {destination}.") from exc


def _read_contract(profile: ResolvedModelProfile) -> tuple[tuple[RequiredArtifact, ...], int]:
    path = _contract_path(profile)
    guidance = f"Run `gurubodh models prepare --profile {profile.profile_id}` with network access"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ModelCacheError(
            f"The model-cache integrity contract is missing or unreadable at {path}. {guidance}."
        ) from exc
    try:
        if set(payload) != {"schema_version", "model", "revision", "artifacts", "total_artifact_bytes"}:
            raise ValueError
        if payload["schema_version"] != MODEL_CACHE_CONTRACT_VERSION:
            raise ValueError
        if payload["model"] != profile.model or payload["revision"] != profile.revision:
            raise ValueError
        entries = payload["artifacts"]
        if not isinstance(entries, list) or [entry.get("path") for entry in entries] != list(
            REQUIRED_RUNTIME_FILES
        ):
            raise ValueError
        artifacts = []
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"path", "size", "hash"}:
                raise ValueError
            hash_value = entry["hash"]
            if not isinstance(hash_value, dict) or set(hash_value) != {"algorithm", "digest"}:
                raise ValueError
            artifact = RequiredArtifact(
                entry["path"], entry["size"], hash_value["algorithm"], hash_value["digest"]
            )
            if not _valid_artifact_metadata(artifact):
                raise ValueError
            artifacts.append(artifact)
        total_bytes = payload["total_artifact_bytes"]
        if not isinstance(total_bytes, int) or isinstance(total_bytes, bool) or total_bytes < 0:
            raise ValueError
        if total_bytes != sum(artifact.size for artifact in artifacts):
            raise ValueError
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ModelCacheError(
            f"The model-cache integrity contract is invalid at {path}. {guidance} to rebuild it."
        ) from None
    return tuple(artifacts), total_bytes


def _valid_artifact_metadata(artifact: RequiredArtifact) -> bool:
    if artifact.path not in REQUIRED_RUNTIME_FILES:
        return False
    if not isinstance(artifact.size, int) or isinstance(artifact.size, bool) or artifact.size < 0:
        return False
    lengths = {"git-sha1": 40, "sha256": 64}
    length = lengths.get(artifact.hash_algorithm)
    return length is not None and isinstance(artifact.digest, str) and re.fullmatch(
        rf"[0-9a-f]{{{length}}}", artifact.digest
    ) is not None


def _artifact_is_valid(profile: ResolvedModelProfile, artifact: RequiredArtifact) -> bool:
    return _path_matches_artifact(_snapshot_dir(profile) / artifact.path, artifact)


def _artifact_cache_state(profile: ResolvedModelProfile, artifact: RequiredArtifact) -> str:
    if _artifact_is_valid(profile, artifact):
        return "ready"
    if _path_matches_artifact(_blob_path(profile, artifact), artifact):
        return "relink"
    return "download"


def _path_matches_artifact(path: Path, artifact: RequiredArtifact) -> bool:
    try:
        if not path.is_file() or path.stat().st_size != artifact.size:
            return False
        digest = _file_digest(path, artifact.hash_algorithm, artifact.size)
    except OSError:
        return False
    return digest == artifact.digest


def _file_digest(path: Path, algorithm: str, size: int) -> str:
    if algorithm == "sha256":
        digest = hashlib.sha256()
    elif algorithm == "git-sha1":
        digest = hashlib.sha1()
        digest.update(f"blob {size}\0".encode("ascii"))
    else:
        raise ValueError("unsupported artifact hash algorithm")
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _snapshot_dir(profile: ResolvedModelProfile) -> Path:
    return _model_cache_dir(profile) / "snapshots" / profile.revision


def _model_cache_dir(profile: ResolvedModelProfile) -> Path:
    repo_dir = f"models--{'--'.join(profile.model.split('/'))}"
    return profile.cache_dir / repo_dir


def _blob_path(profile: ResolvedModelProfile, artifact: RequiredArtifact) -> Path:
    return _model_cache_dir(profile) / "blobs" / artifact.digest


def _contract_path(profile: ResolvedModelProfile) -> Path:
    return _snapshot_dir(profile) / MODEL_CACHE_CONTRACT_FILENAME


def _format_bytes(size: int) -> str:
    value = float(size)
    units = ("bytes", "KiB", "MiB", "GiB", "TiB")
    unit = units[0]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024
    return f"{int(value)} {unit}" if unit == "bytes" else f"{value:.2f} {unit}"
