"""Gemini-backed canonical locale-aware chapter proofreading artifacts."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import difflib
from email.utils import parsedate_to_datetime
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import threading
import time
from typing import Any, Callable

from gurubodh.contracts import (
    CheckpointArtifactRecord,
    PrepSubjectJob,
    Proofreader,
    ProofreadingOutcome,
    ProofreadingProviderResponse,
    ProofreadingStatus,
)
from gurubodh.constants import ENTRY_POINT_PREP_SUBJECT
from gurubodh.content_identity import build_content_identity
from gurubodh.errors import ProcessingError
from gurubodh.locales import LocaleSpec
from gurubodh.metadata import build_chapter_metadata
from gurubodh.naming import chapter_output_filename
from gurubodh.schema_validation import write_json_artifact
from gurubodh.storage import destination_artifact_reference
from gurubodh.time_utils import utc_now


GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY"
PROOFREADING_OUTPUT_DIR = "proofreading"
PROOFREADING_MANIFEST_FILENAME = "proofreading_manifest.json"
PROOFREADING_SCHEMA_VERSION = 2

EDIT_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "corrected_text": {"type": "string", "description": "Corrected source text only."},
        "edits": {
            "type": "array",
            "description": "Every spelling, grammar, or punctuation correction.",
            "items": {
                "type": "object",
                "properties": {
                    "original": {"type": "string"},
                    "corrected": {"type": "string"},
                    "category": {"type": "string", "enum": ["spelling", "grammar", "punctuation"]},
                    "reason": {"type": "string"},
                },
                "required": ["original", "corrected", "category", "reason"],
            },
        },
    },
    "required": ["corrected_text", "edits"],
}


class ProofreadingError(ProcessingError):
    def __init__(
        self,
        code: str,
        message: str,
        retryable: bool = False,
        retry_after_seconds: float | None = None,
        request_attempts: int = 0,
        successful_request_attempts: int = 0,
        request_diagnostics: dict[str, Any] | None = None,
        terminal_retry_exhaustion_reason: str | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        # These are deliberately request-level counters, not chapter counters.
        # They let resumable callers audit retries and terminal API failures.
        self.request_attempts = request_attempts
        self.successful_request_attempts = successful_request_attempts
        self.request_diagnostics = request_diagnostics
        self.terminal_retry_exhaustion_reason = terminal_retry_exhaustion_reason


@dataclass(frozen=True)
class ProofreadingSettings:
    provider: str = "google-ai-studio"
    model: str = "gemini-3.7-flash"
    max_output_tokens: int = 8192
    max_input_characters: int = 30000
    max_retries: int = 3
    initial_retry_delay_seconds: float = 2.0
    max_retry_delay_seconds: float = 30.0
    min_request_interval_seconds: float = 6.0
    max_requests_per_minute: int = 8
    max_estimated_input_tokens_per_minute: int = 20000
    request_timeout_seconds: float = 120.0
    request_progress_interval_seconds: float = 15.0
    unavailable_max_retries: int = 2
    unavailable_first_retry_delay_seconds: float = 30.0
    unavailable_second_retry_delay_seconds: float = 90.0
    unavailable_cooldown_seconds: float = 120.0

    def __post_init__(self) -> None:
        positive_settings = (
            "request_timeout_seconds",
            "request_progress_interval_seconds",
            "unavailable_first_retry_delay_seconds",
            "unavailable_second_retry_delay_seconds",
            "unavailable_cooldown_seconds",
        )
        for name in positive_settings:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if (
            isinstance(self.unavailable_max_retries, bool)
            or not isinstance(self.unavailable_max_retries, int)
            or not 1 <= self.unavailable_max_retries <= 2
        ):
            raise ValueError("unavailable_max_retries must be between 1 and 2")
        if self.request_progress_interval_seconds > self.request_timeout_seconds:
            raise ValueError("request_progress_interval_seconds must not exceed request_timeout_seconds")

    def public_dict(self) -> dict[str, Any]:
        return {
            "mandatory": True,
            "provider": self.provider,
            "model": self.model,
            "max_output_tokens": self.max_output_tokens,
            "max_input_characters": self.max_input_characters,
            "max_retries": self.max_retries,
            "initial_retry_delay_seconds": self.initial_retry_delay_seconds,
            "max_retry_delay_seconds": self.max_retry_delay_seconds,
            "min_request_interval_seconds": self.min_request_interval_seconds,
            "max_requests_per_minute": self.max_requests_per_minute,
            "max_estimated_input_tokens_per_minute": self.max_estimated_input_tokens_per_minute,
            "request_timeout_seconds": self.request_timeout_seconds,
            "request_progress_interval_seconds": self.request_progress_interval_seconds,
            "unavailable_max_retries": self.unavailable_max_retries,
            "unavailable_first_retry_delay_seconds": self.unavailable_first_retry_delay_seconds,
            "unavailable_second_retry_delay_seconds": self.unavailable_second_retry_delay_seconds,
            "unavailable_cooldown_seconds": self.unavailable_cooldown_seconds,
        }


def estimate_input_tokens(text: str) -> int:
    """A deliberately conservative local estimate for quota pacing, not billing."""
    return max(1, math.ceil(len(text) * 1.25)) if text else 0


def _tokens(text: str) -> list[str]:
    return re.findall(r"\s+|\S+", text, flags=re.UNICODE)


def word_level_diff(original: str, corrected: str) -> tuple[str, dict[str, Any]]:
    """Render a whitespace-preserving word diff without another model request."""
    original_tokens, corrected_tokens = _tokens(original), _tokens(corrected)
    matcher = difflib.SequenceMatcher(None, original_tokens, corrected_tokens, autojunk=False)
    rendered: list[str] = []
    changed_segments = 0
    removed_words = added_words = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            rendered.extend(original_tokens[i1:i2])
            continue
        changed_segments += 1
        removed, added = "".join(original_tokens[i1:i2]), "".join(corrected_tokens[j1:j2])
        removed_words += len(re.findall(r"\S+", removed))
        added_words += len(re.findall(r"\S+", added))
        if removed:
            rendered.append(f"[-{removed}-]")
        if added:
            rendered.append(f"{{+{added}+}}")
    return "".join(rendered), {
        "total_words_original": len(re.findall(r"\S+", original)),
        "total_words_corrected": len(re.findall(r"\S+", corrected)),
        "changed_segments": changed_segments,
        "removed_word_count": removed_words,
        "added_word_count": added_words,
        "similarity_ratio": round(matcher.ratio(), 3),
    }


def _validated_response(response_text: str, original_text: str) -> tuple[str, list[dict[str, str]]]:
    try:
        payload = json.loads(response_text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ProofreadingError("malformed_response", f"Gemini did not return valid structured JSON: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != {"corrected_text", "edits"}:
        raise ProofreadingError("malformed_response", "Gemini response must contain only corrected_text and edits.")
    corrected = payload["corrected_text"]
    edits = payload["edits"]
    if not isinstance(corrected, str) or (original_text.strip() and not corrected.strip()):
        raise ProofreadingError("malformed_response", "Gemini returned an empty corrected_text for non-empty source text.")
    if not isinstance(edits, list):
        raise ProofreadingError("malformed_response", "Gemini response edits must be an array.")
    validated: list[dict[str, str]] = []
    source_without_outer_whitespace = original_text.strip()
    corrected_without_outer_whitespace = corrected.strip()
    for index, edit in enumerate(edits, start=1):
        if not isinstance(edit, dict) or set(edit) != {"original", "corrected", "category", "reason"}:
            raise ProofreadingError("malformed_response", f"Gemini edit {index} has an invalid shape.")
        if edit["category"] not in {"spelling", "grammar", "punctuation"}:
            raise ProofreadingError("malformed_response", f"Gemini edit {index} has an invalid category.")
        if not all(isinstance(edit[key], str) and edit[key].strip() for key in ("original", "corrected", "reason")):
            raise ProofreadingError("malformed_response", f"Gemini edit {index} has an empty required value.")
        if (
            edit["original"].strip() == source_without_outer_whitespace
            or edit["corrected"].strip() == corrected_without_outer_whitespace
        ):
            raise ProofreadingError(
                "malformed_response",
                f"Gemini edit {index} would embed a full chapter text in proofreading provenance.",
            )
        validated.append({key: edit[key] for key in ("original", "corrected", "category", "reason")})
    text_changed = original_text.rstrip("\n") != corrected.rstrip("\n")
    if text_changed and not validated:
        raise ProofreadingError("malformed_response", "Gemini changed the text without an explanatory edit list.")
    if not text_changed and validated:
        raise ProofreadingError("malformed_response", "Gemini supplied edits without changing the text.")
    return corrected, validated


def _status_code(exc: Exception) -> int | None:
    for value in (getattr(exc, "status_code", None), getattr(getattr(exc, "response", None), "status_code", None), getattr(exc, "code", None)):
        if isinstance(value, int):
            return value
    return None


def _valid_delay(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    delay = float(value)
    return delay if math.isfinite(delay) and delay >= 0 else None


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


def utc_now_datetime():
    """A small seam for parsing date-based HTTP retry hints."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


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
        detail = f"HTTP {status_code} {api_status}" if status_code else api_status
    else:
        detail = f"HTTP {status_code}" if status_code else exc.__class__.__name__
    return detail


