"""Proofreading provider and request-policy configuration."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


@dataclass(frozen=True)
class ProofreadingSettings:
    provider: str
    model: str
    max_output_tokens: int
    max_input_characters: int
    max_retries: int
    initial_retry_delay_seconds: float
    max_retry_delay_seconds: float
    min_request_interval_seconds: float
    max_requests_per_minute: int
    max_estimated_input_tokens_per_minute: int
    request_timeout_seconds: float
    request_progress_interval_seconds: float
    unavailable_max_retries: int
    unavailable_first_retry_delay_seconds: float
    unavailable_second_retry_delay_seconds: float
    unavailable_cooldown_seconds: float

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
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be greater than zero")
        if (
            isinstance(self.unavailable_max_retries, bool)
            or not isinstance(self.unavailable_max_retries, int)
            or not 1 <= self.unavailable_max_retries <= 2
        ):
            raise ValueError("unavailable_max_retries must be between 1 and 2")
        if self.request_progress_interval_seconds > self.request_timeout_seconds:
            raise ValueError(
                "request_progress_interval_seconds must not exceed request_timeout_seconds"
            )

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
