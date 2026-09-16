"""Issue #330: advisory upstream checks for immutable model pins."""

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from gurubodh.cli import main
from gurubodh.job_components import ComponentCatalog
from gurubodh.model_cache import REQUIRED_RUNTIME_FILES
from gurubodh.model_updates import ModelUpdateCheckError, check_model_updates


CLI_ROOT = Path(__file__).parents[1]
PROFILE_ID = "bge-m3-semantic-window-v1"
MODEL = "BAAI/bge-m3"
PINNED = "5617a9f61b028005a4858fdac845db406aefb181"
UPSTREAM = "b" * 40
CHECKED_AT = datetime(2026, 9, 16, 8, 30, tzinfo=timezone.utc)


def sibling(path, content, *, complete=True):
    digest = hashlib.sha256(content).hexdigest()
    if path == "pytorch_model.bin":
        lfs = SimpleNamespace(sha256=digest if complete else None)
        blob_id = "f" * 40
    else:
        lfs = None
        blob_id = digest[:40] if complete else None
    return SimpleNamespace(
        rfilename=path,
        size=len(content) if complete else None,
        blob_id=blob_id,
        lfs=lfs,
    )


def commit(commit_id, day, title):
    return SimpleNamespace(
        commit_id=commit_id,
        created_at=datetime(2026, 9, day, 10, 0, tzinfo=timezone.utc),
        title=title,
    )


