"""Issue #329: explicit pinned-model cache preparation and offline verification."""

from contextlib import redirect_stdout
from dataclasses import replace
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from gurubodh.cli import main
from gurubodh.errors import ConfigurationError
from gurubodh.job_components import ComponentCatalog
from gurubodh.model_cache import (
    MODEL_CACHE_CONTRACT_FILENAME,
    ModelCacheError,
    REQUIRED_RUNTIME_FILES,
    prepare_model_cache,
    resolve_model_profile,
    verify_model_cache,
)


CLI_ROOT = Path(__file__).parents[1]
PROFILE_ID = "bge-m3-semantic-window-v1"
MODEL = "BAAI/bge-m3"
REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
LFS_FILES = {"pytorch_model.bin", "sentencepiece.bpe.model", "tokenizer.json"}


def git_blob_digest(content):
    return hashlib.sha1(f"blob {len(content)}\0".encode("ascii") + content).hexdigest()


class ModelCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.cache = Path(temporary.name) / "cache"
        self.catalog = ComponentCatalog(CLI_ROOT)
        self.contents = {
            path: f"fixture artifact: {path}\n".encode("utf-8") for path in REQUIRED_RUNTIME_FILES
        }
        self.siblings = []
        for path, content in self.contents.items():
            if path in LFS_FILES:
                lfs = SimpleNamespace(sha256=hashlib.sha256(content).hexdigest())
                blob_id = "a" * 40
            else:
                lfs = None
                blob_id = git_blob_digest(content)
            self.siblings.append(
                SimpleNamespace(rfilename=path, size=len(content), blob_id=blob_id, lfs=lfs)
            )
        self.info = SimpleNamespace(sha=REVISION, siblings=self.siblings)
        self.environment = patch.dict(os.environ, {"GURUBODH_MODEL_CACHE_DIR": str(self.cache)}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def snapshot_dir(self):
        return self.cache / "models--BAAI--bge-m3" / "snapshots" / REVISION

    def fake_download(self, **kwargs):
        filename = kwargs["filename"]
        content = self.contents[filename]
        sibling = next(value for value in self.siblings if value.rfilename == filename)
        digest = sibling.lfs.sha256 if sibling.lfs else sibling.blob_id
        blob = self.cache / "models--BAAI--bge-m3" / "blobs" / digest
        blob.parent.mkdir(parents=True, exist_ok=True)
        blob.write_bytes(content)
        destination = self.snapshot_dir() / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.unlink(missing_ok=True)
        destination.symlink_to(os.path.relpath(blob, destination.parent))
        return str(destination)

    def prepare(self, *, info=None, downloader=None, progress=None):
        messages = [] if progress is None else progress
        with patch("huggingface_hub.HfApi") as api, \
             patch("huggingface_hub.hf_hub_download", side_effect=downloader or self.fake_download) as download, \
             patch("gurubodh.model_cache._run_embedding_smoke") as smoke:
            api.return_value.model_info.return_value = self.info if info is None else info
            prepare_model_cache(self.catalog, PROFILE_ID, progress=messages.append)
        return messages, download, smoke

    def test_prepare_reports_exact_plan_before_downloading_only_allowlisted_files(self):
        events = []

        def download(**kwargs):
            events.append(f"download:{kwargs['filename']}")
            return self.fake_download(**kwargs)

        messages, calls, smoke = self.prepare(downloader=download, progress=events)
        total = sum(len(content) for content in self.contents.values())
        first_download = next(index for index, value in enumerate(events) if value.startswith("download:"))
        report = "\n".join(events[:first_download])
        self.assertIn(f"Model: {MODEL}", report)
        self.assertIn(f"Revision: {REVISION}", report)
        self.assertIn("Embedding device: cpu", report)
        self.assertIn(f"Total required artifact bytes: {total}", report)
        self.assertIn(f"Remaining download bytes: {total}", report)
        self.assertEqual(
            [call.kwargs["filename"] for call in calls.call_args_list], list(REQUIRED_RUNTIME_FILES)
        )
        self.assertTrue(all(call.kwargs["force_download"] for call in calls.call_args_list))
        self.assertNotIn("safetensors", " ".join(REQUIRED_RUNTIME_FILES))
        self.assertNotIn("onnx", " ".join(REQUIRED_RUNTIME_FILES))
        self.assertEqual(smoke.call_count, 1)
        contract = json.loads((self.snapshot_dir() / MODEL_CACHE_CONTRACT_FILENAME).read_text())
        self.assertEqual([item["path"] for item in contract["artifacts"]], list(REQUIRED_RUNTIME_FILES))
        self.assertEqual(contract["total_artifact_bytes"], total)
        self.assertIn("Model cache is ready", "\n".join(messages))

    def test_maintained_profile_uses_cpu_for_prepare_and_verify_without_cuda_masking(self):
        profile = resolve_model_profile(self.catalog, PROFILE_ID)
        self.assertEqual(profile.config.device, "cpu")
        model = SimpleNamespace(encode=lambda texts, **kwargs: [[0.5, 0.5] for _ in texts])
        constructor = Mock(return_value=model)
        with patch.dict(sys.modules, {"sentence_transformers": SimpleNamespace(SentenceTransformer=constructor)}), \
             patch("huggingface_hub.HfApi") as api, \
             patch("huggingface_hub.hf_hub_download", side_effect=self.fake_download):
            api.return_value.model_info.return_value = self.info
            for command in ("prepare", "verify"):
                with self.subTest(command=command):
                    constructor.reset_mock()
                    stdout = StringIO()
                    with redirect_stdout(stdout):
                        main(["models", command, "--profile", PROFILE_ID, "--project-root", str(CLI_ROOT)])
                    constructor.assert_called_once_with(
                        MODEL, cache_folder=str(self.cache.resolve()), local_files_only=True,
                        device="cpu", revision=REVISION,
                    )
                    output = stdout.getvalue()
                    self.assertIn("Embedding device: cpu", output)
                    self.assertLess(output.index("Embedding device: cpu"),
                                    output.index("Offline embedding smoke check succeeded."))
                    self.assertNotIn("CUDA_VISIBLE_DEVICES", os.environ)

    def test_prepare_reuses_complete_cache_and_repairs_only_damaged_content(self):
        self.prepare()
        messages, calls, _ = self.prepare()
        self.assertEqual(calls.call_count, 0)
        self.assertIn("Remaining download bytes: 0", "\n".join(messages))

        damaged = "tokenizer.json"
        (self.snapshot_dir() / damaged).write_bytes(b"damaged")
        unrelated = self.cache / "models--other--model" / "blobs" / "keep"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text("unrelated")
        messages, calls, _ = self.prepare()
        self.assertEqual([call.kwargs["filename"] for call in calls.call_args_list], [damaged])
        self.assertTrue(calls.call_args.kwargs["force_download"])
        self.assertIn(f"Remaining download bytes: {len(self.contents[damaged])}", "\n".join(messages))
        self.assertEqual(unrelated.read_text(), "unrelated")

    def test_custom_null_device_is_reported_as_auto(self):
        profile = resolve_model_profile(self.catalog, PROFILE_ID)
        profile = replace(profile, config=replace(profile.config, device=None))
        with patch("gurubodh.model_cache.resolve_model_profile", return_value=profile):
            messages, _, _ = self.prepare()
            self.assertIn("Embedding device: auto", messages)
            self.assertNotIn("Embedding device: cpu", messages)
            messages = []
            with patch("gurubodh.model_cache._run_embedding_smoke"):
                verify_model_cache(self.catalog, PROFILE_ID, progress=messages.append)
            self.assertIn("Embedding device: auto", messages)
            self.assertNotIn("Embedding device: cpu", messages)

    def test_prepare_relinks_valid_blob_without_counting_or_downloading_its_content(self):
        artifact = self.siblings[0]
        content = self.contents[artifact.rfilename]
        blob = self.cache / "models--BAAI--bge-m3" / "blobs" / artifact.blob_id
        blob.parent.mkdir(parents=True)
        blob.write_bytes(content)
        messages, calls, _ = self.prepare()
        relink = next(call for call in calls.call_args_list if call.kwargs["filename"] == artifact.rfilename)
        self.assertFalse(relink.kwargs["force_download"])
        expected_remaining = sum(map(len, self.contents.values())) - len(content)
        self.assertIn(f"Remaining download bytes: {expected_remaining}", "\n".join(messages))

    def test_missing_upstream_file_fails_without_download_or_fallback(self):
        missing = REQUIRED_RUNTIME_FILES[-1]
        info = SimpleNamespace(
            sha=REVISION,
            siblings=[sibling for sibling in self.siblings if sibling.rfilename != missing],
        )
        with patch("huggingface_hub.HfApi") as api, \
             patch("huggingface_hub.hf_hub_download") as download:
            api.return_value.model_info.return_value = info
            with self.assertRaisesRegex(ModelCacheError, "missing required runtime files") as raised:
                prepare_model_cache(self.catalog, PROFILE_ID, progress=lambda message: None)
        self.assertIn("no whole-repository fallback", str(raised.exception))
        download.assert_not_called()
        self.assertFalse((self.snapshot_dir() / MODEL_CACHE_CONTRACT_FILENAME).exists())

    def test_interrupted_download_never_writes_contract_or_reports_readiness(self):
        calls = 0

        def interrupted(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise ConnectionError("interrupted")
            return self.fake_download(**kwargs)

        messages = []
        with patch("huggingface_hub.HfApi") as api, \
             patch("huggingface_hub.hf_hub_download", side_effect=interrupted):
            api.return_value.model_info.return_value = self.info
            with self.assertRaisesRegex(ModelCacheError, "cache is not ready"):
                prepare_model_cache(self.catalog, PROFILE_ID, progress=messages.append)
        self.assertFalse((self.snapshot_dir() / MODEL_CACHE_CONTRACT_FILENAME).exists())
        self.assertNotIn("ready for profile", "\n".join(messages))

    def test_verify_is_network_free_and_uses_production_embedding_helper(self):
        self.prepare()
        helper = SimpleNamespace(encode_texts=lambda texts, **kwargs: [[0.5, 0.5]])
        messages = []
        with patch("huggingface_hub.HfApi", side_effect=AssertionError("network metadata forbidden")), \
             patch("huggingface_hub.hf_hub_download", side_effect=AssertionError("download forbidden")), \
             patch("socket.socket", side_effect=AssertionError("network forbidden")), \
             patch("gurubodh.model_cache.SentenceTransformerEmbeddingHelper", return_value=helper) as embedding:
            verify_model_cache(self.catalog, PROFILE_ID, progress=messages.append)
        self.assertTrue(embedding.call_args.kwargs["local_files_only"])
        self.assertEqual(embedding.call_args.kwargs["model_revision"], REVISION)
        self.assertEqual(embedding.call_args.kwargs["device"], "cpu")
        self.assertIn("Offline embedding smoke check succeeded", "\n".join(messages))
        self.assertIn("Model cache is ready", "\n".join(messages))

    def test_verify_rejects_missing_damaged_and_unloadable_caches_with_guidance(self):
        with self.assertRaisesRegex(ModelCacheError, "models prepare"):
            verify_model_cache(self.catalog, PROFILE_ID, progress=lambda message: None)

        self.prepare()
        (self.snapshot_dir() / "config.json").write_bytes(b"damaged")
        with self.assertRaisesRegex(ModelCacheError, "missing or damaged.*models prepare"):
            verify_model_cache(self.catalog, PROFILE_ID, progress=lambda message: None)

        self.prepare()
        with patch(
            "gurubodh.model_cache.SentenceTransformerEmbeddingHelper.encode_texts",
            side_effect=OSError("unloadable"),
        ):
            with self.assertRaisesRegex(ModelCacheError, "offline embedding smoke check.*models prepare"):
                verify_model_cache(self.catalog, PROFILE_ID, progress=lambda message: None)

    def test_unknown_unsupported_and_invalid_pin_profiles_are_actionable(self):
        with self.assertRaisesRegex(ConfigurationError, "resource is missing"):
            resolve_model_profile(self.catalog, "unknown-profile-v1")

        with tempfile.TemporaryDirectory() as directory:
            resources = Path(directory)
            source = json.loads(
                (CLI_ROOT / f"config/job-components/profiles/chunking/{PROFILE_ID}.json").read_text()
            )
            profile_dir = resources / "config/job-components/profiles/chunking"
            profile_dir.mkdir(parents=True)

            source["chunking"]["local_files_only"] = False
            (profile_dir / f"{PROFILE_ID}.json").write_text(json.dumps(source))
            with self.assertRaisesRegex(ConfigurationError, "local_files_only must be true"):
                resolve_model_profile(ComponentCatalog(resources, resources), PROFILE_ID)

            source["chunking"]["local_files_only"] = True
            source["chunking"]["model_revision"] = "latest"
            (profile_dir / f"{PROFILE_ID}.json").write_text(json.dumps(source))
            with self.assertRaisesRegex(ConfigurationError, "model_revision"):
                resolve_model_profile(ComponentCatalog(resources, resources), PROFILE_ID)

    def test_cli_help_and_dispatch_expose_both_model_commands(self):
        for command in ("prepare", "verify"):
            stdout = StringIO()
            with redirect_stdout(stdout), self.assertRaises(SystemExit) as caught:
                main(["models", command, "--help"])
            self.assertEqual(caught.exception.code, 0)
            help_text = " ".join(stdout.getvalue().split())
            self.assertIn("--profile", help_text)
            self.assertIn("--project-root", help_text)

        for command, target in (
            ("prepare", "gurubodh.cli.prepare_model_cache"),
            ("verify", "gurubodh.cli.verify_model_cache"),
        ):
            with patch(target) as runner:
                self.assertIsNone(
                    main(["models", command, "--profile", PROFILE_ID, "--project-root", str(CLI_ROOT)])
                )
            self.assertEqual(runner.call_args.args[1], PROFILE_ID)


if __name__ == "__main__":
    unittest.main()
