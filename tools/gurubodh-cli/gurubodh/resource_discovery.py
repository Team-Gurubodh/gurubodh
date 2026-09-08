"""Deterministic discovery of immutable resources shipped with the CLI."""

from __future__ import annotations

from functools import lru_cache
from importlib.metadata import PackageNotFoundError, distribution, distributions
from pathlib import Path, PurePosixPath

from gurubodh.errors import ConfigurationError


_DISTRIBUTION = "gurubodh_cli"
_SOURCE_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_CHECKOUT = (_SOURCE_ROOT / "pyproject.toml").is_file()
_CATALOG_ANCHOR = PurePosixPath(
    "config/job-components/commands/prep-subject.json"
)


class BundledResourceError(ConfigurationError):
    """A required distribution-owned resource is absent or ambiguous."""


def _safe_relative(relative: str | PurePosixPath) -> PurePosixPath:
    raw = str(relative)
    path = PurePosixPath(raw)
    if (
        path.is_absolute()
        or not path.parts
        or "\\" in raw
        or any(ord(character) < 32 or ord(character) == 127 for character in raw)
        or any(part in {"", ".", ".."} for part in raw.split("/"))
    ):
        raise BundledResourceError("Bundled resource lookup requires a safe relative path.")
    return path


def _distribution_for_import():
    """Select metadata belonging to this imported package when duplicates exist."""
    module_path = Path(__file__).resolve()
    module_relative = PurePosixPath("gurubodh/resource_discovery.py")
    for candidate in distributions(name=_DISTRIBUTION):
        for entry in candidate.files or ():
            if (
                entry.parts[-len(module_relative.parts) :] == module_relative.parts
                and Path(candidate.locate_file(entry)).resolve() == module_path
            ):
                return candidate
    try:
        return distribution(_DISTRIBUTION)
    except PackageNotFoundError:
        return None


def _installed_resource_path(relative: PurePosixPath) -> Path | None:
    package_distribution = _distribution_for_import()
    if package_distribution is None:
        return None
    matches = []
    for entry in package_distribution.files or ():
        if entry.parts[-len(relative.parts) :] == relative.parts:
            matches.append(Path(package_distribution.locate_file(entry)))
    if len(matches) > 1:
        raise BundledResourceError(
            f"Bundled resource is ambiguous in the installed distribution: {relative}."
        )
    return matches[0] if matches else None


@lru_cache(maxsize=None)
def bundled_resource_path(relative: str | PurePosixPath) -> Path:
    """Resolve one resource from the checkout or the installed RECORD.

    The source candidate is anchored to this module, never to the process's
    current directory. A non-editable installation therefore falls through to
    the exact path recorded by its distribution metadata.
    """
    safe_relative = _safe_relative(relative)
    source = _SOURCE_ROOT.joinpath(*safe_relative.parts)
    installed = None if _SOURCE_CHECKOUT else _installed_resource_path(safe_relative)
    candidates = (source,) if _SOURCE_CHECKOUT else (installed, source)
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate.resolve()
    locations = ", ".join(
        str(candidate) for candidate in (source, installed) if candidate is not None
    )
    raise BundledResourceError(
        f"Required bundled resource {safe_relative} was not found (checked: {locations})."
    )


@lru_cache(maxsize=1)
def bundled_catalog_root() -> Path:
    """Return the one root owning all reusable packaged job components."""
    anchor = bundled_resource_path(_CATALOG_ANCHOR)
    return anchor.parents[3]
