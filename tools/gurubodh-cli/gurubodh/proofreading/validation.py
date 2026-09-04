"""Provider-neutral parsing and validation for structured proofreading output."""

from __future__ import annotations

from dataclasses import dataclass
import json

from gurubodh.proofreading.errors import ProofreadingError


EDIT_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "corrected_text": {
            "type": "string",
            "description": "Corrected source text only.",
        },
        "edits": {
            "type": "array",
            "description": "Every spelling, grammar, or punctuation correction.",
            "items": {
                "type": "object",
                "properties": {
                    "original": {"type": "string"},
                    "corrected": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": ["spelling", "grammar", "punctuation"],
                    },
                    "reason": {"type": "string"},
                },
                "required": ["original", "corrected", "category", "reason"],
            },
        },
    },
    "required": ["corrected_text", "edits"],
}


@dataclass(frozen=True)
class ProofreadingEdit:
    original: str
    corrected: str
    category: str
    reason: str

    def to_payload(self) -> dict[str, str]:
        return {
            "original": self.original,
            "corrected": self.corrected,
            "category": self.category,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ValidatedProofreadingResponse:
    corrected_text: str
    edits: tuple[ProofreadingEdit, ...]


def parse_structured_response(
    response_text: str,
    original_text: str,
    *,
    provider_name: str,
) -> ValidatedProofreadingResponse:
    """Parse provider text and enforce the text-free provenance contract."""
    try:
        payload = json.loads(response_text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ProofreadingError(
            "malformed_response",
            f"{provider_name} did not return valid structured JSON: {exc}",
        ) from exc
    if not isinstance(payload, dict) or set(payload) != {"corrected_text", "edits"}:
        raise ProofreadingError(
            "malformed_response",
            f"{provider_name} response must contain only corrected_text and edits.",
        )
    corrected = payload["corrected_text"]
    edits = payload["edits"]
    if not isinstance(corrected, str) or (original_text.strip() and not corrected.strip()):
        raise ProofreadingError(
            "malformed_response",
            f"{provider_name} returned an empty corrected_text for non-empty source text.",
        )
    if not isinstance(edits, list):
        raise ProofreadingError(
            "malformed_response", f"{provider_name} response edits must be an array."
        )
    validated: list[ProofreadingEdit] = []
    source_without_outer_whitespace = original_text.strip()
    corrected_without_outer_whitespace = corrected.strip()
    for index, edit in enumerate(edits, start=1):
        if not isinstance(edit, dict) or set(edit) != {
            "original",
            "corrected",
            "category",
            "reason",
        }:
            raise ProofreadingError(
                "malformed_response",
                f"{provider_name} edit {index} has an invalid shape.",
            )
        if edit["category"] not in {"spelling", "grammar", "punctuation"}:
            raise ProofreadingError(
                "malformed_response",
                f"{provider_name} edit {index} has an invalid category.",
            )
        if not all(
            isinstance(edit[key], str) and edit[key].strip()
            for key in ("original", "corrected", "reason")
        ):
            raise ProofreadingError(
                "malformed_response",
                f"{provider_name} edit {index} has an empty required value.",
            )
        if (
            edit["original"].strip() == source_without_outer_whitespace
            or edit["corrected"].strip() == corrected_without_outer_whitespace
        ):
            raise ProofreadingError(
                "malformed_response",
                f"{provider_name} edit {index} would embed a full chapter text in proofreading provenance.",
            )
        validated.append(
            ProofreadingEdit(
                original=edit["original"],
                corrected=edit["corrected"],
                category=edit["category"],
                reason=edit["reason"],
            )
        )
    text_changed = original_text.rstrip("\n") != corrected.rstrip("\n")
    if text_changed and not validated:
        raise ProofreadingError(
            "malformed_response",
            f"{provider_name} changed the text without an explanatory edit list.",
        )
    if not text_changed and validated:
        raise ProofreadingError(
            "malformed_response",
            f"{provider_name} supplied edits without changing the text.",
        )
    return ValidatedProofreadingResponse(corrected, tuple(validated))
