"""Validation helpers for semantic chunking artifacts."""

from __future__ import annotations

from gurubodh.ml.semantic_chunking.models import ChunkedDocument, whitespace_insensitive_sha256


def validate_document_for_source(source_text: str, document: ChunkedDocument) -> None:
    """Validate spans and whitespace-insensitive source/chunk checksums."""
    concatenated = "".join(chunk.text for chunk in sorted(document.chunks, key=lambda chunk: chunk.index))
    source_checksum = whitespace_insensitive_sha256(source_text)
    chunk_checksum = whitespace_insensitive_sha256(concatenated)
    if source_checksum != chunk_checksum:
        raise ValueError(
            f"{document.source_name}: semantic chunk checksum mismatch. "
            f"source={source_checksum} chunks={chunk_checksum}"
        )

    last_end = 0
    for expected_index, chunk in enumerate(document.chunks, 1):
        if chunk.index != expected_index:
            raise ValueError(f"{document.source_name}: chunk indexes must be contiguous and ordered.")
        if not (0 <= chunk.start_char < chunk.end_char <= len(source_text)):
            raise ValueError(f"{document.source_name}: chunk {chunk.index} has an invalid source span.")
        if chunk.start_char < last_end:
            raise ValueError(f"{document.source_name}: chunk {chunk.index} overlaps the previous chunk.")
        if source_text[last_end : chunk.start_char].strip():
            raise ValueError(f"{document.source_name}: chunk {chunk.index} leaves non-whitespace source text uncovered.")
        if source_text[chunk.start_char : chunk.end_char] != chunk.text:
            raise ValueError(f"{document.source_name}: chunk {chunk.index} text does not match its source span.")
        last_end = chunk.end_char

    if source_text[last_end:].strip():
        raise ValueError(f"{document.source_name}: chunks leave non-whitespace source text uncovered.")
