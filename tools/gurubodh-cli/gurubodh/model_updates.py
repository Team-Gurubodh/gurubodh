"""Advisory metadata-only checks for newer pinned-model repository revisions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import tempfile
from typing import Callable
from urllib.parse import quote

from gurubodh.errors import ConfigurationError, ProcessingError
from gurubodh.job_components import ComponentCatalog
from gurubodh.model_cache import (
    ModelCacheError,
    REQUIRED_RUNTIME_FILES,
    ResolvedModelProfile,
    required_artifacts_from_info,
    resolve_model_profile,
)


UPSTREAM_REVISION = "main"
WEIGHT_FILES = frozenset({"pytorch_model.bin"})
TOKENIZER_FILES = frozenset(
    {
        "sentencepiece.bpe.model",
        "special_tokens_map.json",
        "tokenizer.json",
        "tokenizer_config.json",
    }
)
CONFIGURATION_FILES = frozenset(REQUIRED_RUNTIME_FILES) - WEIGHT_FILES - TOKENIZER_FILES
REPORT_CONFIG_FILES = (
    "1_Pooling/config.json",
    "config.json",
    "sentence_bert_config.json",
)


class ModelUpdateCheckError(ProcessingError):
    """An advisory upstream model check could not produce a reliable result."""


@dataclass(frozen=True)
class FileChanges:
    """Repository paths changed between the pinned and upstream revisions."""

    weights: tuple[str, ...] = ()
    tokenizer: tuple[str, ...] = ()
    configuration: tuple[str, ...] = ()
    documentation_metadata: tuple[str, ...] = ()
    other_non_runtime: tuple[str, ...] = ()
    unclassified: tuple[str, ...] = ()

    @property
    def runtime_categories(self) -> tuple[str, ...]:
        categories = []
        for label, paths in (
            ("weights", self.weights),
            ("tokenizer", self.tokenizer),
            ("configuration", self.configuration),
        ):
            if paths:
                categories.append(label)
        return tuple(categories)


def check_model_updates(
    catalog: ComponentCatalog,
    profile_id: str,
    *,
    progress: Callable[[str], None] = print,
    checked_at: datetime | None = None,
) -> None:
    """Report whether upstream main descends from the selected immutable pin."""
    checked_at = checked_at or datetime.now(timezone.utc)
    try:
        profile = resolve_model_profile(catalog, profile_id, require_cache=False)
    except ConfigurationError as exc:
        raise ModelUpdateCheckError(
            _unable_message(profile_id, None, checked_at, f"the selected profile is invalid: {exc}")
        ) from exc

    try:
        from huggingface_hub import HfApi

        api = HfApi()
        upstream_info = api.model_info(
            profile.model,
            revision=UPSTREAM_REVISION,
            files_metadata=True,
        )
    except Exception as exc:
        raise ModelUpdateCheckError(
            _unable_message(
                profile.profile_id,
                profile,
                checked_at,
                "upstream main metadata is unavailable; check network access, authentication, and the Hub API",
            )
        ) from exc

    upstream_sha = getattr(upstream_info, "sha", None)
    if not _is_commit_id(upstream_sha):
        raise ModelUpdateCheckError(
            _unable_message(
                profile.profile_id,
                profile,
                checked_at,
                "upstream main did not resolve to a full immutable commit ID",
            )
        )

    if upstream_sha == profile.revision:
        pinned_info = upstream_info
    else:
        try:
            pinned_info = api.model_info(
                profile.model,
                revision=profile.revision,
                files_metadata=True,
            )
        except Exception as exc:
            raise ModelUpdateCheckError(
                _unable_message(
                    profile.profile_id,
                    profile,
                    checked_at,
                    "the pinned revision is unavailable from the model repository",
                    upstream_sha=upstream_sha,
                )
            ) from exc
        if getattr(pinned_info, "sha", None) != profile.revision:
            raise ModelUpdateCheckError(
                _unable_message(
                    profile.profile_id,
                    profile,
                    checked_at,
                    "the pinned revision did not resolve to the requested commit ID",
                    upstream_sha=upstream_sha,
                )
            )

    try:
        commits = api.list_repo_commits(
            profile.model,
            revision=upstream_sha,
            formatted=False,
        )
    except Exception as exc:
        raise ModelUpdateCheckError(
            _unable_message(
                profile.profile_id,
                profile,
                checked_at,
                "revision history is unavailable; a differing commit ID alone is not an update result",
                upstream_sha=upstream_sha,
            )
        ) from exc

    commit_ids = [getattr(commit, "commit_id", None) for commit in commits]
    if not commit_ids or commit_ids[0] != upstream_sha:
        raise ModelUpdateCheckError(
            _unable_message(
                profile.profile_id,
                profile,
                checked_at,
                "revision history does not start at the upstream commit, so ordering is indeterminate",
                upstream_sha=upstream_sha,
            )
        )
    try:
        pinned_index = commit_ids.index(profile.revision)
    except ValueError:
        raise ModelUpdateCheckError(
            _unable_message(
                profile.profile_id,
                profile,
                checked_at,
                "the pin is not an ancestor of upstream main; history is missing, divergent, or indeterminate",
                upstream_sha=upstream_sha,
            )
        ) from None

    current = pinned_index == 0
    changes = FileChanges() if current else _compare_repository_files(pinned_info, upstream_info)
    details = _read_upstream_details(profile, upstream_info, upstream_sha, checked_at)
    required_size = _required_artifact_size(upstream_info, upstream_sha)
    lines = _render_report(
        profile=profile,
        checked_at=checked_at,
        upstream_sha=upstream_sha,
        commits=commits,
        pinned_index=pinned_index,
        current=current,
        changes=changes,
        details=details,
        required_size=required_size,
    )
    for line in lines:
        progress(line)


def _compare_repository_files(pinned_info, upstream_info) -> FileChanges:
    pinned = _file_map(pinned_info)
    upstream = _file_map(upstream_info)
    if pinned is None or upstream is None:
        return FileChanges(unclassified=("repository file inventory unavailable",))

    changed = []
    unclassified = []
    for path in sorted(set(pinned) | set(upstream)):
        if path not in pinned or path not in upstream:
            changed.append(path)
            continue
        before = _file_identity(pinned[path])
        after = _file_identity(upstream[path])
        if before is not None and after is not None:
            if before != after:
                changed.append(path)
            continue
        before_size = getattr(pinned[path], "size", None)
        after_size = getattr(upstream[path], "size", None)
        if _valid_size(before_size) and _valid_size(after_size) and before_size != after_size:
            changed.append(path)
        else:
            unclassified.append(path)

    categories: dict[str, list[str]] = {
        "weights": [],
        "tokenizer": [],
        "configuration": [],
        "documentation_metadata": [],
        "other_non_runtime": [],
    }
    for path in changed:
        if path in WEIGHT_FILES:
            categories["weights"].append(path)
        elif path in TOKENIZER_FILES:
            categories["tokenizer"].append(path)
        elif path in CONFIGURATION_FILES:
            categories["configuration"].append(path)
        elif _is_documentation_or_metadata(path):
            categories["documentation_metadata"].append(path)
        else:
            categories["other_non_runtime"].append(path)
    return FileChanges(
        **{name: tuple(paths) for name, paths in categories.items()},
        unclassified=tuple(unclassified),
    )


def _file_map(info) -> dict[str, object] | None:
    siblings = getattr(info, "siblings", None)
    if siblings is None:
        return None
    result = {}
    try:
        for sibling in siblings:
            path = getattr(sibling, "rfilename", None)
            if isinstance(path, str) and path:
                result[path] = sibling
    except TypeError:
        return None
    return result


def _file_identity(sibling) -> tuple[str, str] | None:
    lfs = getattr(sibling, "lfs", None)
    lfs_sha256 = getattr(lfs, "sha256", None) if lfs is not None else None
    if isinstance(lfs_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", lfs_sha256):
        return "sha256", lfs_sha256
    blob_id = getattr(sibling, "blob_id", None)
    if isinstance(blob_id, str) and re.fullmatch(r"[0-9a-f]{40}", blob_id):
        return "git-sha1", blob_id
    return None


def _is_documentation_or_metadata(path: str) -> bool:
    lowered = path.lower()
    name = Path(lowered).name
    return (
        name in {".gitattributes", "license", "license.txt", "notice", "notice.txt"}
        or lowered.endswith((".md", ".rst"))
        or lowered.startswith("docs/")
    )


def _read_upstream_details(
    profile: ResolvedModelProfile,
    upstream_info,
    upstream_sha: str,
    checked_at: datetime,
) -> dict[str, object | None]:
    available_paths = set(_file_map(upstream_info) or {})
    documents: dict[str, Mapping[str, object] | None] = {}
    with tempfile.TemporaryDirectory(prefix="gurubodh-model-update-") as directory:
        for filename in REPORT_CONFIG_FILES:
            if filename not in available_paths:
                documents[filename] = None
                continue
            try:
                from huggingface_hub import hf_hub_download

                downloaded = hf_hub_download(
                    repo_id=profile.model,
                    filename=filename,
                    revision=upstream_sha,
                    cache_dir=directory,
                    local_files_only=False,
                )
            except Exception as exc:
                raise ModelUpdateCheckError(
                    _unable_message(
                        profile.profile_id,
                        profile,
                        checked_at,
                        f"required descriptive/configuration file {filename} could not be read from upstream",
                        upstream_sha=upstream_sha,
                    )
                ) from exc
            try:
                value = json.loads(Path(downloaded).read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                value = None
            documents[filename] = value if isinstance(value, Mapping) else None

    base_config = documents.get("config.json") or {}
    pooling_config = documents.get("1_Pooling/config.json") or {}
    sentence_config = documents.get("sentence_bert_config.json") or {}

    architectures = base_config.get("architectures")
    architecture = None
    if isinstance(architectures, list) and architectures and all(
        isinstance(value, str) and value for value in architectures
    ):
        architecture = ", ".join(architectures)

    dimension = pooling_config.get("word_embedding_dimension")
    dimension_source = "1_Pooling/config.json word_embedding_dimension"
    if not _positive_int(dimension):
        dimension = base_config.get("hidden_size")
        dimension_source = "config.json hidden_size"
    if not _positive_int(dimension):
        dimension = None
        dimension_source = None

    context_limit = sentence_config.get("max_seq_length")
    if not _positive_int(context_limit):
        context_limit = None

    return {
        "architecture": architecture,
        "embedding_dimension": dimension,
        "embedding_dimension_source": dimension_source,
        "context_limit": context_limit,
        "license": _license_from_info(upstream_info),
    }


def _license_from_info(info) -> str | None:
    card_data = getattr(info, "card_data", None)
    if isinstance(card_data, Mapping):
        value = card_data.get("license")
    else:
        value = getattr(card_data, "license", None)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _required_artifact_size(info, upstream_sha: str) -> tuple[int | None, str | None]:
    try:
        artifacts = required_artifacts_from_info(
            info,
            expected_revision=upstream_sha,
            revision_label="Upstream revision",
        )
    except ModelCacheError as exc:
        reason = str(exc).split(";", 1)[0].split(". No artifact content", 1)[0]
        return None, reason
    return sum(artifact.size for artifact in artifacts), None


def _render_report(
    *,
    profile: ResolvedModelProfile,
    checked_at: datetime,
    upstream_sha: str,
    commits,
    pinned_index: int,
    current: bool,
    changes: FileChanges,
    details: Mapping[str, object | None],
    required_size: tuple[int | None, str | None],
) -> list[str]:
    pinned_commit = commits[pinned_index]
    upstream_commit = commits[0]
    model_url = f"https://huggingface.co/{quote(profile.model, safe='/')}"
    lines = [
        f"Profile: {profile.profile_id}",
        f"Model: {profile.model}",
        f"Pinned revision: {profile.revision}",
        f"Pinned commit date: {_format_datetime(getattr(pinned_commit, 'created_at', None))}",
        f"Upstream revision (main): {upstream_sha}",
        f"Upstream commit date: {_format_datetime(getattr(upstream_commit, 'created_at', None))}",
        f"Checked at: {_format_datetime(checked_at)}",
    ]
    if current:
        lines.append("Revision relationship: the pin is the current upstream main commit.")
    else:
        lines.append(
            f"Revision relationship: the pin is an ancestor of upstream main "
            f"({pinned_index} newer commit(s))."
        )

    lines.extend(
        [
            f"Architecture: {details['architecture'] or 'Unavailable from upstream configuration'}",
            _render_dimension(details),
            f"Context/token limit: {details['context_limit'] or 'Unavailable from upstream configuration'}",
            f"License: {details['license'] or 'Unavailable from upstream model-card metadata'}",
            _render_required_size(required_size),
        ]
    )

    if not current:
        lines.extend(
            [
                f"Runtime weights changed: {_render_paths(changes.weights)}",
                f"Tokenizer changed: {_render_paths(changes.tokenizer)}",
                f"Runtime configuration changed: {_render_paths(changes.configuration)}",
                f"Documentation/metadata changed: {_render_paths(changes.documentation_metadata)}",
                f"Other non-runtime artifacts changed: {_render_paths(changes.other_non_runtime)}",
                f"Unclassified paths (incomplete metadata): {_render_paths(changes.unclassified)}",
            ]
        )

    lines.append(f"Model card: {model_url}")
    lines.append(f"Pinned commit: {model_url}/commit/{profile.revision}")
    lines.append(f"Upstream commit: {model_url}/commit/{upstream_sha}")
    if not current:
        lines.append("Relevant newer commits:")
        for commit in commits[: min(pinned_index, 5)]:
            commit_id = getattr(commit, "commit_id", "")
            title = " ".join(str(getattr(commit, "title", "") or "Untitled commit").split())
            if len(title) > 100:
                title = f"{title[:97]}..."
            lines.append(
                f"- {_format_datetime(getattr(commit, 'created_at', None))} {title}: "
                f"{model_url}/commit/{commit_id}"
            )
        if pinned_index > 5:
            lines.append(f"- {pinned_index - 5} additional newer commit(s) omitted from this concise report.")
    summary = (
        "no newer upstream main revision was found."
        if current else _change_summary(changes)
    )
    lines.extend(
        [
            "",
            "Conclusion:",
            f"  Status: {'current' if current else 'update available'}",
            f"  Change summary: {summary}",
            "  Advisory: newer does not imply better quality, retraining, or validated "
            "compatibility; the pin and cache are unchanged.",
        ]
    )
    return lines


def _change_summary(changes: FileChanges) -> str:
    if changes.unclassified:
        return (
            "a newer repository revision exists, but incomplete file metadata prevents a complete "
            "runtime-change classification; review the commits before considering any pin change."
        )
    if changes.runtime_categories:
        return (
            f"required runtime {', '.join(changes.runtime_categories)} changed; this is not a compatibility "
            "or quality assessment and no automatic upgrade is performed."
        )
    if changes.other_non_runtime:
        return (
            "only non-runtime artifacts changed; the maintained required runtime files did not change, "
            "so this is not reported as a new model release."
        )
    if changes.documentation_metadata:
        return (
            "documentation/metadata-only repository changes; this is not a new model release."
        )
    return (
        "repository history changed without exposed file-content differences; this is not a new model release."
    )


def _render_dimension(details: Mapping[str, object | None]) -> str:
    dimension = details["embedding_dimension"]
    if dimension is None:
        return "Embedding dimensions: Unavailable from upstream configuration"
    return f"Embedding dimensions: {dimension} ({details['embedding_dimension_source']})"


def _render_required_size(value: tuple[int | None, str | None]) -> str:
    size, reason = value
    if size is None:
        return f"Required runtime artifact size: Unavailable ({reason})"
    return f"Required runtime artifact size: {size} bytes ({_format_bytes(size)})"


def _render_paths(paths: tuple[str, ...]) -> str:
    if not paths:
        return "none"
    visible = paths[:8]
    value = ", ".join(visible)
    if len(paths) > len(visible):
        value += f", and {len(paths) - len(visible)} more"
    return value


def _unable_message(
    profile_id: str,
    profile: ResolvedModelProfile | None,
    checked_at: datetime,
    reason: str,
    *,
    upstream_sha: str | None = None,
) -> str:
    lines = [
        "Model update check result: unable to determine.",
        "Status: unable to check",
        f"Profile: {profile_id}",
    ]
    if profile is not None:
        lines.extend(
            [
                f"Model: {profile.model}",
                f"Pinned revision: {profile.revision}",
            ]
        )
    if upstream_sha is not None:
        lines.append(f"Upstream revision (main): {upstream_sha}")
    lines.extend(
        [
            f"Checked at: {_format_datetime(checked_at)}",
            f"Reason: {reason}.",
            "The command did not report the pin as current and did not change the profile or model cache.",
        ]
    )
    return "\n".join(lines)


def _is_commit_id(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def _valid_size(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _positive_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _format_datetime(value) -> str:
    if not isinstance(value, datetime):
        return "Unavailable from upstream revision history"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _format_bytes(size: int) -> str:
    value = float(size)
    units = ("bytes", "KiB", "MiB", "GiB", "TiB")
    unit = units[0]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024
    return f"{int(value)} {unit}" if unit == "bytes" else f"{value:.2f} {unit}"
