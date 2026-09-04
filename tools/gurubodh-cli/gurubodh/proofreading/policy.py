"""Provider-neutral request pacing, retry, and diagnostic policy."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import math
import random
import re
import time
from typing import Any, Callable

from gurubodh.proofreading.errors import ProofreadingError
from gurubodh.proofreading.settings import ProofreadingSettings


def estimate_input_tokens(text: str) -> int:
    """Return a conservative local estimate for quota pacing, not billing."""
    return max(1, math.ceil(len(text) * 1.25)) if text else 0


def _status_code(exc: Exception) -> int | None:
    for value in (
        getattr(exc, "status_code", None),
        getattr(getattr(exc, "response", None), "status_code", None),
        getattr(exc, "code", None),
    ):
        if isinstance(value, int):
            return value
    return None


def _valid_delay(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    delay = float(value)
    return delay if math.isfinite(delay) and delay >= 0 else None


def utc_now_datetime():
    """A small seam for parsing date-based HTTP retry hints."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def _retry_after_header_seconds(exc: Exception) -> float | None:
    """Read a bounded Retry-After hint without retaining response content."""
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if not headers:
        return None
    try:
        retry_after_ms = headers.get("retry-after-ms")
        if retry_after_ms is not None:
            return _valid_delay(float(retry_after_ms) / 1000)
        value = headers.get("retry-after")
    except (AttributeError, TypeError, ValueError):
        return None
    if value is None:
        return None
    try:
        numeric = _valid_delay(float(value))
    except (TypeError, ValueError):
        numeric = None
    if numeric is not None:
        return numeric
    if not isinstance(value, str):
        return None
    try:
        date_value = parsedate_to_datetime(value)
        if date_value.tzinfo is None:
            return None
        return _valid_delay((date_value - utc_now_datetime()).total_seconds())
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _retry_after_seconds(exc: Exception) -> float | None:
    value = _valid_delay(getattr(exc, "retry_after_seconds", None))
    if value is not None:
        return value
    header_value = _retry_after_header_seconds(exc)
    if header_value is not None:
        return header_value
    for message in (getattr(exc, "message", None), str(exc)):
        if not isinstance(message, str):
            continue
        match = re.search(
            r"\b(?:retry|try again)\s+(?:in|after)\s+(\d+(?:\.\d+)?)\s*(?:s|sec(?:onds?)?)\b",
            message,
            flags=re.IGNORECASE,
        )
        if match:
            return _valid_delay(float(match.group(1)))
    return None


def _api_error_detail(exc: Exception, status_code: int | None) -> str:
    """Return safe API diagnostics without serializing response content."""
    api_status = getattr(exc, "status", None)
    if isinstance(api_status, str) and re.fullmatch(r"[A-Z_]{1,64}", api_status):
        return f"HTTP {status_code} {api_status}" if status_code else api_status
    return f"HTTP {status_code}" if status_code else exc.__class__.__name__


def _is_sdk_timeout_exception(exc: Exception) -> bool:
    """Recognize built-in and common HTTP-client timeout exception chains."""
    if isinstance(exc, TimeoutError):
        return True
    pending = [exc]
    seen: set[int] = set()
    while pending:
        candidate = pending.pop()
        if id(candidate) in seen:
            continue
        seen.add(id(candidate))
        name = candidate.__class__.__name__.lower()
        module = candidate.__class__.__module__
        if "timeout" in name and (
            module.startswith(("httpx", "requests", "google"))
            or module == "builtins"
        ):
            return True
        for nested in (
            getattr(candidate, "__cause__", None),
            getattr(candidate, "__context__", None),
        ):
            if isinstance(nested, Exception):
                pending.append(nested)
    return False


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
        elapsed = _valid_delay(item.get("elapsed_seconds"))
        if elapsed is not None:
            diagnostic["elapsed_seconds"] = round(elapsed, 3)
        retry_delay = _valid_delay(item.get("retry_delay_seconds"))
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


