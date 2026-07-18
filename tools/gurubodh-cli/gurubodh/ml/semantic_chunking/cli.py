"""Command-line interface for semantic chunking."""

from __future__ import annotations

import argparse
from pathlib import Path

from gurubodh.ml.semantic_chunking.config import SemanticChunkConfig
from gurubodh.ml.semantic_chunking.file_io import chunk_folder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Semantic chunk Hindi/Indic .txt files.")
    parser.add_argument("--source-dir", type=Path, default=Path("source"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--model-name", default="BAAI/bge-m3")
    parser.add_argument("--window-size", type=int, default=3)
    parser.add_argument("--threshold-percentile", type=float, default=82.0)
    parser.add_argument("--min-chars", type=int, default=700)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", default=None, help='Examples: "cpu", "mps", "cuda".')
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = SemanticChunkConfig(
        model_name=args.model_name,
        threshold_percentile=args.threshold_percentile,
        min_chars=args.min_chars,
        window_size=args.window_size,
        batch_size=args.batch_size,
        device=args.device,
    )
    documents = chunk_folder(
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        config=config,
    )
    for document in documents:
        print(f"{document.source_name}: {document.chunk_count} chunks")

    output_dir = args.output_dir.resolve() if args.output_dir else args.source_dir.resolve().parent / "semantic_chunks_bge_m3"
    print(f"Wrote outputs to {output_dir}")


if __name__ == "__main__":
    main()
