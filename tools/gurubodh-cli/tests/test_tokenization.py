import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gurubodh.ml.tokenization.cli import build_parser, format_json, format_text, iter_sources, run_compare_tokenizers
from gurubodh.ml.tokenization.compare import (
    BgeM3TokenCounter,
    SarvamTokenCounter,
    compare_text,
    disable_tokenizer_parallelism_warning,
    normalize_for_token_counting,
    word_count,
)


class FakeTokenizer:
    def __init__(self):
        self.calls = []

    def encode(self, text, add_special_tokens=False):
        self.calls.append({"text": text, "add_special_tokens": add_special_tokens})
        return list(text)


class FakeSarvamCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(usage=SimpleNamespace(prompt_tokens=42))


class FakeSarvamClient:
    def __init__(self):
        self.completions = FakeSarvamCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


class FakeBgeCounter:
    def __init__(self, model_name, model_revision=None, local_files_only=False, progress=None):
        self.model_name = model_name
        self.model_revision = model_revision
        self.local_files_only = local_files_only
        self.progress = progress

    def count_tokens(self, text):
        if self.progress:
            self.progress("Fake tokenizer ready.")
        return len(text)


class TokenizationTests(unittest.TestCase):
    def test_normalize_for_token_counting_removes_all_whitespace(self):
        self.assertEqual(normalize_for_token_counting(" अ\tआ\nइ  "), "अआइ")

    def test_word_count_uses_original_text(self):
        self.assertEqual(word_count("पहला शब्द\nदूसरा शब्द"), 4)

    def test_tokenizer_parallelism_defaults_to_false_without_overriding_user_value(self):
        with patch.dict(os.environ, {}, clear=True):
            disable_tokenizer_parallelism_warning()
            self.assertEqual(os.environ["TOKENIZERS_PARALLELISM"], "false")

        with patch.dict(os.environ, {"TOKENIZERS_PARALLELISM": "true"}, clear=True):
            disable_tokenizer_parallelism_warning()
            self.assertEqual(os.environ["TOKENIZERS_PARALLELISM"], "true")

    def test_compare_text_counts_tokens_on_whitespace_stripped_text(self):
        tokenizer = FakeTokenizer()
        bge_counter = BgeM3TokenCounter(tokenizer=tokenizer)
        comparison = compare_text("chapter.txt", "पहला शब्द\nदूसरा शब्द", bge_counter)

        self.assertEqual(tokenizer.calls[0]["text"], "पहलाशब्ददूसराशब्द")
        self.assertFalse(tokenizer.calls[0]["add_special_tokens"])
        self.assertEqual(comparison.word_count, 4)
        self.assertEqual(comparison.bge_token_count, len("पहलाशब्ददूसराशब्द"))
        self.assertAlmostEqual(comparison.bge_tokens_per_word, len("पहलाशब्ददूसराशब्द") / 4)

    def test_sarvam_counter_uses_prompt_usage_without_network_when_client_injected(self):
        client = FakeSarvamClient()
        counter = SarvamTokenCounter(model_name="sarvam-105b", client=client)

        self.assertEqual(counter.count_tokens("परीक्षण"), 42)
        self.assertEqual(client.completions.calls[0]["model"], "sarvam-105b")
        self.assertEqual(client.completions.calls[0]["messages"][0]["content"], "परीक्षण")
        self.assertEqual(client.completions.calls[0]["max_tokens"], 1)

    def test_iter_sources_filters_directory_by_chapter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "001.txt").write_text("एक", encoding="utf-8")
            (root / "002.txt").write_text("दो", encoding="utf-8")

            sources = list(iter_sources(None, root, {"002"}))

        self.assertEqual(sources, [("002.txt", "दो")])

    def test_run_compare_tokenizers_refuses_sarvam_without_external_approval(self):
        parser = build_parser()
        args = parser.parse_args(["--source-file", "/tmp/chapter.txt", "--include-sarvam"])

        with self.assertRaisesRegex(ValueError, "external API"):
            run_compare_tokenizers(args)

    def test_run_compare_tokenizers_reports_progress(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_file = Path(temp_dir) / "001.txt"
            source_file.write_text("पहला शब्द", encoding="utf-8")
            parser = build_parser()
            args = parser.parse_args(["--source-file", str(source_file), "--local-files-only"])
            events = []

            with patch("gurubodh.ml.tokenization.cli.BgeM3TokenCounter", FakeBgeCounter):
                comparisons = run_compare_tokenizers(args, progress=events.append)

        self.assertEqual(len(comparisons), 1)
        self.assertIn("Tokenizer comparison started", events)
        self.assertIn(f"Source file: {source_file.resolve()}", events)
        self.assertIn("Tokenizer loading mode: local files only", events)
        self.assertIn("Found 1 text file.", events)
        self.assertIn("[1/1] 001.txt: starting", events)
        self.assertIn("001.txt: counting BAAI/bge-m3 tokens", events)
        self.assertIn("[1/1] 001.txt: complete", events)
        self.assertIn("Tokenizer comparison complete", events)

    def test_format_json_includes_machine_readable_ratios(self):
        comparison = compare_text("chapter.txt", "पहला दूसरा", BgeM3TokenCounter(tokenizer=FakeTokenizer()))
        payload = json.loads(format_json([comparison]))

        self.assertEqual(payload["comparison_count"], 1)
        self.assertTrue(payload["whitespace_removed_for_token_counting"])
        self.assertEqual(payload["summary"]["total_words"], 2)
        self.assertEqual(payload["summary"]["bge"]["model"], "BAAI/bge-m3")
        self.assertEqual(payload["summary"]["bge"]["average_tokens_per_word"], len("पहलादूसरा") / 2)
        self.assertEqual(payload["files"][0]["source_name"], "chapter.txt")
        self.assertEqual(payload["files"][0]["bge"]["model"], "BAAI/bge-m3")
        self.assertIsNone(payload["files"][0]["sarvam"])

    def test_format_text_includes_summary_line(self):
        comparison = compare_text("chapter.txt", "पहला दूसरा", BgeM3TokenCounter(tokenizer=FakeTokenizer()))

        output = format_text([comparison])

        self.assertIn("Summary", output)
        self.assertIn("Total words: 2", output)
        self.assertIn("BAAI/bge-m3: 4.50 tokens/word", output)
        self.assertIn("Sarvam: skipped", output)


if __name__ == "__main__":
    unittest.main()
