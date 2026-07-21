"""Command-line interface for semantic chunking."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from gurubodh.ml.semantic_chunking.config import (
    MODEL_CACHE_ENV_VAR,
    ModelCacheConfigError,
    SemanticChunkConfig,
    SemanticChunkConfigError,
)
from gurubodh.ml.semantic_chunking.file_io import chunk_folder, resolve_output_dir


def add_generate_chunks_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-dir", type=Path, required=True, help="Directory containing prepared chapter .txt files.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Parent directory for semantic chunk POC output.")
    parser.add_argument("--model-name", default="BAAI/bge-m3")
    parser.add_argument("--model-revision", default=None)
    parser.add_argument("--window-size", type=int, default=3)
    parser.add_argument("--threshold-percentile", type=float, default=80.0)
    parser.add_argument("--min-chars", type=int, default=650)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument(
        "--normalize-embeddings",
        dest="normalize_embeddings",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--device", choices=["cpu", "mps", "cuda"], default=None)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--chapter", action="append", dest="chapters", help="Single chapter .txt filename or stem to process.")
    parser.add_argument("--chapters", nargs="+", dest="chapter_list", help="Chapter .txt filenames or stems to process.")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing semantic chunk output files.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Semantic chunk Hindi/Indic .txt files.")
    add_generate_chunks_options(parser)
    return parser


def build_config_from_args(args: argparse.Namespace) -> SemanticChunkConfig:
    return SemanticChunkConfig.from_env(
        model_name=args.model_name,
        model_revision=args.model_revision,
        threshold_percentile=args.threshold_percentile,
        min_chars=args.min_chars,
        window_size=args.window_size,
        batch_size=args.batch_size,
        normalize_embeddings=args.normalize_embeddings,
        device=args.device,
        local_files_only=args.local_files_only,
    )


def run_generate_chunks(args: argparse.Namespace, progress: Callable[[str], None] | None = None) -> list:
    config = build_config_from_args(args)
    cache_dir = config.resolved_cache_dir()
    output_dir = resolve_output_dir(args.source_dir.resolve(), args.output_dir)
    chapters = set(args.chapters or [])
    chapters.update(args.chapter_list or [])
    if progress:
        progress("Semantic chunking started")
        progress(f"Source: {args.source_dir.resolve()}")
        progress(f"Output: {output_dir}")
        progress(f"Model: {config.model_name}")
        progress(f"Device: {config.device or 'auto'}")
        progress(f"Model cache: {cache_dir}")
    return chunk_folder(
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        config=config,
        chapters=chapters or None,
        overwrite=args.overwrite,
        progress=progress,
    )


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        documents = run_generate_chunks(args, progress=print)
    except (FileExistsError, FileNotFoundError, ModelCacheConfigError, SemanticChunkConfigError, ValueError) as exc:
        parser.error(str(exc))

    for document in documents:
        print(f"{document.source_name}: {document.chunk_count} chunks")

    output_dir = resolve_output_dir(args.source_dir.resolve(), args.output_dir)
    print(f"Wrote outputs to {output_dir}")
    print(f"Used model cache from {MODEL_CACHE_ENV_VAR}.")


if __name__ == "__main__":
    main()
