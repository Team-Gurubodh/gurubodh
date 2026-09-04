"""Domain failures raised by proofreading providers and use cases."""

from __future__ import annotations

from typing import Any

from gurubodh.errors import ProcessingError


class ProofreadingError(ProcessingError):
    """A bounded proofreading failure safe to translate at workflow boundaries."""

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
