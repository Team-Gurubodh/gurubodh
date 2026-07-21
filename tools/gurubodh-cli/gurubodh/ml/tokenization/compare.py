"""Compare local BGE-M3 token counts with optional Sarvam API counts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from typing import Any


DEFAULT_BGE_M3_MODEL = "BAAI/bge-m3"
DEFAULT_SARVAM_MODEL = "sarvam-105b"
SARVAM_API_KEY_ENV_VAR = "SARVAM_API_KEY"
SARVAM_BASE_URL = "https://api.sarvam.ai/v1"
TOKENIZERS_PARALLELISM_ENV_VAR = "TOKENIZERS_PARALLELISM"
ProgressCallback = Callable[[str], None]


def normalize_for_token_counting(text: str) -> str:
    """Remove all Unicode whitespace before token counting."""
    return "".join(char for char in text if not char.isspace())


def word_count(text: str) -> int:
    """Return a simple whitespace-delimited word count from the original text."""
    return len(text.split())


def disable_tokenizer_parallelism_warning() -> None:
    """Default Hugging Face tokenizer parallelism off for CLI stability."""
    os.environ.setdefault(TOKENIZERS_PARALLELISM_ENV_VAR, "false")


def tokens_per_word(tokens: int | None, words: int) -> float | None:
    if tokens is None or words == 0:
        return None
    return tokens / words


def words_for_token_budget(tokens: int | None, words: int, token_budget: int = 700) -> float | None:
    ratio = tokens_per_word(tokens, words)
    if not ratio:
        return None
    return token_budget / ratio


@dataclass(frozen=True)
class TokenizerComparison:
    """Token count comparison for one source text."""

    source_name: str
    original_char_count: int
    normalized_char_count: int
    word_count: int
    bge_model_name: str
    bge_token_count: int
    sarvam_model_name: str | None = None
    sarvam_prompt_token_count: int | None = None

    @property
    def bge_tokens_per_word(self) -> float | None:
        return tokens_per_word(self.bge_token_count, self.word_count)

    @property
    def sarvam_tokens_per_word(self) -> float | None:
        return tokens_per_word(self.sarvam_prompt_token_count, self.word_count)

    @property
    def bge_words_for_700_tokens(self) -> float | None:
        return words_for_token_budget(self.bge_token_count, self.word_count)

    @property
    def sarvam_words_for_700_tokens(self) -> float | None:
        return words_for_token_budget(self.sarvam_prompt_token_count, self.word_count)

    def to_dict(self) -> dict:
        return {
            "source_name": self.source_name,
            "original_char_count": self.original_char_count,
            "normalized_char_count": self.normalized_char_count,
            "whitespace_removed_for_token_counting": True,
            "word_count": self.word_count,
            "bge": {
                "model": self.bge_model_name,
                "token_count": self.bge_token_count,
                "tokens_per_word": self.bge_tokens_per_word,
                "estimated_words_per_700_tokens": self.bge_words_for_700_tokens,
            },
            "sarvam": {
                "model": self.sarvam_model_name,
                "prompt_token_count": self.sarvam_prompt_token_count,
                "tokens_per_word": self.sarvam_tokens_per_word,
                "estimated_words_per_700_tokens": self.sarvam_words_for_700_tokens,
            }
            if self.sarvam_model_name
            else None,
        }


class BgeM3TokenCounter:
    """Lazy local tokenizer wrapper for BGE-M3 token counts."""

    def __init__(
        self,
        model_name: str = DEFAULT_BGE_M3_MODEL,
        model_revision: str | None = None,
        local_files_only: bool = False,
        tokenizer: Any | None = None,
        progress: ProgressCallback | None = None,
    ) -> None:
        self.model_name = model_name
        self.model_revision = model_revision
        self.local_files_only = local_files_only
        self._tokenizer = tokenizer
        self._progress = progress

    def count_tokens(self, text: str) -> int:
        tokenizer = self.tokenizer
        try:
            token_ids = tokenizer.encode(text, add_special_tokens=False)
        except TypeError:
            token_ids = tokenizer.encode(text)
        return len(token_ids)

    @property
    def tokenizer(self) -> Any:
        if self._tokenizer is None:
            self._tokenizer = self._load_tokenizer()
        return self._tokenizer

    def _load_tokenizer(self) -> Any:
        disable_tokenizer_parallelism_warning()
        self._emit_progress(f"Loading tokenizer {self.model_name}...")
        try:
            from transformers import AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "BGE-M3 token counting requires transformers. "
                "Install the Gurubodh CLI package dependencies before running compare-tokenizers."
            ) from exc

        kwargs: dict[str, Any] = {"local_files_only": self.local_files_only}
        if self.model_revision:
            kwargs["revision"] = self.model_revision
        tokenizer = AutoTokenizer.from_pretrained(self.model_name, **kwargs)
        self._emit_progress("Tokenizer ready.")
        return tokenizer

    def _emit_progress(self, message: str) -> None:
        if self._progress:
            self._progress(message)


class SarvamTokenCounter:
    """Sarvam token counter backed by the live OpenAI-compatible API."""

    def __init__(
        self,
        model_name: str = DEFAULT_SARVAM_MODEL,
        api_key: str | None = None,
        client: Any | None = None,
        progress: ProgressCallback | None = None,
    ) -> None:
        self.model_name = model_name
        self.api_key = api_key
        self._client = client
        self._progress = progress

    def count_tokens(self, text: str) -> int:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": text}],
            max_tokens=1,
        )
        return int(response.usage.prompt_tokens)

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self._load_client()
        return self._client

    def _load_client(self) -> Any:
        self._emit_progress(f"Initializing Sarvam API client for {self.model_name}...")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "Sarvam token counting requires the openai Python package. "
                "Install the Gurubodh CLI package dependencies before running Sarvam comparison."
            ) from exc

        api_key = self.api_key or os.environ.get(SARVAM_API_KEY_ENV_VAR)
        if not api_key:
            raise RuntimeError(f"Set {SARVAM_API_KEY_ENV_VAR} before running Sarvam token comparison.")
        client = OpenAI(base_url=SARVAM_BASE_URL, api_key=api_key)
        self._emit_progress("Sarvam API client ready.")
        return client

    def _emit_progress(self, message: str) -> None:
        if self._progress:
            self._progress(message)


def compare_text(
    source_name: str,
    text: str,
    bge_counter: BgeM3TokenCounter,
    sarvam_counter: SarvamTokenCounter | None = None,
    progress: ProgressCallback | None = None,
) -> TokenizerComparison:
    normalized_text = normalize_for_token_counting(text)
    if progress:
        progress(
            f"{source_name}: removed whitespace "
            f"({len(text)} original chars -> {len(normalized_text)} chars)"
        )
        progress(f"{source_name}: counting {bge_counter.model_name} tokens")
    bge_tokens = bge_counter.count_tokens(normalized_text) if normalized_text else 0
    if progress:
        progress(f"{source_name}: {bge_counter.model_name} tokens counted")
    if progress and sarvam_counter:
        progress(f"{source_name}: requesting {sarvam_counter.model_name} prompt token count")
    sarvam_tokens = sarvam_counter.count_tokens(normalized_text) if sarvam_counter and normalized_text else None
    if progress and sarvam_counter:
        progress(f"{source_name}: {sarvam_counter.model_name} prompt tokens counted")

    return TokenizerComparison(
        source_name=source_name,
        original_char_count=len(text),
        normalized_char_count=len(normalized_text),
        word_count=word_count(text),
        bge_model_name=bge_counter.model_name,
        bge_token_count=bge_tokens,
        sarvam_model_name=sarvam_counter.model_name if sarvam_counter else None,
        sarvam_prompt_token_count=sarvam_tokens,
    )