class RequestRateLimiter:
    """Stateful local pacing for interval, request-count, and token budgets."""

    def __init__(
        self,
        settings: ProofreadingSettings,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.settings = settings
        self.clock = clock
        self.sleep = sleep
        self.requests: deque[tuple[float, int]] = deque()
        self.last_request_at: float | None = None

    def acquire(
        self,
        estimated_tokens: int,
        on_wait: Callable[[float], None] | None = None,
    ) -> float:
        now = self.clock()
        while self.requests and now - self.requests[0][0] >= 60:
            self.requests.popleft()
        waits = []
        if self.last_request_at is not None:
            waits.append(
                self.settings.min_request_interval_seconds
                - (now - self.last_request_at)
            )
        if len(self.requests) >= self.settings.max_requests_per_minute:
            waits.append(60 - (now - self.requests[0][0]))
        used_tokens = sum(tokens for _, tokens in self.requests)
        if (
            self.requests
            and used_tokens + estimated_tokens
            > self.settings.max_estimated_input_tokens_per_minute
        ):
            waits.append(60 - (now - self.requests[0][0]))
        wait_seconds = max([0.0, *waits])
        if wait_seconds:
            if on_wait:
                on_wait(wait_seconds)
            self.sleep(wait_seconds)
            now = self.clock()
            while self.requests and now - self.requests[0][0] >= 60:
                self.requests.popleft()
        self.requests.append((now, estimated_tokens))
        self.last_request_at = now
        return wait_seconds


@dataclass(frozen=True)
class RequestFailure:
    """Safe classification of a provider transport exception."""

    status_code: int | None
    detail: str
    retryable: bool
    retry_limit: int
    retry_after_seconds: float | None
    is_unavailable: bool
    is_timeout: bool


@dataclass(frozen=True)
class RetryPlan:
    delay_seconds: float
    server_retry_hint_used: bool
    source: str


class RequestPolicy:
    """Classify failures and calculate retry/terminal outcomes without an SDK."""

    def __init__(
        self,
        settings: ProofreadingSettings,
        *,
        provider_name: str,
        random_value: Callable[[], float] = random.random,
    ):
        self.settings = settings
        self.random_value = random_value
        self.provider_name = provider_name

    def classify(self, exc: Exception) -> RequestFailure:
        status_code = _status_code(exc)
        is_unavailable = status_code == 503
        is_timeout = _is_sdk_timeout_exception(exc)
        retryable = (
            status_code in {408, 429, 500, 502, 504}
            or is_unavailable
            or is_timeout
            or isinstance(exc, ConnectionError)
        )
        retry_limit = (
            self.settings.unavailable_max_retries
            if is_unavailable
            else self.settings.max_retries
        )
        return RequestFailure(
            status_code=status_code,
            detail=_api_error_detail(exc, status_code),
            retryable=retryable,
            retry_limit=retry_limit,
            retry_after_seconds=(
                _retry_after_seconds(exc) if retryable else None
            ),
            is_unavailable=is_unavailable,
            is_timeout=is_timeout,
        )

    @staticmethod
    def can_retry(failure: RequestFailure, attempts: int) -> bool:
        return failure.retryable and attempts <= failure.retry_limit

    @staticmethod
    def terminal_reason(failure: RequestFailure) -> str:
        if failure.is_unavailable:
            return "service_unavailable_retry_exhausted"
        return (
            "max_retries_exhausted"
            if failure.retryable
            else "non_retryable_api_failure"
        )

    def retry_plan(self, failure: RequestFailure, retry_number: int) -> RetryPlan:
        retry_hint = failure.retry_after_seconds
        if failure.is_unavailable:
            scheduled_delay = (
                self.settings.unavailable_first_retry_delay_seconds
                if retry_number == 1
                else self.settings.unavailable_second_retry_delay_seconds
            )
            hint_used = retry_hint is not None and retry_hint >= scheduled_delay
            delay = max(scheduled_delay, retry_hint or 0.0)
            source = (
                f"{self.provider_name}'s requested retry delay"
                if hint_used
                else "503 service-capacity recovery schedule"
            )
        else:
            delay = (
                retry_hint
                if retry_hint is not None
                else min(
                    self.settings.max_retry_delay_seconds,
                    self.settings.initial_retry_delay_seconds
                    * (2 ** (retry_number - 1)),
                )
            )
            hint_used = retry_hint is not None
            source = (
                f"{self.provider_name}'s requested retry delay"
                if hint_used
                else "exponential backoff"
            )
        delay += delay * 0.25 * self.random_value()
        return RetryPlan(delay, hint_used, source)

    def terminal_error(
        self,
        failure: RequestFailure,
        attempts: int,
        request_diagnostics: dict[str, Any] | None,
    ) -> ProofreadingError:
        if failure.is_unavailable:
            code = "service_unavailable"
            message = (
                f"{self.provider_name} service capacity is temporarily unavailable "
                f"({failure.detail}); recovery retry budget exhausted after "
                f"{attempts} request attempt(s)."
            )
        else:
            code = (
                "rate_limited"
                if failure.status_code == 429
                else ("request_timeout" if failure.is_timeout else "api_error")
            )
            message = (
                f"{self.provider_name} proofreading request failed ({failure.detail})."
            )
        terminal_reason = self.terminal_reason(failure)
        return ProofreadingError(
            code,
            message,
            retryable=failure.retryable,
            request_attempts=attempts,
            request_diagnostics=request_diagnostics,
            terminal_retry_exhaustion_reason=terminal_reason,
        )
