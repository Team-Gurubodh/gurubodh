"""Sentence splitting helpers for Hindi/Indic prose."""

from __future__ import annotations

import re


SENTENCE_END_RE = re.compile(r"(?<=[।!?\.])\s+")
PARAGRAPH_RE = re.compile(r"\n\s*\n+")


def split_sentences(text: str) -> list[str]:
    """Split text into sentence-like units while preserving paragraph meaning."""
    text = text.replace("\ufeff", "").strip()
    if not text:
        return []

    sentences: list[str] = []
    for paragraph in PARAGRAPH_RE.split(text):
        paragraph = " ".join(line.strip() for line in paragraph.splitlines() if line.strip())
        if not paragraph:
            continue
        parts = [part.strip() for part in SENTENCE_END_RE.split(paragraph) if part.strip()]
        sentences.extend(parts)

    return sentences
