"""Contained, read-only loading of the declared JSON component catalog."""

from __future__ import annotations

import json
from pathlib import Path
import re

from gurubodh.contracts import ComponentSnapshot
from gurubodh.errors import ConfigurationError
from gurubodh.schema_validation import validate_component


_DIRECTORIES = {
    "command-definition": "commands",
    "environment": "environments",
    "storage-profile": "storage-profiles",
    "locale-definition": "locales",
    "proofreading-profile": "profiles/proofreading",
    "chunking-profile": "profiles/chunking",
}
_ID = r"[a-z0-9]+(?:[_-][a-z0-9]+)*"
_PROFILE_ID = r"[a-z0-9]+(?:[.-][a-z0-9]+)*-v[1-9][0-9]*"


def validate_resource_id(kind: str, resource_id: str) -> None:
    """Reject references before constructing or accessing a filesystem path."""
    if kind == "command-definition":
        valid = isinstance(resource_id, str) and resource_id in {
            "prep-subject", "generate-chunks", "generate-docx", "lab-proofread",
        }
    elif kind == "locale-definition":
        valid = isinstance(resource_id, str) and resource_id in {"hi-IN", "mr-IN"}
    elif kind in {"subject-manifest", *_DIRECTORIES}:
        pattern = _PROFILE_ID if kind in {"proofreading-profile", "chunking-profile"} else _ID
        valid = isinstance(resource_id, str) and re.fullmatch(pattern, resource_id) is not None
    else:
        raise ConfigurationError("Component lookup: unsupported component kind.")
    if not valid:
        raise ConfigurationError(f"Component lookup ({kind}): invalid resource ID.")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate property")
        result[key] = value
    return result


class ComponentCatalog:
    """One explicit CLI root; discovery across installations belongs to #287."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def load(self, kind: str, resource_id: str) -> ComponentSnapshot:
        validate_resource_id(kind, resource_id)
        if kind == "subject-manifest":
            directory = self.root / "jobs" / "subjects" / resource_id
            path = directory / "manifest.json"
        else:
            directory = self.root / "config" / "job-components" / _DIRECTORIES[kind]
            path = directory / f"{resource_id}.json"
        origin = path.relative_to(self.root).as_posix()
        context = f"Component lookup ({kind}, {origin})"
        try:
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(directory):
                raise ConfigurationError(f"{context}: resource must remain within its fixed directory.")
            if not resolved.is_file():
                raise ConfigurationError(f"{context}: resource must be a regular JSON file.")
            content = resolved.read_bytes()
        except (OSError, RuntimeError, ValueError):
            raise ConfigurationError(f"{context}: resource is missing, unreadable, or has an unsafe path.") from None
        try:
            document = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise ConfigurationError(f"{context}: resource must contain valid UTF-8 JSON with unique properties.") from None
        validate_component(document, kind, origin, expected_id=resource_id)
        return ComponentSnapshot(kind, resource_id, origin, content)
