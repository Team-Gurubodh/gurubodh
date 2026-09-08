"""Safe configuration export boundary shared by resolution and audit writers."""

from collections.abc import Mapping
from typing import Any
import re
from urllib.parse import urlsplit, urlunsplit

REDACTED = "[redacted]"
CONFIG_SNAPSHOT_KEYS = (
    "schema_version",
    "pipeline",
    "source",
    "destination",
    "naming",
    "chunking",
    "chapters",
    "chapter_split",
    "metadata_defaults",
    "proofreading",
    "locale",
    "lab_root",
)


def _config_payload(config: Mapping[str, Any] | None) -> dict[str, Any]:
    if config is None:
        return {}
    converter = getattr(config, "to_payload", None)
    value = converter() if callable(converter) else dict(config)
    return value if isinstance(value, dict) else {}


def _secret_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    return bool(
        re.search(
            r"(?:^|_)(?:api_key|apikey|access_key|secret|secret_key|token|password|credential|credentials|authorization)(?:$|_)",
            normalized,
        )
    )


_OMIT = object()


def _safe_configuration_value(
    value: Any, key: str | None = None, *, redact_content: bool = True,
) -> Any:
    if key is not None and _secret_key(key):
        return REDACTED
    if key == "metadata_defaults" and isinstance(value, Mapping):
        # The legacy schema permits arbitrary metadata extensions. None has
        # defined execution semantics; do not export their keys or values.
        value = {name: item for name, item in value.items() if name in {
            "language", "source_script", "output_text_encoding", "summary_chapter_markers",
        }}
    if redact_content and key in {"prompt", "prompt_body", "source_text", "chapter_text", "corrected_text",
               "raw_request", "raw_response", "request_body", "response_body"}:
        return REDACTED
    if isinstance(value, str) and "://" in value:
        try:
            url = urlsplit(value)
            if url.scheme in {"http", "https"}:
                # Never export authorization/userinfo, signed queries or fragments.
                return urlunsplit((url.scheme, url.netloc.rsplit("@", 1)[-1], url.path, "", ""))
        except ValueError:
            return REDACTED
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if value == value and value not in (float("inf"), float("-inf")) else _OMIT
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for raw_key, item in value.items():
            item_key = str(raw_key)
            if item_key.startswith("_"):
                continue
            safe_item = _safe_configuration_value(item, item_key, redact_content=redact_content)
            if safe_item is not _OMIT:
                sanitized[item_key] = safe_item
        return sanitized
    if isinstance(value, (list, tuple)):
        sanitized_items = [_safe_configuration_value(item, redact_content=redact_content) for item in value]
        return [item for item in sanitized_items if item is not _OMIT]
    # Paths, compiled expressions, providers, clients, and all other runtime
    # objects are deliberately absent from a configuration snapshot.
    return _OMIT


def safe_configuration_snapshot(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return only schema-shaped, JSON-safe configuration with secrets removed."""
    payload = _config_payload(config)
    selected = {
        key: payload[key]
        for key in CONFIG_SNAPSHOT_KEYS
        if key in payload
    }
    sanitized = _safe_configuration_value(selected)
    return sanitized if isinstance(sanitized, dict) else {}


def redact_value(key: str, value: Any) -> Any:
    """Compatibility helper for callers that need the centralized policy."""
    safe = _safe_configuration_value(value, key)
    return None if safe is _OMIT else safe


def redact_mapping(data: Mapping[str, Any], *, redact_content: bool = True) -> dict[str, Any]:
    sanitized = _safe_configuration_value(data, redact_content=redact_content)
    return sanitized if isinstance(sanitized, dict) else {}