def _is_sdk_timeout_exception(exc: Exception) -> bool:
    """Recognize built-in and HTTP-client timeout classes used by Google Gen AI."""
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
            module.startswith(("httpx", "requests", "google")) or module == "builtins"
        ):
            return True
        for nested in (getattr(candidate, "__cause__", None), getattr(candidate, "__context__", None)):
            if isinstance(nested, Exception):
                pending.append(nested)
    return False


def _safe_request_diagnostics(value: Any) -> dict[str, Any] | None:
    """Return only bounded operational request facts suitable for durable reports."""
    raw = getattr(value, "request_diagnostics", value if isinstance(value, dict) else None)
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
    if not isinstance(terminal_reason, str) or not re.fullmatch(r"[a-z0-9_]{1,80}", terminal_reason):
        terminal_reason = None
    if not attempts and terminal_reason is None:
        return None
    return {"attempts": attempts, "terminal_retry_exhaustion_reason": terminal_reason}


def safe_request_diagnostics(value: Any) -> dict[str, Any] | None:
    """Expose safe request facts for lab and checkpoint failure reports."""
    return _safe_request_diagnostics(value)


class RequestRateLimiter:
    def __init__(self, settings: ProofreadingSettings, clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        self.settings = settings
        self.clock = clock
        self.sleep = sleep
        self.requests: deque[tuple[float, int]] = deque()
        self.last_request_at: float | None = None

    def acquire(self, estimated_tokens: int, on_wait: Callable[[float], None] | None = None) -> float:
        now = self.clock()
        while self.requests and now - self.requests[0][0] >= 60:
            self.requests.popleft()
        waits = []
        if self.last_request_at is not None:
            waits.append(self.settings.min_request_interval_seconds - (now - self.last_request_at))
        if len(self.requests) >= self.settings.max_requests_per_minute:
            waits.append(60 - (now - self.requests[0][0]))
        used_tokens = sum(tokens for _, tokens in self.requests)
        if self.requests and used_tokens + estimated_tokens > self.settings.max_estimated_input_tokens_per_minute:
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


class GeminiProofreader:
    def __init__(
        self,
        settings: ProofreadingSettings,
        locale: LocaleSpec | None = None,
        client: Any | None = None,
        types_module: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
        random_value: Callable[[], float] = random.random,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.settings = settings
        self.locale = locale
        self._client = client
        self._types_module = types_module
        self._sleep = sleep
        self._random_value = random_value
        self._clock = clock
        self._last_request_elapsed_seconds = 0.0
        self._limiter = RequestRateLimiter(settings, clock=clock, sleep=sleep)

    @property
    def client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = os.environ.get(GEMINI_API_KEY_ENV_VAR)
        if not api_key:
            raise ProofreadingError("missing_credentials", f"Set {GEMINI_API_KEY_ENV_VAR} before enabling proofreading.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ProofreadingError("missing_dependency", "Proofreading requires the google-genai package. Reinstall Gurubodh CLI dependencies.") from exc
        self._types_module = types
        self._client = genai.Client(api_key=api_key)
        return self._client

    def _config(self) -> Any:
        if self._types_module is None:
            _ = self.client
        if self.locale is None:
            raise ProofreadingError(
                "missing_locale",
                "Gemini proofreading requires an explicitly selected supported language.",
            )
        return self._types_module.GenerateContentConfig(
            system_instruction=self.locale.proofreading_instruction,
            max_output_tokens=self.settings.max_output_tokens,
            response_mime_type="application/json",
            response_schema=EDIT_LIST_SCHEMA,
            http_options={"timeout": int(self.settings.request_timeout_seconds * 1000)},
        )

    def _generate_content_with_progress(
        self,
        text: str,
        progress: Callable[[str], None] | None,
    ) -> tuple[Any, float]:
        """Run the synchronous SDK call while reporting bounded request status."""
        started_at = self._clock()
        completed = threading.Event()
        result: dict[str, Any] = {}

        def generate() -> None:
            try:
                result["response"] = self.client.models.generate_content(
                    model=self.settings.model,
                    contents=f"<source-text>\n{text}\n</source-text>",
                    config=self._config(),
                )
            except BaseException as exc:  # Re-raise the original SDK error on the caller thread.
                result["error"] = exc
            finally:
                completed.set()

        thread = threading.Thread(target=generate, name="gurubodh-gemini-request", daemon=True)
        thread.start()
        while not completed.wait(self.settings.request_progress_interval_seconds):
            # Do not race a just-completed response into a stale heartbeat.
            if completed.is_set():
                break
            elapsed = max(0.0, self._clock() - started_at)
            remaining = max(0.0, self.settings.request_timeout_seconds - elapsed)
            if progress:
                progress(
                    "Gemini request is still in progress "
                    f"({elapsed:.1f}s elapsed; {remaining:.1f}s remaining before the "
                    f"{self.settings.request_timeout_seconds:.1f}s timeout)."
                )
        thread.join()
        elapsed = max(0.0, self._clock() - started_at)
        self._last_request_elapsed_seconds = elapsed
        if "error" in result:
            raise result["error"]
        return result["response"], elapsed

    def _unavailable_retry_delay(self, retry_number: int, retry_hint: float | None) -> tuple[float, bool]:
        if retry_number == 1:
            scheduled_delay = self.settings.unavailable_first_retry_delay_seconds
        else:
            scheduled_delay = self.settings.unavailable_second_retry_delay_seconds
        hint_used = retry_hint is not None and retry_hint >= scheduled_delay
        delay = max(scheduled_delay, retry_hint or 0.0)
        return delay + delay * 0.25 * self._random_value(), hint_used

    def proofread(
        self, text: str, progress: Callable[[str], None] | None = None
    ) -> ProofreadingProviderResponse:
        estimated_tokens = estimate_input_tokens(text)
        if len(text) > self.settings.max_input_characters:
            raise ProofreadingError(
                "input_too_large",
                f"Chapter has {len(text)} characters; configured proofreading limit is {self.settings.max_input_characters}.",
            )
        if estimated_tokens > self.settings.max_estimated_input_tokens_per_minute:
            raise ProofreadingError(
                "input_too_large",
                "Chapter estimated input tokens exceed the configured per-minute proofreading budget.",
            )
        attempts = 0
        total_throttle_seconds = 0.0
        request_attempt_diagnostics: list[dict[str, Any]] = []

        def announce_local_wait(wait_seconds: float) -> None:
            if progress:
                progress(f"Waiting {wait_seconds:.1f} seconds for local Gemini request pacing.")

        while True:
            attempts += 1
            if progress:
                progress("Checking local Gemini request pacing before sending.")
            total_throttle_seconds += self._limiter.acquire(
                estimated_tokens,
                on_wait=announce_local_wait if progress else None,
            )
            if progress:
                progress(
                    "Sending Gemini request "
                    f"(attempt {attempts}; estimated input {estimated_tokens} tokens; "
                    f"timeout {self.settings.request_timeout_seconds:.1f} seconds)."
                )
            try:
                response, request_elapsed_seconds = self._generate_content_with_progress(text, progress)
                request_attempt_diagnostics.append(
                    {
                        "attempt": attempts,
                        "http_status": 200,
                        "elapsed_seconds": round(request_elapsed_seconds, 3),
                        "server_retry_hint_used": False,
                    }
                )
                try:
                    corrected, edits = _validated_response(response.text, text)
                except ProofreadingError as exc:
                    # The request itself completed even if its response violated
                    # the proofreading contract.
                    exc.request_attempts = attempts
                    exc.successful_request_attempts = 1
                    exc.request_diagnostics = _safe_request_diagnostics(
                        {"attempts": request_attempt_diagnostics, "terminal_retry_exhaustion_reason": None}
                    )
                    raise
                if progress:
                    progress("Gemini response received; validating and writing canonical artifacts.")
                return {
                    "corrected_text": corrected,
                    "edits": edits,
                    "estimated_input_tokens": estimated_tokens,
                    "attempts": attempts,
                    "successful_request_attempts": 1,
                    "failed_request_attempts": attempts - 1,
                    "throttle_seconds": round(total_throttle_seconds, 3),
                    "usage": usage_summary(getattr(response, "usage_metadata", None)),
                    "request_diagnostics": _safe_request_diagnostics(
                        {"attempts": request_attempt_diagnostics, "terminal_retry_exhaustion_reason": None}
                    ),
                }
            except ProofreadingError:
                raise
            except Exception as exc:
                status_code = _status_code(exc)
                request_elapsed_seconds = self._last_request_elapsed_seconds
                request_attempt_diagnostics.append(
                    {
                        "attempt": attempts,
                        "http_status": status_code,
                        "elapsed_seconds": round(request_elapsed_seconds, 3),
                        "server_retry_hint_used": False,
                    }
                )
                is_unavailable = status_code == 503
                is_timeout = _is_sdk_timeout_exception(exc)
                retryable = status_code in {408, 429, 500, 502, 504} or is_unavailable or is_timeout or isinstance(exc, ConnectionError)
                retry_limit = self.settings.unavailable_max_retries if is_unavailable else self.settings.max_retries
                if not retryable or attempts > retry_limit:
                    if is_unavailable:
                        code = "service_unavailable"
                        terminal_reason = "service_unavailable_retry_exhausted"
                        message = (
                            "Gemini service capacity is temporarily unavailable "
                            f"({_api_error_detail(exc, status_code)}); recovery retry budget exhausted after "
                            f"{attempts} request attempt(s)."
                        )
                    else:
                        code = "rate_limited" if status_code == 429 else ("request_timeout" if is_timeout else "api_error")
                        terminal_reason = "max_retries_exhausted" if retryable else "non_retryable_api_failure"
                        message = f"Gemini proofreading request failed ({_api_error_detail(exc, status_code)})."
                    diagnostics = _safe_request_diagnostics(
                        {
                            "attempts": request_attempt_diagnostics,
                            "terminal_retry_exhaustion_reason": terminal_reason,
                        }
                    )
                    raise ProofreadingError(
                        code,
                        message,
                        retryable=retryable,
                        request_attempts=attempts,
                        request_diagnostics=diagnostics,
                        terminal_retry_exhaustion_reason=terminal_reason,
                    ) from exc
                retry_after = _retry_after_seconds(exc)
                if is_unavailable:
                    delay, hint_used = self._unavailable_retry_delay(attempts, retry_after)
                    source = "Gemini's requested retry delay" if hint_used else "503 service-capacity recovery schedule"
                else:
                    delay = retry_after if retry_after is not None else min(
                        self.settings.max_retry_delay_seconds,
                        self.settings.initial_retry_delay_seconds * (2 ** (attempts - 1)),
                    )
                    delay += delay * 0.25 * self._random_value()
                    hint_used = retry_after is not None
                    source = "Gemini's requested retry delay" if hint_used else "exponential backoff"
                request_attempt_diagnostics[-1]["retry_delay_seconds"] = round(delay, 3)
                request_attempt_diagnostics[-1]["server_retry_hint_used"] = hint_used
                if progress:
                    progress(
                        f"Gemini returned a transient {status_code or 'network'} error; "
                        f"retrying in {delay:.1f} seconds ({source})."
                    )
                self._sleep(delay)
                total_throttle_seconds += delay


def usage_summary(usage: Any) -> dict[str, int] | None:
    if usage is None:
        return None
    values = {}
    for source, target in (("prompt_token_count", "input_tokens"), ("candidates_token_count", "output_tokens"), ("total_token_count", "total_tokens")):
        value = getattr(usage, source, None)
        if isinstance(value, int):
            values[target] = value
    return values or None


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((text if text.endswith("\n") else text + "\n").encode("utf-8"))


def _proofread_artifact_paths(proofreading_dir: Path, text_filename: str) -> dict[str, Path]:
    stem = Path(text_filename).stem
    return {
        "diff": proofreading_dir / f"{stem}.proofread.diff.txt",
        "json": proofreading_dir / f"{stem}.proofread.json",
    }


def _artifact_integrity(path: Path) -> dict[str, Any]:
    return {"algorithm": "sha256", "encoding": "UTF-8", "line_endings": "LF", "scope": "artifact-bytes", "value": hashlib.sha256(path.read_bytes()).hexdigest()}


def _canonical_text_filename(unmodified_source_filename: str) -> str:
    suffix = "_unmodified_source.txt"
    if not unmodified_source_filename.endswith(suffix):
        raise ProofreadingError(
            "invalid_unmodified_source_artifact",
            f"Unmodified source artifact has an unexpected filename: {unmodified_source_filename}",
        )
    return f"{unmodified_source_filename.removesuffix(suffix)}.txt"


def _chapter_file_names(config: dict[str, Any], chapter_number: int) -> dict[str, Any]:
    text_name = chapter_output_filename(config, chapter_number, ".txt")
    metadata_name = chapter_output_filename(config, chapter_number, ".json")
    return {
        "metadata": metadata_name,
        "text": text_name,
        "metadata_relative_path": Path("chapters") / "text_and_metadata" / metadata_name,
        "text_relative_path": Path("chapters") / "text_and_metadata" / text_name,
    }


def _canonical_text_value(corrected_text: str) -> str:
    """Normalize canonical artifact line endings without applying identity normalization."""
    return corrected_text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def _validate_proofreader_locale(proofreader: Proofreader, locale: LocaleSpec) -> None:
    """Reject a caller-supplied Gemini client whose prompt locale disagrees.

    This guard runs before the request. It protects the canonical metadata
    language from being paired with a Gemini instruction selected for another
    locale while preserving lightweight fake proofreaders used by tests.
    """
    if isinstance(proofreader, GeminiProofreader):
        selected = proofreader.locale
        if selected is None or selected.language != locale.language:
            selected_language = selected.language if selected else "none"
            raise ProofreadingError(
                "locale_mismatch",
                f"Selected proofreading language {selected_language!r} does not match chapter metadata language {locale.language!r}.",
            )


def proofread_single_chapter_artifacts(
    config: PrepSubjectJob,
    paths: dict[str, Path],
    chapter_number: int,
    unmodified_source_path: Path,
    converter_counts: dict[str, int] | None = None,
    entry_point: str = ENTRY_POINT_PREP_SUBJECT,
    proofreader: Proofreader | None = None,
    progress: Callable[[str], None] | None = None,
) -> ProofreadingOutcome:
    """Proofread one staged chapter and write its complete artifact set.

    The caller owns checkpointing.  This deliberately returns only bounded
    provenance and artifact checksums; neither the source nor corrected text is
    returned for inclusion in a job checkpoint or audit record.
    """
    settings = config.proofreading_settings
    source_bytes = unmodified_source_path.read_bytes()
    source_text = source_bytes.decode("utf-8")
    locale = config.locale
    source_identity = build_content_identity(
        config["naming"]["category_code"],
        config["naming"]["subject_code"],
        locale.language,
        source_text,
    )
    text_filename = _canonical_text_filename(unmodified_source_path.name)
    file_names = _chapter_file_names(config, chapter_number)
    if text_filename != file_names["text"]:
        raise ProofreadingError(
            "invalid_unmodified_source_artifact",
            f"Unmodified source filename does not match chapter {chapter_number:03d}: {unmodified_source_path.name}",
        )

    proofreader = proofreader or GeminiProofreader(settings, locale=locale)
    _validate_proofreader_locale(proofreader, locale)
    response = proofreader.proofread(source_text, progress=progress)
    canonical_text = _canonical_text_value(response["corrected_text"])
    canonical_text_path = paths["text_and_metadata"] / text_filename
    metadata_path = paths["text_and_metadata"] / file_names["metadata"]
    _write_text(canonical_text_path, canonical_text)
    metadata = build_chapter_metadata(
        config,
        chapter_number,
        file_names,
        canonical_text,
        converter_counts or {},
        utc_now(),
        entry_point,
    )
    write_json_artifact(metadata_path, metadata, "chapter metadata")

    canonical_artifact_text = canonical_text_path.read_text(encoding="utf-8")
    rendered_diff, diff_summary = word_level_diff(source_text, canonical_artifact_text)
    proof_dir = paths["proofreading"]
    proof_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths = _proofread_artifact_paths(proof_dir, text_filename)
    _write_text(artifact_paths["diff"], "Word-level proof-reading diff. [-removed-] {+added+}\n\n" + rendered_diff)
    relative_dir = Path("chapters") / PROOFREADING_OUTPUT_DIR
    canonical_integrity = _artifact_integrity(canonical_text_path)
    payload = {
        "schema_version": PROOFREADING_SCHEMA_VERSION,
        "status": "succeeded",
        "created_at": utc_now(),
        "provider": {"name": settings.provider, "model": settings.model},
        "proofreading_locale": locale.proofreading_provenance(),
        "unmodified_source": {
            "text_artifact": destination_artifact_reference(
                config,
                Path("chapters") / "unmodified_source_text" / unmodified_source_path.name,
            ),
            "text_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "content_identity": source_identity,
        },
        "canonical_corrected": {
            "text_artifact": metadata["storage"]["artifacts"]["text"],
            "text_sha256": canonical_integrity["value"],
            "content_identity": metadata["content_identity"],
        },
        "diff_artifact": destination_artifact_reference(config, relative_dir / artifact_paths["diff"].name),
        "integrity": {
            "unmodified_source": _artifact_integrity(unmodified_source_path),
            "canonical_corrected": canonical_integrity,
            "diff": _artifact_integrity(artifact_paths["diff"]),
        },
        "local_diff_summary": diff_summary,
        "gemini_edits": response["edits"],
        "request": {
            **{key: response[key] for key in ("estimated_input_tokens", "attempts", "throttle_seconds", "usage")},
            "diagnostics": response.get("request_diagnostics"),
        },
    }
    write_json_artifact(artifact_paths["json"], payload, "chapter proofreading")
    artifact_files = [
        unmodified_source_path,
        canonical_text_path,
        metadata_path,
        artifact_paths["diff"],
        artifact_paths["json"],
    ]
    return ProofreadingOutcome(
        chapter_number=f"{chapter_number:03d}",
        status=ProofreadingStatus.SUCCEEDED,
        correction_count=len(response["edits"]),
        request_attempts=response["attempts"],
        successful_request_attempts=response.get(
            "successful_request_attempts", response["attempts"]
        ),
        request_diagnostics=response.get("request_diagnostics"),
        local_diff_summary=diff_summary,
        unmodified_source_content_key=source_identity["content_key"],
        canonical_content_key=metadata["content_identity"]["content_key"],
        artifacts={
            "unmodified_source": destination_artifact_reference(
                config,
                Path("chapters") / "unmodified_source_text" / unmodified_source_path.name,
            ),
            "canonical_text": metadata["storage"]["artifacts"]["text"],
            "canonical_metadata": metadata["storage"]["artifacts"]["metadata"],
            **{key: destination_artifact_reference(config, relative_dir / path.name) for key, path in artifact_paths.items()},
        },
        checkpoint_artifacts=tuple(
            CheckpointArtifactRecord(
                path=str(path.relative_to(paths["subject"])),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
            for path in artifact_files
            if path.is_file()
        ),
    )


def write_proofreading_manifest(
    paths: dict[str, Path],
    settings: ProofreadingSettings,
    chapters: list[dict[str, Any]],
    locale: LocaleSpec,
) -> Path:
    """Write the final canonical proofreading provenance manifest."""
    manifest = {
        "schema_version": PROOFREADING_SCHEMA_VERSION,
        "provider": {"name": settings.provider, "model": settings.model},
        "proofreading_locale": locale.proofreading_provenance(),
        "counts": {"succeeded": len(chapters), "failed": 0, "skipped": 0},
        "chapters": [{key: value for key, value in chapter.items() if key != "checkpoint_artifacts"} for chapter in chapters],
    }
    manifest_path = paths["proofreading"] / PROOFREADING_MANIFEST_FILENAME
    return write_json_artifact(manifest_path, manifest, "proofreading manifest")
