"""Provider-neutral proofreading orchestration."""

from __future__ import annotations

from dataclasses import dataclass
import random
import time
from typing import Callable, Protocol

from gurubodh.contracts import ProofreadingProviderResponse
from gurubodh.diagnostics import safe_request_diagnostics
from gurubodh.locales import LocaleSpec
from gurubodh.proofreading.errors import ProofreadingError
from gurubodh.proofreading.policy import (
    RequestPolicy,
    RequestRateLimiter,
    estimate_input_tokens,
)
from gurubodh.proofreading.settings import ProofreadingSettings
from gurubodh.proofreading.validation import parse_structured_response


@dataclass(frozen=True)
class RawProofreadingResponse:
    """Provider transport output before proofreading validation."""

    text: str
    elapsed_seconds: float
    usage: dict[str, int] | None


class ProofreadingTransport(Protocol):
    """Minimal transport seam consumed by provider-neutral orchestration."""

    @property
    def last_request_elapsed_seconds(self) -> float: ...

    def send(
        self,
        text: str,
        progress: Callable[[str], None] | None = None,
    ) -> RawProofreadingResponse: ...


class ProofreadingService:
    """Apply request policy and validation around a proofreading transport."""

    def __init__(
        self,
        settings: ProofreadingSettings,
        transport: ProofreadingTransport,
        *,
        provider_name: str,
        locale: LocaleSpec | None,
        sleep: Callable[[float], None] = time.sleep,
        random_value: Callable[[], float] = random.random,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.settings = settings
        self.transport = transport
        self.provider_name = provider_name
        self.locale = locale
        self._sleep = sleep
        self._limiter = RequestRateLimiter(settings, clock=clock, sleep=sleep)
        self._policy = RequestPolicy(
            settings,
            provider_name=provider_name,
            random_value=random_value,
        )

    def proofread(
        self,
        text: str,
        progress: Callable[[str], None] | None = None,
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
        request_attempt_diagnostics: list[dict[str, object]] = []

        def announce_local_wait(wait_seconds: float) -> None:
            if progress:
                progress(
                    f"Waiting {wait_seconds:.1f} seconds for local {self.provider_name} request pacing."
                )

        while True:
            attempts += 1
            if progress:
                progress(
                    f"Checking local {self.provider_name} request pacing before sending."
                )
            total_throttle_seconds += self._limiter.acquire(
                estimated_tokens,
                on_wait=announce_local_wait if progress else None,
            )
            if progress:
                progress(
                    f"Sending {self.provider_name} request "
                    f"(attempt {attempts}; estimated input {estimated_tokens} tokens; "
                    f"timeout {self.settings.request_timeout_seconds:.1f} seconds)."
                )
            try:
                response = self.transport.send(text, progress=progress)
                request_attempt_diagnostics.append(
                    {
                        "attempt": attempts,
                        "http_status": 200,
                        "elapsed_seconds": round(response.elapsed_seconds, 3),
                        "server_retry_hint_used": False,
                    }
                )
                try:
                    validated = parse_structured_response(
                        response.text,
                        text,
                        provider_name=self.provider_name,
                    )
                except ProofreadingError as exc:
                    # The request itself completed even if its response violated
                    # the proofreading contract.
                    exc.request_attempts = attempts
                    exc.successful_request_attempts = 1
                    exc.request_diagnostics = safe_request_diagnostics(
                        {
                            "attempts": request_attempt_diagnostics,
                            "terminal_retry_exhaustion_reason": None,
                        }
                    )
                    raise
                if progress:
                    progress(
                        f"{self.provider_name} response received; validating and writing canonical artifacts."
                    )
                return {
                    "corrected_text": validated.corrected_text,
                    "edits": [edit.to_payload() for edit in validated.edits],
                    "estimated_input_tokens": estimated_tokens,
                    "attempts": attempts,
                    "successful_request_attempts": 1,
                    "failed_request_attempts": attempts - 1,
                    "throttle_seconds": round(total_throttle_seconds, 3),
                    "usage": response.usage,
                    "request_diagnostics": safe_request_diagnostics(
                        {
                            "attempts": request_attempt_diagnostics,
                            "terminal_retry_exhaustion_reason": None,
                        }
                    ),
                }
            except ProofreadingError:
                raise
            except Exception as exc:
                failure = self._policy.classify(exc)
                request_attempt_diagnostics.append(
                    {
                        "attempt": attempts,
                        "http_status": failure.status_code,
                        "elapsed_seconds": round(
                            self.transport.last_request_elapsed_seconds, 3
                        ),
                        "server_retry_hint_used": False,
                    }
                )
                if not self._policy.can_retry(failure, attempts):
                    diagnostics = safe_request_diagnostics(
                        {
                            "attempts": request_attempt_diagnostics,
                            "terminal_retry_exhaustion_reason": self._policy.terminal_reason(
                                failure
                            ),
                        }
                    )
                    raise self._policy.terminal_error(
                        failure, attempts, diagnostics
                    ) from exc
                retry = self._policy.retry_plan(failure, attempts)
                request_attempt_diagnostics[-1]["retry_delay_seconds"] = round(
                    retry.delay_seconds, 3
                )
                request_attempt_diagnostics[-1][
                    "server_retry_hint_used"
                ] = retry.server_retry_hint_used
                if progress:
                    progress(
                        f"{self.provider_name} returned a transient "
                        f"{failure.status_code or 'network'} error; retrying in "
                        f"{retry.delay_seconds:.1f} seconds ({retry.source})."
                    )
                self._sleep(retry.delay_seconds)
                total_throttle_seconds += retry.delay_seconds
