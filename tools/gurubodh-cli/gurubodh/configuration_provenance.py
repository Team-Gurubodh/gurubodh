"""Versioned configuration identity, deliberately independent of resume identity.

safe-json-v1 hashes UTF-8 JSON without BOM/newline/insignificant whitespace,
with Unicode preserved (no normalization), lexicographically sorted object
keys, ordered arrays and explicit nulls. Finite integral floats (including -0)
encode as integers; other floats use Python's shortest round-trip JSON form.
Non-finite numbers and non-JSON values are rejected. Redaction precedes hashing.
Component hashes cover entire sanitized documents, including unused declarations;
the assembled digest covers only the safe effective configuration snapshot.
Neither digest is a checkpoint compatibility fingerprint.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Literal

from gurubodh.audit_configuration import redact_mapping, safe_configuration_snapshot
from gurubodh.contracts import ComponentSnapshot, JobResolutionInputs, ProfileSelection


CANONICAL_JSON_VERSION = "safe-json-v1"
RESOLVER_CONTRACT_VERSION = "1.0.0"
PROVENANCE_SCHEMA_VERSION = "1.0.0"


def canonical_json(value: Any) -> bytes:
    def normalize(item):
        if item is None or isinstance(item, (str, bool, int)):
            return item
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("Canonical JSON requires finite numbers.")
            return int(item) if item.is_integer() else item
        if isinstance(item, dict) and all(isinstance(key, str) for key in item):
            return {key: normalize(val) for key, val in item.items()}
        if isinstance(item, list):
            return [normalize(val) for val in item]
        raise ValueError("Canonical JSON requires JSON values and string keys.")

    return json.dumps(normalize(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def configuration_digest(snapshot: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(safe_configuration_snapshot(snapshot))).hexdigest()


@dataclass(frozen=True)
class ComponentProvenance:
    kind: str
    resource_id: str
    resource_reference: str
    component_schema_version: str
    content_sha256: str

    @classmethod
    def capture(cls, component: ComponentSnapshot) -> ComponentProvenance:
        document = component.to_payload()
        return cls(component.kind, component.resource_id, component.origin,
                   document["component_schema_version"],
                   hashlib.sha256(canonical_json(redact_mapping(document))).hexdigest())

    def to_payload(self) -> dict[str, str]:
        return {"kind": self.kind, "resource_id": self.resource_id,
                "resource_reference": self.resource_reference,
                "component_schema_version": self.component_schema_version,
                "content_sha256": self.content_sha256}


@dataclass(frozen=True)
class ConfigurationProvenance:
    input_mode: Literal["in_memory", "composition"]
    assembled_configuration_sha256: str
    job_schema_version: str | int | None
    manifest_id: str | None = None
    edition: str | None = None
    command_definition_id: str | None = None
    environment_id: str | None = None
    storage_profile_id: str | None = None
    profiles: tuple[ProfileSelection, ...] = ()
    components: tuple[ComponentProvenance, ...] = ()
    invocation_profiles: tuple[tuple[str, str], ...] = ()
    chapters: tuple[str, ...] | None = None
    environment_bindings: tuple[str, ...] = ()

    @classmethod
    def capture(
        cls, configuration, *, input_mode="composition",
        inputs: JobResolutionInputs | None = None,
        components: tuple[ComponentSnapshot, ...] = (),
        profiles: tuple[ProfileSelection, ...] = (),
        command_definition_id: str | None = None,
        edition: str | None = None,
    ) -> ConfigurationProvenance:
        snapshot = safe_configuration_snapshot(configuration)
        bindings = {name for name, _ in inputs.root_bindings} if inputs else set()
        semantic_config = getattr(configuration, "semantic_chunk_config", None)
        if semantic_config is not None:
            bindings.add("GURUBODH_MODEL_CACHE_DIR")
        return cls(
            input_mode=input_mode,
            assembled_configuration_sha256=configuration_digest(snapshot),
            job_schema_version=snapshot.get("schema_version"),
            manifest_id=inputs.manifest_id if inputs else None,
            edition=inputs.locale if inputs else edition,
            command_definition_id=inputs.command if inputs else command_definition_id,
            environment_id=inputs.environment_id if inputs else None,
            storage_profile_id=inputs.storage_profile_id if inputs else None,
            profiles=inputs.profiles if inputs else profiles,
            components=tuple(ComponentProvenance.capture(component) for component in
                             (inputs.components if inputs else components)),
            invocation_profiles=inputs.invocation_profiles if inputs else tuple(
                (profile.kind, profile.profile_id) for profile in profiles if profile.selected_by == "invocation"
            ),
            chapters=inputs.chapters if inputs else None,
            environment_bindings=tuple(sorted(bindings)),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": PROVENANCE_SCHEMA_VERSION,
            "input_mode": self.input_mode,
            "canonical_json": CANONICAL_JSON_VERSION,
            "resolver_contract_version": RESOLVER_CONTRACT_VERSION if self.input_mode == "composition" else None,
            "assembled_configuration_sha256": self.assembled_configuration_sha256,
            "job_schema_version": self.job_schema_version,
            "manifest_id": self.manifest_id,
            "edition": self.edition,
            "command_definition_id": self.command_definition_id,
            "environment_id": self.environment_id,
            "storage_profile_id": self.storage_profile_id,
            "profiles": [{"kind": profile.kind, "profile_id": profile.profile_id,
                          "selected_by": profile.selected_by} for profile in self.profiles],
            "components": [component.to_payload() for component in self.components],
            "invocation": {"profiles": dict(self.invocation_profiles),
                           "chapters": list(self.chapters) if self.chapters is not None else None},
            "environment_bindings": list(self.environment_bindings),
        }


def provenance_markdown(report: dict[str, Any]) -> list[str]:
    """Shared rendering also accepts historical 2.0 envelopes without provenance."""
    provenance = report.get("configuration_provenance")
    if provenance is None:
        return []
    # JSON escaping keeps arbitrary path characters out of Markdown structure.
    lines = ["", "## Configuration provenance", "", "```json",
             json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True), "```"]
    return lines
