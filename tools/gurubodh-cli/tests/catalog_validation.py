"""Read-only validation of a complete catalog, independent of job selection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from gurubodh.errors import ConfigurationError
from gurubodh.job_components import ComponentCatalog, _DIRECTORIES, _unique_object
from gurubodh.legacy import font_detection
from gurubodh.schema_validation import POLICY_SCHEMAS, validate_policy


@dataclass(frozen=True)
class CatalogValidationResult:
    components: tuple[tuple[str, str], ...]
    policies: tuple[str, ...]


def _catalog_files(root: Path, directory: Path) -> tuple[Path, ...]:
    """Traverse deterministically, checking containment before following paths."""
    files = []

    def visit(path: Path, ancestors: frozenset[Path]) -> None:
        origin = path.relative_to(root).as_posix()
        try:
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(root) or resolved in ancestors:
                raise ConfigurationError(f"Catalog validation ({origin}): unsafe catalog path.")
            if resolved.is_dir():
                if path.suffix == ".json":
                    raise ConfigurationError(f"Catalog validation ({origin}): resource must be a regular JSON file.")
                for child in sorted(path.iterdir()):
                    visit(child, ancestors | {resolved})
            elif resolved.is_file():
                if path.suffix == ".json" and not path.name.endswith(".schema.json"):
                    files.append(path)
            else:
                raise ConfigurationError(f"Catalog validation ({origin}): unsupported catalog path.")
        except (OSError, RuntimeError, ValueError):
            raise ConfigurationError(
                f"Catalog validation ({origin}): missing, unreadable, or unsafe catalog path."
            ) from None

    if not directory.is_dir():
        origin = directory.relative_to(root).as_posix()
        raise ConfigurationError(f"Catalog validation ({origin}): required catalog root is missing.")
    visit(directory, frozenset())
    return tuple(files)


def _discover_components(root: Path) -> tuple[tuple[str, str], ...]:
    components = []
    subjects = root / "jobs" / "subjects"
    for path in _catalog_files(root, subjects):
        relative = path.relative_to(subjects)
        if len(relative.parts) != 2 or relative.name != "manifest.json":
            raise ConfigurationError(
                f"Catalog validation ({path.relative_to(root).as_posix()}): "
                "subject manifests must use jobs/subjects/<id>/manifest.json."
            )
        components.append(("subject-manifest", relative.parts[0]))

    reusable = root / "config" / "job-components"
    kinds = {directory: kind for kind, directory in _DIRECTORIES.items()}
    for path in _catalog_files(root, reusable):
        relative = path.relative_to(reusable)
        kind = kinds.get(relative.parent.as_posix())
        if kind is None:
            raise ConfigurationError(
                f"Catalog validation ({path.relative_to(root).as_posix()}): "
                "unsupported component placement or kind."
            )
        components.append((kind, path.stem))
    return tuple(sorted(components))


def _validate_policies(root: Path) -> tuple[str, ...]:
    directory = root / "config" / "policies"
    policies = {}
    for path in _catalog_files(root, directory):
        origin = path.relative_to(root).as_posix()
        if path.parent != directory or path.stem not in POLICY_SCHEMAS:
            raise ConfigurationError(f"Catalog validation ({origin}): unsupported policy placement or kind.")
        policies[path.stem] = path

    required = Path(font_detection._SOURCE_FONT_POLICY).stem
    if required not in policies:
        raise ConfigurationError(
            f"Catalog validation ({font_detection._SOURCE_FONT_POLICY}): required policy is missing."
        )
    for kind, path in sorted(policies.items()):
        if kind == required:
            # Redirect only the policy lookup; the real schema and semantic
            # checks run, and patch restores the loader even on failure.
            with patch.object(font_detection, "bundled_resource_path", return_value=path):
                font_detection.load_approved_unicode_font_families()
        else:
            origin = path.relative_to(root).as_posix()
            try:
                document = json.loads(path.read_bytes().decode("utf-8"), object_pairs_hook=_unique_object)
            except (OSError, ValueError, RecursionError):
                raise ConfigurationError(f"Catalog validation ({origin}): invalid policy JSON.") from None
            validate_policy(document, kind, origin)
    return tuple(sorted(policies))


def _origin(kind: str, resource_id: str) -> str:
    if kind == "subject-manifest":
        return f"jobs/subjects/{resource_id}/manifest.json"
    return f"config/job-components/{_DIRECTORIES[kind]}/{resource_id}.json"


def _validate_declared_references(
    documents: Mapping[tuple[str, str], Mapping[str, Any]],
) -> None:
    stores = {
        store
        for (kind, _), document in documents.items()
        if kind == "environment"
        for store in document["stores"]
    }

    def require(kind: str, resource_id: str, origin: str, field: str) -> None:
        if (kind, resource_id) not in documents:
            raise ConfigurationError(
                f"Catalog validation ({origin}): {field} references a missing {kind}."
            )

    def profiles(declarations: Mapping[str, str], origin: str, field: str) -> None:
        for name, resource_id in sorted(declarations.items()):
            require(f"{name}-profile", resource_id, origin, f"{field}.{name}")

    for (kind, resource_id), document in sorted(documents.items()):
        origin = _origin(kind, resource_id)
        if kind == "command-definition":
            profiles(document["default_profiles"], origin, "$.default_profiles")
        elif kind == "subject-manifest":
            profiles(document.get("profile_overrides", {}), origin, "$.profile_overrides")
            for locale, edition in sorted(document["editions"].items()):
                field = f"$.editions.{locale}"
                require("locale-definition", locale, origin, field)
                profiles(edition.get("profile_overrides", {}), origin, f"{field}.profile_overrides")
        elif kind == "storage-profile":
            for role in ("source_document", "subject_artifact_source", "subject_artifact_destination"):
                if document[role] not in stores:
                    raise ConfigurationError(
                        f"Catalog validation ({origin}): $.{role} references a store "
                        "not declared by any environment."
                    )


def validate_catalog(root: Path) -> CatalogValidationResult:
    root = Path(root).resolve()
    components = _discover_components(root)
    catalog = ComponentCatalog(root, resource_root=root)
    documents = {}
    for kind, resource_id in components:
        snapshot = catalog.load(kind, resource_id)
        documents[kind, resource_id] = snapshot.to_payload()
    policies = _validate_policies(root)
    _validate_declared_references(documents)
    return CatalogValidationResult(components, policies)
