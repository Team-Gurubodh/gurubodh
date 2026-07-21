"""File and folder helpers for semantic chunking."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Iterable

from gurubodh.ml.semantic_chunking.config import SemanticChunkConfig
from gurubodh.ml.semantic_chunking.models import ChunkedDocument, whitespace_insensitive_sha256
from gurubodh.ml.semantic_chunking.segmenter import ParagraphSegmenter, SemanticChunkingParagraphSegmenter


DEFAULT_OUTPUT_SUBDIR = "semantic_chunks_bge_m3"
ProgressCallback = Callable[[str], None]


def iter_text_files(source_dir: Path) -> Iterable[Path]:
    yield from sorted(source_dir.glob("*.txt"))


def chunk_folder(
    source_dir: str | Path,
    output_dir: str | Path | None = None,
    config: SemanticChunkConfig | None = None,
    segmenter: ParagraphSegmenter | None = None,
    chapters: set[str] | None = None,
    overwrite: bool = False,
    progress: ProgressCallback | None = None,
) -> list[ChunkedDocument]:
    """Chunk every .txt file in a folder and write JSON/Markdown outputs."""
    source_path = Path(source_dir).resolve()
    output_path = resolve_output_dir(source_path, output_dir)
    ensure_output_available(output_path, overwrite=overwrite)

    text_files = list(iter_text_files(source_path))
    if chapters:
        requested = {chapter if chapter.endswith(".txt") else f"{chapter}.txt" for chapter in chapters}
        text_files = [path for path in text_files if path.name in requested or path.stem in chapters]
        missing = sorted(requested - {path.name for path in text_files})
        if missing:
            raise FileNotFoundError(f"Requested chapter files not found in {source_path}: {', '.join(missing)}")
    if not text_files:
        raise FileNotFoundError(f"No .txt files found in {source_path}")

    config = config or SemanticChunkConfig()
    segmenter = segmenter or SemanticChunkingParagraphSegmenter(config, progress=progress)
    documents: list[ChunkedDocument] = []
    output_path.mkdir(parents=True, exist_ok=True)
    total_files = len(text_files)
    _emit_progress(progress, f"Found {total_files} chapter text {_plural(total_files, 'file')}.")

    for position, text_file in enumerate(text_files, 1):
        prefix = f"[{position}/{total_files}] {text_file.name}:"
        _emit_progress(progress, f"{prefix} reading source text")
        text = text_file.read_text(encoding="utf-8")
        _emit_progress(progress, f"{prefix} segmenting {len(text)} characters")
        document = segmenter.segment(text, source_name=text_file.name)
        _emit_progress(progress, f"{prefix} validating chunks")
        validate_document_for_source(text, document)
        write_json(output_path / f"{text_file.stem}.chunks.json", document)
        write_markdown(output_path / f"{text_file.stem}.chunks.md", document)
        _emit_progress(progress, f"{prefix} wrote {document.chunk_count} {_plural(document.chunk_count, 'chunk')}")
        documents.append(document)

    _emit_progress(progress, "Writing summary.json")
    write_summary(output_path / "summary.json", source_path, output_path, config, documents)
    chunk_count = sum(document.chunk_count for document in documents)
    _emit_progress(
        progress,
        f"Semantic chunking complete: {total_files} {_plural(total_files, 'file')}, "
        f"{chunk_count} {_plural(chunk_count, 'chunk')}",
    )
    return documents


def _emit_progress(progress: ProgressCallback | None, message: str) -> None:
    if progress:
        progress(message)


def _plural(count: int, singular: str) -> str:
    return singular if count == 1 else f"{singular}s"


def resolve_output_dir(source_dir: Path, output_dir: str | Path | None) -> Path:
    if output_dir:
        return Path(output_dir).resolve() / DEFAULT_OUTPUT_SUBDIR
    return source_dir.parent / DEFAULT_OUTPUT_SUBDIR


def ensure_output_available(output_dir: Path, overwrite: bool) -> None:
    if not output_dir.exists():
        return
    if any(output_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"Semantic chunk output already exists at {output_dir}. Use --overwrite to replace it.")


def write_json(path: Path, document: ChunkedDocument) -> None:
    path.write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown(path: Path, document: ChunkedDocument) -> None:
    lines = [
        f"# Semantic chunks: {document.source_name or 'document'}",
        "",
        f"Total chunks: {document.chunk_count}",
        f"Estimated embedding tokens: {document.estimated_embedding_token_count}",
        "",
    ]
    for chunk in document.chunks:
        lines.extend(
            [
                f"## Chunk {chunk.index}",
                "",
                f"- Characters: {chunk.char_count}",
                f"- Sentences: {chunk.sentence_count}",
                f"- Estimated embedding tokens: {chunk.estimated_embedding_token_count}",
                f"- Sentence range: {chunk.start_sentence}-{chunk.end_sentence}",
                f"- Character span: {chunk.start_char}-{chunk.end_char}",
                f"- Text checksum: {chunk.chunk_text_sha256}",
                "",
                chunk.text,
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_summary(
    path: Path,
    source_dir: Path,
    output_dir: Path,
    config: SemanticChunkConfig,
    documents: list[ChunkedDocument],
) -> None:
    payload = {
        "provider": config.provider,
        "model": config.model_name,
        "embedding_mode": config.embedding_mode,
        "embedding_dimension": config.embedding_dimension,
        "strategy_version": config.strategy_version,
        "source_dir": str(source_dir),
        "output_dir": str(output_dir),
        "window_size": config.window_size,
        "threshold_percentile": config.threshold_percentile,
        "min_chars": config.min_chars,
        "batch_size": config.batch_size,
        "normalize_embeddings": config.normalize_embeddings,
        "device": config.device,
        "files": [
            {
                "source_file": document.source_name,
                "chunk_count": document.chunk_count,
                "estimated_embedding_token_count": document.estimated_embedding_token_count,
                "breakpoint_threshold": document.breakpoint_threshold,
                "source_text_sha256": document.source_text_sha256,
                "concatenated_chunks_sha256": document.concatenated_chunks_sha256,
            }
            for document in documents
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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
