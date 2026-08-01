"""Stable provenance identifiers for normalized prepared chapter content."""

import hashlib
import re
import unicodedata
import uuid


# This UUID is a Gurubodh-owned, immutable namespace for content identity v1.
GURUBODH_CONTENT_NAMESPACE = uuid.UUID("7ecde8b9-3560-426a-9fd5-52bff1b6c575")
CONTENT_IDENTITY_CONTRACT_VERSION = 1
CONTENT_NORMALIZATION = "gurubodh-chapter-content-v1"
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def normalize_chapter_content_v1(text: str) -> str:
    """Apply the v1 content-key normalization contract without adding an LF."""
    if not isinstance(text, str):
        raise ValueError("Chapter content must be a string")
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip(" \t") for line in text.split("\n"))
    return text.strip()


def normalized_content_sha256(text: str) -> str:
    return hashlib.sha256(normalize_chapter_content_v1(text).encode("utf-8")).hexdigest()


def content_key(category_code: str, subject_code: str, language: str, normalized_sha256: str) -> str:
    values = {
        "category code": category_code,
        "subject code": subject_code,
        "language": language,
        "normalized content checksum": normalized_sha256,
    }
    for label, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Content identity requires a non-blank {label}")
    if not _SHA256_PATTERN.fullmatch(normalized_sha256):
        raise ValueError("Content identity requires a 64-character lowercase hexadecimal checksum")
    name = f"v1|{category_code}|{subject_code}|{language}|{normalized_sha256}"
    return str(uuid.uuid5(GURUBODH_CONTENT_NAMESPACE, name))


def build_content_identity(category_code: str, subject_code: str, language: str, text: str) -> dict:
    checksum = normalized_content_sha256(text)
    return {
        "algorithm": "uuid5",
        "namespace": str(GURUBODH_CONTENT_NAMESPACE),
        "identity_contract_version": CONTENT_IDENTITY_CONTRACT_VERSION,
        "normalization": CONTENT_NORMALIZATION,
        "normalized_content_sha256": checksum,
        "content_key": content_key(category_code, subject_code, language, checksum),
    }


def validate_content_identity(identity: dict, category_code: str, subject_code: str, language: str, text: str) -> dict:
    """Validate provenance metadata against its source text and return it."""
    if not isinstance(identity, dict):
        raise ValueError("content_identity is missing")
    expected = build_content_identity(category_code, subject_code, language, text)
    if identity != expected:
        raise ValueError("content_identity does not match the source chapter content or identity contract")
    return identity
