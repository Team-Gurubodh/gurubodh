"""Provider-neutral comparison of source and corrected text."""

from __future__ import annotations

import difflib
import re
from typing import Any


def _tokens(text: str) -> list[str]:
    return re.findall(r"\s+|\S+", text, flags=re.UNICODE)


def word_level_diff(original: str, corrected: str) -> tuple[str, dict[str, Any]]:
    """Render a whitespace-preserving word diff without another model request."""
    original_tokens, corrected_tokens = _tokens(original), _tokens(corrected)
    matcher = difflib.SequenceMatcher(
        None, original_tokens, corrected_tokens, autojunk=False
    )
    rendered: list[str] = []
    changed_segments = 0
    removed_words = added_words = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            rendered.extend(original_tokens[i1:i2])
            continue
        changed_segments += 1
        removed = "".join(original_tokens[i1:i2])
        added = "".join(corrected_tokens[j1:j2])
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
