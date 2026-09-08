"""Deterministic field-by-field composition, with no execution side effects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from gurubodh.configuration_provenance import ConfigurationProvenance
import os
from pathlib import Path, PurePosixPath
import re

from gurubodh.config import (
    prepare_generate_chunks_job,
    prepare_generate_docx_job,
    prepare_prep_subject_job,
    proofreading_config,
)
from gurubodh.contracts import (
    JobResolutionInputs, ProfileSelection, ResolvedJob, ResolvedProofreading,
)
from gurubodh.errors import ConfigurationError
from gurubodh.job_components import ComponentCatalog, validate_resource_id


_PREPARERS = {
    "prep-subject": prepare_prep_subject_job,
    "generate-chunks": prepare_generate_chunks_job,
    "generate-docx": prepare_generate_docx_job,
}
_CREDENTIAL_VARIABLES = frozenset({
    "GEMINI_API_KEY", "CLOUDFLARE_R2_ACCOUNT_ID",
    "CLOUDFLARE_R2_ACCESS_KEY_ID", "CLOUDFLARE_R2_SECRET_ACCESS_KEY",
})


def _posix_join(*parts: str) -> str:
    # Component schemas already enforce this grammar. Check the join boundary
    # explicitly so PurePosixPath cannot silently discard or normalize segments.
    for part in parts:
        if (not part or any(segment in {"", ".", ".."} for segment in part.split("/"))
                or re.search(r"[\\:\x00-\x1f\x7f${}]", part)):
            raise ConfigurationError("Composition: expected a safe relative POSIX path.")
    return str(PurePosixPath(*parts))


def _chapters(command: str, chapters: list[str] | None) -> tuple[str, ...] | None:
    if chapters is None:
        return None
    if command != "generate-chunks":
        raise ConfigurationError("Invocation: chapters is supported only by generate-chunks.")
    if (not isinstance(chapters, list) or not chapters
            or any(not isinstance(value, str) or re.fullmatch(r"[0-9]{3}", value) is None
                   for value in chapters)
            or len(set(chapters)) != len(chapters)):
        raise ConfigurationError("Invocation: chapters must be a nonempty unique list of exact three-ASCII-digit strings.")
    return tuple(chapters)


def _profile_selection(kind, command, manifest, edition, invocation):
    selected = command["default_profiles"][kind]
    selected_by = "command"
    for label, values in (("manifest", manifest.get("profile_overrides", {})),
                          ("edition", edition.get("profile_overrides", {})),
                          ("invocation", invocation)):
        if kind in values:
            selected = values[kind]
            selected_by = label
    return ProfileSelection(kind, selected, selected_by)


def _store_location(store_id, store, environment, environ, bindings):
    location = {"backend": store["backend"]}
    if store["backend"] == "r2":
        location["bucket"] = store["bucket"]
        location["url_base"] = store["url_base"]
        return location
    variable = store["root_dir"]["$env"]
    context = (f"Composition (environment, {environment.origin}): "
               f"$.stores.{store_id}.root_dir ({variable})")
    if variable in _CREDENTIAL_VARIABLES or variable == "GURUBODH_MODEL_CACHE_DIR":
        raise ConfigurationError(f"{context} must reference a non-secret library root variable.")
    # Read each used name once. Never enumerate the environment, expand other
    # variables, resolve credentials, or inspect/create a library directory.
    value = bindings.get(variable)
    if value is None:
        value = environ.get(variable)
        if (not isinstance(value, str) or not value or not Path(value).is_absolute()
                or re.search(r"[\x00-\x1f\x7f${}]", value)):
            raise ConfigurationError(f"{context} must be set to a nonempty absolute path without interpolation.")
        bindings[variable] = value
    location["root_dir"] = value
    return location


def resolve_job(
    catalog: ComponentCatalog,
    *,
    command: str,
    manifest_id: str,
    locale: str,
    environment_id: str,
    storage_profile_id: str,
    proofreading_profile_id: str | None = None,
    chunking_profile_id: str | None = None,
    chapters: list[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> ResolvedJob:
    """Assemble and prepare a canonical job; retain the exact resolution inputs.

    The catalog root and all five selectors are explicit. Invocation settings
    are limited to applicable complete profile IDs and the chunks chapter list.
    """
    validate_resource_id("command-definition", command)
    if command not in _PREPARERS:
        raise ConfigurationError("Composition: command does not define a canonical job.")
    for kind, identity in (("subject-manifest", manifest_id), ("locale-definition", locale),
                           ("environment", environment_id), ("storage-profile", storage_profile_id)):
        validate_resource_id(kind, identity)
    selected_chapters = _chapters(command, chapters)
    invocation = {}
    for kind, identity, applicable in (("proofreading", proofreading_profile_id, "prep-subject"),
                                       ("chunking", chunking_profile_id, "generate-chunks")):
        if identity is not None:
            if command != applicable:
                raise ConfigurationError(f"Invocation: {kind} profile is not applicable to {command}.")
            validate_resource_id(f"{kind}-profile", identity)
            invocation[kind] = identity

    snapshots = []

    def load(kind, identity):
        snapshot = catalog.load(kind, identity)
        snapshots.append(snapshot)
        return snapshot.to_payload()

    definition = load("command-definition", command)
    manifest = load("subject-manifest", manifest_id)
    if locale not in manifest["editions"]:
        raise ConfigurationError(
            f"Composition (subject-manifest, {snapshots[-1].origin}): $.editions.{locale} is required for this run."
        )
    edition = manifest["editions"][locale]
    locale_definition = load("locale-definition", locale)
    environment = load("environment", environment_id)
    environment_snapshot = snapshots[-1]
    route = load("storage-profile", storage_profile_id)
    route_snapshot = snapshots[-1]
    profiles = []
    policies = {}
    for kind in definition["default_profiles"]:
        selection = _profile_selection(kind, definition, manifest, edition, invocation)
        policies[kind] = load(f"{kind}-profile", selection.profile_id)[kind]
        profiles.append(selection)

    bindings = {}
    runtime_environ = os.environ if environ is None else environ
    subject_dir = _posix_join(manifest["artifact_root"], locale)
    source_document = edition["source_document"]
    job = {
        "schema_version": definition["job_schema_version"],
        "pipeline": (definition["pipeline_by_encoding"][source_document["font_encoding"]]
                     if command == "prep-subject" else definition["pipeline"]),
    }
    for side in ("source", "destination"):
        role = definition[f"{side}_role"]
        store_id = route[role]
        if store_id not in environment["stores"]:
            raise ConfigurationError(
                f"Composition (storage-profile, {route_snapshot.origin}): $.{role} "
                f"references a missing store in environment {environment_id}: $.stores.{store_id}."
            )
        store = environment["stores"][store_id]
        location = _store_location(store_id, store, environment_snapshot, runtime_environ, bindings)
        if command == "prep-subject" and side == "source":
            location["font_encoding"] = source_document["font_encoding"]
            location["file_format"] = source_document["file_format"]
            if store["backend"] == "local":
                location["relative_path"] = source_document["relative_path"]
            else:
                location["key"] = _posix_join(store["prefix"], source_document["relative_path"])
        else:
            location["subject_dir"] = subject_dir
            if store["backend"] == "r2":
                location["prefix"] = store["prefix"]
        job[side] = location

    names = {
        "category_code": manifest["identity"]["category_code"],
        "subject_code": manifest["identity"]["subject_code"],
        "title_slug": manifest["identity"]["title_slug"],
        "version": edition["release"]["version"],
        "subversion": edition["release"]["subversion"],
        "language": locale,
    }
    job["naming"] = {field: names[field] for field in definition["naming_fields"]}
    if command == "prep-subject":
        split = edition["chapter_split"]
        job["chapter_split"] = {"enabled": split["enabled"]}
        if split["enabled"]:
            job["chapter_split"]["pattern_type"] = split["pattern_type"]
            job["chapter_split"]["pattern"] = split["pattern"]
            if split["pattern_type"] == "regex":
                job["chapter_split"]["flags"] = list(split["flags"])
        metadata = locale_definition["metadata_defaults"]
        job["metadata_defaults"] = {
            "language": locale,
            "source_script": metadata["source_script"],
            "output_text_encoding": metadata["output_text_encoding"],
            "summary_chapter_markers": list(metadata["summary_chapter_markers"]),
        }
        job["proofreading"] = policies["proofreading"]
    elif command == "generate-chunks":
        job["chunking"] = policies["chunking"]
        if selected_chapters is not None:
            job["chapters"] = list(selected_chapters)
    origin = f"composed {command}: {manifest_id}/{locale}, {environment_id}/{storage_profile_id}"
    prepared = _PREPARERS[command](job, origin)
    inputs = JobResolutionInputs(
        command, manifest_id, locale, environment_id, storage_profile_id,
        tuple(invocation.items()), selected_chapters, tuple(profiles), tuple(snapshots),
        tuple(bindings.items()),
    )
    provenance = ConfigurationProvenance.capture(prepared, inputs=inputs)
    return ResolvedJob(replace(prepared, provenance=provenance), inputs)


def resolve_lab_proofreading(
    catalog: ComponentCatalog, *, proofreading_profile_id: str | None = None,
) -> ResolvedProofreading:
    """Resolve lab's JSON-owned default, without a manifest or canonical job."""
    command = catalog.load("command-definition", "lab-proofread")
    profile_id = command.to_payload()["default_profiles"]["proofreading"]
    selected_by = "command"
    if proofreading_profile_id is not None:
        profile_id = proofreading_profile_id
        selected_by = "invocation"
    profile = catalog.load("proofreading-profile", profile_id)
    return ResolvedProofreading(
        proofreading_config(profile.to_payload()),
        ProfileSelection("proofreading", profile_id, selected_by),
        (command, profile),
    )
