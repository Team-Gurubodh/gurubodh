"""Sentence splitting helpers for Hindi/Indic prose."""

from __future__ import annotations

from dataclasses import dataclass
import re


SENTENCE_BOUNDARY_RE = re.compile(r"[।!?\.]+(?:[\"'”’])?(?=\s+|$)")


@dataclass(frozen=True)
class SentenceSpan:
    """One sentence-like text unit and its exact source span."""

    text: str
    start_char: int
    end_char: int
    source_index: int


def _skip_leading_whitespace(text: str, start: int) -> int:
    while start < len(text) and text[start].isspace():
        start += 1
    return start


def _trim_trailing_whitespace(text: str, end: int) -> int:
    while end > 0 and text[end - 1].isspace():
        end -= 1
    return end


def _normalized_sentence(text: str) -> str:
    return " ".join(text.split())


def split_sentence_spans(text: str) -> list[SentenceSpan]:
    """Split text into sentence-like units while retaining source spans."""
    if not text or not text.strip():
        return []

    spans: list[SentenceSpan] = []
    cursor = 0

    for match in SENTENCE_BOUNDARY_RE.finditer(text):
        start = _skip_leading_whitespace(text, cursor)
        end = match.end()
        if start < end:
            sentence_text = _normalized_sentence(text[start:end])
            if sentence_text:
                spans.append(SentenceSpan(sentence_text, start, end, len(spans)))
        cursor = end

    start = _skip_leading_whitespace(text, cursor)
    end = _trim_trailing_whitespace(text, len(text))
    if start < end:
        sentence_text = _normalized_sentence(text[start:end])
        if sentence_text:
            spans.append(SentenceSpan(sentence_text, start, end, len(spans)))

    return spans


def split_sentences(text: str) -> list[str]:
    """Split text into sentence-like units while preserving paragraph meaning."""
    return [span.text for span in split_sentence_spans(text)]
