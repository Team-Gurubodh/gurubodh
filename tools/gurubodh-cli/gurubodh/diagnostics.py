"""Shared sanitization for bounded operational request diagnostics."""

from __future__ import annotations

import math
import re
from typing import Any


def _valid_nonnegative_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else None


def safe_request_diagnostics(value: Any) -> dict[str, Any] | None:
    """Return only bounded operational request facts suitable for reports."""
    raw = getattr(
        value, "request_diagnostics", value if isinstance(value, dict) else None
    )
    if not isinstance(raw, dict):
        return None
    attempts: list[dict[str, Any]] = []
    for item in raw.get("attempts", [])[:32]:
        if not isinstance(item, dict):
            continue
        diagnostic: dict[str, Any] = {}
        attempt = item.get("attempt")
        if isinstance(attempt, int) and attempt > 0:
            diagnostic["attempt"] = attempt
        status = item.get("http_status")
        if isinstance(status, int) and 100 <= status <= 599:
            diagnostic["http_status"] = status
        elapsed = _valid_nonnegative_number(item.get("elapsed_seconds"))
        if elapsed is not None:
            diagnostic["elapsed_seconds"] = round(elapsed, 3)
        retry_delay = _valid_nonnegative_number(item.get("retry_delay_seconds"))
        if retry_delay is not None:
            diagnostic["retry_delay_seconds"] = round(retry_delay, 3)
        hint_used = item.get("server_retry_hint_used")
        if isinstance(hint_used, bool):
            diagnostic["server_retry_hint_used"] = hint_used
        if diagnostic:
            attempts.append(diagnostic)
    terminal_reason = raw.get("terminal_retry_exhaustion_reason")
    if not isinstance(terminal_reason, str) or not re.fullmatch(
        r"[a-z0-9_]{1,80}", terminal_reason
    ):
        terminal_reason = None
    if not attempts and terminal_reason is None:
        return None
    return {
        "attempts": attempts,
        "terminal_retry_exhaustion_reason": terminal_reason,
    }