class ModelUpdateTests(unittest.TestCase):
    def setUp(self):
        self.catalog = ComponentCatalog(CLI_ROOT)
        self.base_content = {
            path: f"pinned: {path}\n".encode("utf-8") for path in REQUIRED_RUNTIME_FILES
        }
        self.base_content["README.md"] = b"model card\n"
        self.pinned_info = self.info(PINNED, self.base_content)
        self.config_documents = {
            "1_Pooling/config.json": {"word_embedding_dimension": 1024},
            "config.json": {"architectures": ["XLMRobertaModel"], "hidden_size": 1024},
            "sentence_bert_config.json": {"max_seq_length": 8192},
        }

    def info(self, revision, contents, *, card_data=True, incomplete=()):
        return SimpleNamespace(
            sha=revision,
            siblings=[
                sibling(path, content, complete=path not in incomplete)
                for path, content in sorted(contents.items())
            ],
            card_data={"license": "mit"} if card_data else None,
        )

    def fake_download(self, **kwargs):
        self.assertIn(kwargs["filename"], self.config_documents)
        destination = Path(kwargs["cache_dir"]) / kwargs["filename"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(self.config_documents[kwargs["filename"]]))
        return str(destination)

    def run_check(self, upstream_info, commits, *, pinned_info=None, downloader=None):
        messages = []
        pinned_info = self.pinned_info if pinned_info is None else pinned_info

        def model_info(model, *, revision, files_metadata):
            self.assertEqual(model, MODEL)
            self.assertTrue(files_metadata)
            if revision == "main":
                return upstream_info
            if revision == PINNED:
                return pinned_info
            self.fail(f"unexpected revision: {revision}")

        with patch.dict(os.environ, {}, clear=True), \
             patch("huggingface_hub.HfApi") as api_type, \
             patch(
                 "huggingface_hub.hf_hub_download",
                 side_effect=downloader or self.fake_download,
             ) as download:
            api = api_type.return_value
            api.model_info.side_effect = model_info
            api.list_repo_commits.return_value = commits
            check_model_updates(
                self.catalog,
                PROFILE_ID,
                progress=messages.append,
                checked_at=CHECKED_AT,
            )
        return "\n".join(messages), api, download

    def test_current_pin_reports_identity_dates_metadata_and_leaves_cache_unchanged(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        cache = Path(temporary.name) / "runtime-cache"
        cache.mkdir()
        sentinel = cache / "sentinel"
        sentinel.write_text("unchanged")
        profile_path = CLI_ROOT / f"config/job-components/profiles/chunking/{PROFILE_ID}.json"
        original_profile = profile_path.read_bytes()
        with patch.dict(os.environ, {"GURUBODH_MODEL_CACHE_DIR": str(cache)}, clear=True), \
             patch("huggingface_hub.HfApi") as api_type, \
             patch("huggingface_hub.hf_hub_download", side_effect=self.fake_download) as download, \
             patch(
                 "gurubodh.model_cache.SentenceTransformerEmbeddingHelper",
                 side_effect=AssertionError("model initialization forbidden"),
             ):
            api = api_type.return_value
            api.model_info.return_value = self.pinned_info
            api.list_repo_commits.return_value = [commit(PINNED, 10, "Pinned revision")]
            messages = []
            check_model_updates(
                self.catalog,
                PROFILE_ID,
                progress=messages.append,
                checked_at=CHECKED_AT,
            )
        report = "\n".join(messages)
        self.assertIn(f"Profile: {PROFILE_ID}", report)
        self.assertIn(f"Model: {MODEL}", report)
        self.assertIn(f"Pinned revision: {PINNED}", report)
        self.assertIn("Pinned commit date: 2026-09-10T10:00:00Z", report)
        self.assertIn("Checked at: 2026-09-16T08:30:00Z", report)
        self.assertIn("Status: current", report)
        self.assertIn("Architecture: XLMRobertaModel", report)
        self.assertIn("Embedding dimensions: 1024", report)
        self.assertIn("Context/token limit: 8192", report)
        self.assertIn("License: mit", report)
        self.assertIn("Required runtime artifact size:", report)
        self.assertIn("Model card: https://huggingface.co/BAAI/bge-m3", report)
        self.assertIn("the pin and cache are unchanged", report)
        self.assertEqual(
            report.splitlines()[-4:-1],
            [
                "Conclusion:",
                "  Status: current",
                "  Change summary: no newer upstream main revision was found.",
            ],
        )
        self.assertTrue(report.splitlines()[-1].startswith("  Advisory: "))
        self.assertEqual(sentinel.read_text(), "unchanged")
        self.assertEqual(list(cache.iterdir()), [sentinel])
        self.assertEqual(profile_path.read_bytes(), original_profile)
        self.assertEqual(
            {call.kwargs["filename"] for call in download.call_args_list},
            set(self.config_documents),
        )
        self.assertTrue(all("pytorch_model.bin" not in str(call) for call in download.call_args_list))
        self.assertTrue(all(Path(call.kwargs["cache_dir"]) != cache for call in download.call_args_list))

    def test_newer_runtime_files_are_classified_by_shared_required_artifact_contract(self):
        upstream_content = dict(self.base_content)
        for path in ("pytorch_model.bin", "tokenizer.json", "config.json"):
            upstream_content[path] += b"changed"
        upstream = self.info(UPSTREAM, upstream_content)
        report, api, _ = self.run_check(
            upstream,
            [commit(UPSTREAM, 16, "Runtime update"), commit(PINNED, 10, "Pinned")],
        )
        self.assertIn("Status: update available", report)
        self.assertIn("pin is an ancestor of upstream main (1 newer commit(s))", report)
        self.assertIn("Runtime weights changed: pytorch_model.bin", report)
        self.assertIn("Tokenizer changed: tokenizer.json", report)
        self.assertIn("Runtime configuration changed: config.json", report)
        self.assertIn("required runtime weights, tokenizer, configuration changed", report)
        self.assertIn(f"https://huggingface.co/{MODEL}/commit/{UPSTREAM}", report)
        self.assertLess(report.index("Relevant newer commits:"), report.index("Conclusion:"))
        self.assertIn("\nConclusion:\n  Status: update available\n  Change summary: ", report)
        api.list_repo_commits.assert_called_once_with(MODEL, revision=UPSTREAM, formatted=False)

    def test_documentation_only_revision_is_not_called_a_model_release(self):
        upstream_content = dict(self.base_content)
        upstream_content["README.md"] = b"revised model card\n"
        report, _, _ = self.run_check(
            self.info(UPSTREAM, upstream_content),
            [commit(UPSTREAM, 16, "Docs"), commit(PINNED, 10, "Pinned")],
        )
        self.assertIn("Documentation/metadata changed: README.md", report)
        self.assertIn("Runtime weights changed: none", report)
        self.assertIn("documentation/metadata-only repository changes", report)
        self.assertIn("this is not a new model release", report)

    def test_unrelated_artifacts_are_separate_from_runtime_and_documentation(self):
        upstream_content = dict(self.base_content)
        upstream_content["onnx/model.onnx"] = b"unrelated export"
        report, _, _ = self.run_check(
            self.info(UPSTREAM, upstream_content),
            [commit(UPSTREAM, 16, "Export"), commit(PINNED, 10, "Pinned")],
        )
        self.assertIn("Other non-runtime artifacts changed: onnx/model.onnx", report)
        self.assertIn("maintained required runtime files did not change", report)

    def test_incomplete_metadata_is_identified_without_guessing(self):
        upstream_content = dict(self.base_content)
        upstream_content["README.md"] = b"updated\n"
        upstream = self.info(
            UPSTREAM,
            upstream_content,
            card_data=False,
            incomplete=("config.json",),
        )
        self.config_documents["config.json"] = {"hidden_size": "unknown"}
        self.config_documents["1_Pooling/config.json"] = {"word_embedding_dimension": "unknown"}
        self.config_documents["sentence_bert_config.json"] = {"max_seq_length": "unknown"}
        report, _, _ = self.run_check(
            upstream,
            [commit(UPSTREAM, 16, "Incomplete"), commit(PINNED, 10, "Pinned")],
        )
        self.assertIn("Embedding dimensions: Unavailable", report)
        self.assertIn("Context/token limit: Unavailable", report)
        self.assertIn("License: Unavailable", report)
        self.assertIn("Required runtime artifact size: Unavailable", report)
        self.assertIn("Unclassified paths (incomplete metadata): config.json", report)
        self.assertIn("prevents a complete runtime-change classification", report)

    def test_missing_pin_and_divergent_history_are_unable_to_determine(self):
        upstream = self.info(UPSTREAM, self.base_content)
        with patch("huggingface_hub.HfApi") as api_type:
            api = api_type.return_value
            api.model_info.side_effect = [upstream, FileNotFoundError("missing")]
            with self.assertRaisesRegex(ModelUpdateCheckError, "(?s)unable to determine.*pinned revision"):
                check_model_updates(self.catalog, PROFILE_ID, checked_at=CHECKED_AT)

        with patch("huggingface_hub.HfApi") as api_type:
            api = api_type.return_value
            api.model_info.side_effect = [upstream, self.pinned_info]
            api.list_repo_commits.return_value = [
                commit(UPSTREAM, 16, "Upstream"),
                commit("c" * 40, 15, "Other history"),
            ]
            with self.assertRaisesRegex(ModelUpdateCheckError, "not an ancestor.*divergent"):
                check_model_updates(self.catalog, PROFILE_ID, checked_at=CHECKED_AT)

    def test_network_api_failure_exits_nonzero_and_never_reports_current(self):
        stderr = StringIO()
        stdout = StringIO()
        with patch("huggingface_hub.HfApi") as api_type, \
             redirect_stdout(stdout), redirect_stderr(stderr):
            api_type.return_value.model_info.side_effect = ConnectionError("offline")
            with self.assertRaises(SystemExit) as caught:
                main(
                    [
                        "models",
                        "check-updates",
                        "--profile",
                        PROFILE_ID,
                        "--project-root",
                        str(CLI_ROOT),
                    ]
                )
        self.assertNotEqual(caught.exception.code, 0)
        message = stderr.getvalue()
        self.assertIn("unable to determine", message)
        self.assertIn("Status: unable to check", message)
        self.assertIn("network access, authentication, and the Hub API", message)
        self.assertNotIn("Status: current", message)
        self.assertEqual(stdout.getvalue(), "")

    def test_cli_help_and_dispatch_expose_update_check(self):
        stdout = StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as caught:
            main(["models", "check-updates", "--help"])
        self.assertEqual(caught.exception.code, 0)
        help_text = " ".join(stdout.getvalue().split())
        self.assertIn("--profile", help_text)
        self.assertIn("metadata only", help_text)

        with patch("gurubodh.cli.check_model_updates") as runner:
            self.assertIsNone(
                main(
                    [
                        "models",
                        "check-updates",
                        "--profile",
                        PROFILE_ID,
                        "--project-root",
                        str(CLI_ROOT),
                    ]
                )
            )
        self.assertEqual(runner.call_args.args[1], PROFILE_ID)


if __name__ == "__main__":
    unittest.main()
