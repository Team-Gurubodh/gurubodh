"""Focused proofreading components and supported compatibility imports.

Production callers should import the narrow component they consume. These
re-exports preserve the existing configuration, provider, validation-schema,
error, and text-comparison imports used by CLI callers and tests.
"""

from typing import Any

from gurubodh.proofreading.errors import ProofreadingError
from gurubodh.proofreading.settings import ProofreadingSettings
from gurubodh.proofreading.text_comparison import word_level_diff
from gurubodh.proofreading.validation import EDIT_LIST_SCHEMA

__all__ = [
    "EDIT_LIST_SCHEMA",
    "GeminiProofreader",
    "ProofreadingError",
    "ProofreadingSettings",
    "word_level_diff",
]


def __getattr__(name: str) -> Any:
    """Load the compatibility provider only when that legacy import is used."""
    if name == "GeminiProofreader":
        from gurubodh.proofreading.gemini import GeminiProofreader

        return GeminiProofreader
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
