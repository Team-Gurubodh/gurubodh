"""File and folder helpers for semantic chunking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from gurubodh_utils.semantic_chunking.chunker import SemanticChunker
from gurubodh_utils.semantic_chunking.config import SemanticChunkConfig
from gurubodh_utils.semantic_chunking.models import ChunkedDocument


def iter_text_files(source_dir: Path) -> Iterable[Path]:
    yield from sorted(source_dir.glob("*.txt"))


def chunk_folder(
    source_dir: str | Path,
    output_dir: str | Path | None = None,
    config: SemanticChunkConfig | None = None,
) -> list[ChunkedDocument]:
    """Chunk every .txt file in a folder and write JSON/Markdown outputs."""
    source_path = Path(source_dir).resolve()
    output_path = Path(output_dir).resolve() if output_dir else source_path.parent / "semantic_chunks_bge_m3"
    output_path.mkdir(parents=True, exist_ok=True)

    text_files = list(iter_text_files(source_path))
    if not text_files:
        raise FileNotFoundError(f"No .txt files found in {source_path}")

    chunker = SemanticChunker(config)
    documents: list[ChunkedDocument] = []

    for text_file in text_files:
        text = text_file.read_text(encoding="utf-8")
        document = chunker.chunk_text(text, source_name=text_file.name)
        write_json(output_path / f"{text_file.stem}.chunks.json", document)
        write_markdown(output_path / f"{text_file.stem}.chunks.md", document)
        documents.append(document)

    write_summary(output_path / "summary.json", source_path, output_path, chunker.config, documents)
    return documents


def write_json(path: Path, document: ChunkedDocument) -> None:
    path.write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown(path: Path, document: ChunkedDocument) -> None:
    lines = [
        f"# Semantic chunks: {document.source_name or 'document'}",
        "",
        f"Total chunks: {document.chunk_count}",
        "",
    ]
    for chunk in document.chunks:
        lines.extend(
            [
                f"## Chunk {chunk.index}",
                "",
                f"- Characters: {chunk.char_count}",
                f"- Sentences: {chunk.sentence_count}",
                f"- Sentence range: {chunk.start_sentence}-{chunk.end_sentence}",
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
        "model": config.model_name,
        "source_dir": str(source_dir),
        "output_dir": str(output_dir),
        "window_size": config.window_size,
        "threshold_percentile": config.threshold_percentile,
        "min_chars": config.min_chars,
        "batch_size": config.batch_size,
        "files": [
            {
                "source_file": document.source_name,
                "chunk_count": document.chunk_count,
                "breakpoint_threshold": document.breakpoint_threshold,
            }
            for document in documents
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
