"""Google Gemini SDK transport and its production proofreading composition."""

from __future__ import annotations

import os
import random
import threading
import time
from typing import Any, Callable

from gurubodh.locales import LocaleSpec
from gurubodh.proofreading.errors import ProofreadingError
from gurubodh.proofreading.service import (
    ProofreadingService,
    RawProofreadingResponse,
)
from gurubodh.proofreading.settings import ProofreadingSettings
from gurubodh.proofreading.validation import EDIT_LIST_SCHEMA


GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY"


def _usage_summary(usage: Any) -> dict[str, int] | None:
    if usage is None:
        return None
    values = {}
    for source, target in (
        ("prompt_token_count", "input_tokens"),
        ("candidates_token_count", "output_tokens"),
        ("total_token_count", "total_tokens"),
    ):
        value = getattr(usage, source, None)
        if isinstance(value, int):
            values[target] = value
    return values or None


class GeminiTransport:
    """Translate explicit locale/settings inputs into one Gemini SDK request."""

    def __init__(
        self,
        settings: ProofreadingSettings,
        locale: LocaleSpec | None,
        *,
        client: Any | None = None,
        types_module: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.settings = settings
        self.locale = locale
        self._client = client
        self._types_module = types_module
        self._clock = clock
        self._last_request_elapsed_seconds = 0.0

    @property
    def client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = os.environ.get(GEMINI_API_KEY_ENV_VAR)
        if not api_key:
            raise ProofreadingError(
                "missing_credentials",
                f"Set {GEMINI_API_KEY_ENV_VAR} before enabling proofreading.",
            )
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ProofreadingError(
                "missing_dependency",
                "Proofreading requires the google-genai package. Reinstall Gurubodh CLI dependencies.",
            ) from exc
        self._types_module = types
        self._client = genai.Client(api_key=api_key)
        return self._client

    @property
    def last_request_elapsed_seconds(self) -> float:
        return self._last_request_elapsed_seconds

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
            http_options={
                "timeout": int(self.settings.request_timeout_seconds * 1000)
            },
        )

    def send(
        self,
        text: str,
        progress: Callable[[str], None] | None = None,
    ) -> RawProofreadingResponse:
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
            except BaseException as exc:  # Re-raise the SDK error on the caller thread.
                result["error"] = exc
            finally:
                completed.set()

        thread = threading.Thread(
            target=generate,
            name="gurubodh-gemini-request",
            daemon=True,
        )
        thread.start()
        while not completed.wait(self.settings.request_progress_interval_seconds):
            # Do not race a just-completed response into a stale heartbeat.
            if completed.is_set():
                break
            elapsed = max(0.0, self._clock() - started_at)
            remaining = max(
                0.0, self.settings.request_timeout_seconds - elapsed
            )
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
        response = result["response"]
        return RawProofreadingResponse(
            text=response.text,
            elapsed_seconds=elapsed,
            usage=_usage_summary(getattr(response, "usage_metadata", None)),
        )


class GeminiProofreader(ProofreadingService):
    """Compatibility-friendly Gemini composition implementing Proofreader."""

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
        transport = GeminiTransport(
            settings,
            locale,
            client=client,
            types_module=types_module,
            clock=clock,
        )
        self._gemini_transport = transport
        super().__init__(
            settings,
            transport,
            provider_name="Gemini",
            locale=locale,
            sleep=sleep,
            random_value=random_value,
            clock=clock,
        )

    @property
    def client(self) -> Any:
        """Retain the prior lazy-client inspection seam."""
        return self._gemini_transport.client
