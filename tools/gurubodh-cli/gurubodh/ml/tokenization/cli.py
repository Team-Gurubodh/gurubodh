"""Command-line interface for tokenizer comparison."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Iterable
from pathlib import Path

from gurubodh.ml.tokenization.compare import (
    DEFAULT_BGE_M3_MODEL,
    DEFAULT_SARVAM_MODEL,
    BgeM3TokenCounter,
    SarvamTokenCounter,
    TokenizerComparison,
    compare_text,
)


ProgressCallback = Callable[[str], None]


def add_compare_tokenizers_options(parser: argparse.ArgumentParser) -> None:
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source-file", type=Path, help="Single chapter .txt file to compare.")
    source_group.add_argument("--source-dir", type=Path, help="Directory containing chapter .txt files to compare.")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    parser.add_argument("--model-name", default=DEFAULT_BGE_M3_MODEL, help="Local tokenizer model name.")
    parser.add_argument("--model-revision", default=None, help="Optional Hugging Face model revision.")
    parser.add_argument("--local-files-only", action="store_true", help="Load the local tokenizer from cache only.")
    parser.add_argument("--sarvam-model", default=DEFAULT_SARVAM_MODEL, help="Sarvam chat completion model name.")
    parser.add_argument("--include-sarvam", action="store_true", help="Also count tokens through the Sarvam API.")
    parser.add_argument(
        "--approve-external-api",
        action="store_true",
        help="Confirm that private source text may be sent to the external Sarvam API.",
    )
    parser.add_argument("--chapter", action="append", dest="chapters", help="Single chapter .txt filename or stem to process.")
    parser.add_argument("--chapters", nargs="+", dest="chapter_list", help="Chapter .txt filenames or stems to process.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare tokenizer counts for Hindi/Indic .txt files.")
    add_compare_tokenizers_options(parser)
    return parser


def run_compare_tokenizers(args: argparse.Namespace, progress: ProgressCallback | None = None) -> list[TokenizerComparison]:
    if args.include_sarvam and not args.approve_external_api:
        raise ValueError("Sarvam comparison sends source text to an external API. Use --approve-external-api to confirm.")

    requested_chapters = set(args.chapters or [])
    requested_chapters.update(args.chapter_list or [])
    if args.source_file and requested_chapters:
        raise ValueError("--chapter and --chapters can only be used with --source-dir.")

    bge_counter = BgeM3TokenCounter(
        model_name=args.model_name,
        model_revision=args.model_revision,
        local_files_only=args.local_files_only,
        progress=progress,
    )
    sarvam_counter = SarvamTokenCounter(model_name=args.sarvam_model, progress=progress) if args.include_sarvam else None

    if progress:
        progress("Tokenizer comparison started")
        progress(f"BGE model: {args.model_name}")
        if args.source_file:
            progress(f"Source file: {args.source_file.resolve()}")
        else:
            progress(f"Source directory: {args.source_dir.resolve()}")
        if requested_chapters:
            progress(f"Chapter filter: {', '.join(sorted(requested_chapters))}")
        if args.local_files_only:
            progress("Tokenizer loading mode: local files only")
        if args.include_sarvam:
            progress(f"Sarvam model: {args.sarvam_model}")
            progress("External API approval received for Sarvam token comparison")

    sources = list(iter_sources(args.source_file, args.source_dir, requested_chapters))
    if progress:
        progress(f"Found {len(sources)} text {_plural(len(sources), 'file')}.")

    comparisons: list[TokenizerComparison] = []
    total_sources = len(sources)
    for index, source in enumerate(sources, 1):
        source_name, text = source
        if progress:
            progress(f"[{index}/{total_sources}] {source_name}: starting")
        comparisons.append(compare_text(source_name, text, bge_counter, sarvam_counter, progress=progress))
        if progress:
            progress(f"[{index}/{total_sources}] {source_name}: complete")
    if progress:
        progress("Tokenizer comparison complete")
    return comparisons


def iter_sources(source_file: Path | None, source_dir: Path | None, chapters: set[str] | None = None) -> Iterable[tuple[str, str]]:
    if source_file:
        path = source_file.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Source file not found: {path}")
        yield path.name, path.read_text(encoding="utf-8")
        return

    if not source_dir:
        raise ValueError("Either --source-file or --source-dir is required.")

    source_path = source_dir.resolve()
    if not source_path.is_dir():
        raise FileNotFoundError(f"Source directory not found: {source_path}")

    text_files = sorted(source_path.glob("*.txt"))
    if chapters:
        requested = {chapter if chapter.endswith(".txt") else f"{chapter}.txt" for chapter in chapters}
        text_files = [path for path in text_files if path.name in requested or path.stem in chapters]
        missing = sorted(requested - {path.name for path in text_files})
        if missing:
            raise FileNotFoundError(f"Requested chapter files not found in {source_path}: {', '.join(missing)}")

    if not text_files:
        raise FileNotFoundError(f"No .txt files found in {source_path}")

    for path in text_files:
        yield path.name, path.read_text(encoding="utf-8")


def format_json(comparisons: list[TokenizerComparison]) -> str:
    summary = summarize_comparisons(comparisons)
    payload = {
        "comparison_count": len(comparisons),
        "whitespace_removed_for_token_counting": True,
        "token_counting": {
            "bge_includes_special_tokens": False,
            "sarvam_source": "live-api-prompt-usage",
        },
        "summary": summary,
        "files": [comparison.to_dict() for comparison in comparisons],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def format_text(comparisons: list[TokenizerComparison]) -> str:
    lines = [
        "Tokenizer comparison",
        "Whitespace removed before token counting: yes",
        "",
    ]
    for comparison in comparisons:
        lines.extend(
            [
                comparison.source_name,
                f"  Words: {comparison.word_count}",
                f"  Characters: {comparison.original_char_count} original, {comparison.normalized_char_count} without whitespace",
                (
                    f"  {comparison.bge_model_name}: {comparison.bge_token_count} tokens"
                    f" ({_format_ratio(comparison.bge_tokens_per_word)} tokens/word,"
                    f" {_format_words(comparison.bge_words_for_700_tokens)} words per 700 tokens)"
                ),
            ]
        )
        if comparison.sarvam_model_name:
            lines.append(
                f"  {comparison.sarvam_model_name}: {comparison.sarvam_prompt_token_count} prompt tokens"
                f" ({_format_ratio(comparison.sarvam_tokens_per_word)} tokens/word,"
                f" {_format_words(comparison.sarvam_words_for_700_tokens)} words per 700 tokens)"
            )
        else:
            lines.append("  Sarvam: skipped")
        lines.append("")
    summary = summarize_comparisons(comparisons)
    lines.extend(
        [
            "Summary",
            f"  Total words: {summary['total_words']}",
            f"  {summary['bge']['model']}: {_format_ratio(summary['bge']['average_tokens_per_word'])} tokens/word",
            (
                f"  {summary['sarvam']['model']}: "
                f"{_format_ratio(summary['sarvam']['average_tokens_per_word'])} tokens/word"
            )
            if summary["sarvam"]
            else "  Sarvam: skipped",
        ]
    )
    return "\n".join(lines).rstrip()


def summarize_comparisons(comparisons: list[TokenizerComparison]) -> dict:
    total_words = sum(comparison.word_count for comparison in comparisons)
    total_bge_tokens = sum(comparison.bge_token_count for comparison in comparisons)
    sarvam_comparisons = [
        comparison for comparison in comparisons if comparison.sarvam_prompt_token_count is not None
    ]
    total_sarvam_tokens = sum(comparison.sarvam_prompt_token_count or 0 for comparison in sarvam_comparisons)
    sarvam_words = sum(comparison.word_count for comparison in sarvam_comparisons)

    return {
        "total_words": total_words,
        "bge": {
            "model": comparisons[0].bge_model_name if comparisons else DEFAULT_BGE_M3_MODEL,
            "total_tokens": total_bge_tokens,
            "average_tokens_per_word": _safe_ratio(total_bge_tokens, total_words),
        },
        "sarvam": {
            "model": sarvam_comparisons[0].sarvam_model_name,
            "total_prompt_tokens": total_sarvam_tokens,
            "average_tokens_per_word": _safe_ratio(total_sarvam_tokens, sarvam_words),
        }
        if sarvam_comparisons
        else None,
    }


def _safe_ratio(tokens: int, words: int) -> float | None:
    if words == 0:
        return None
    return tokens / words


def _format_ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _format_words(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0f}"


def _plural(count: int, singular: str) -> str:
    return singular if count == 1 else f"{singular}s"
