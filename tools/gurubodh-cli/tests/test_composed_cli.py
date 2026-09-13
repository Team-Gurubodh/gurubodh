"""Issues #286/#288: composed invocation, inspection, and retired input rejection."""

from contextlib import ExitStack, redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from component_contract_cases import without_job_schemas
from gurubodh.cli import main
from gurubodh.config import (
    prepare_generate_chunks_job, prepare_generate_docx_job, prepare_prep_subject_job,
)
from gurubodh.contracts import GenerateChunksJob, GenerateDocxJob, PrepSubjectJob
from test_job_composition import CLI_ROOT, FIXTURES, KINDS


PREPARERS = {"prep-subject": prepare_prep_subject_job,
             "generate-chunks": prepare_generate_chunks_job, "generate-docx": prepare_generate_docx_job}
RUNNERS = {
    "prep-subject": "gurubodh.pipelines.dispatcher.run_legacy_docx_to_unicode",
    "generate-chunks": "gurubodh.cli.run_generate_chunks_job",
    "generate-docx": "gurubodh.cli.run_generate_docx_job",
}
TYPES = {"prep-subject": PrepSubjectJob, "generate-chunks": GenerateChunksJob, "generate-docx": GenerateDocxJob}


class ComposedCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        shutil.copytree(CLI_ROOT / "config", self.root / "config")
        for filename in ("aps-hindi", "unicode-bilingual"):
            document = json.loads((FIXTURES / f"subjects/{filename}.json").read_text())
            self.write(f"jobs/subjects/{document['manifest_id']}/manifest.json", document)
        alternate = json.loads((self.root / KINDS["proofreading-profile"]).read_text())
        alternate["profile_id"] = "example-proofreading-v2"
        self.write("config/job-components/profiles/proofreading/example-proofreading-v2.json", alternate)
        self.env = {"GURUBODH_SOURCE_LIBRARY_ROOT": str(self.root / "source"),
                    "GURUBODH_CMS_LIBRARY_ROOT": str(self.root / "artifacts")}
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, self.env, clear=True).start()

    def write(self, relative, payload):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def selectors(self, route="local", subject="sub001_aps_example", language="hi-IN"):
        return ["--project-root", str(self.root), "--subject", subject, "--language", language,
                "--environment", "development", "--storage-profile", route]

    def invoke(self, argv):
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertIsNone(main(argv))  # Console entry points call sys.exit(main()).
        return stdout.getvalue(), stderr.getvalue()

    def error(self, argv, message):
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), self.assertRaises(SystemExit) as caught:
            main(argv)
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(message, stderr.getvalue())

    def resolve(self, command, route="local", extra=()):
        stdout, stderr = self.invoke(["config", "resolve", "--command", command, *self.selectors(route), *extra])
        return json.loads(stdout), stderr

    def test_help_explains_modes_precedence_retirement_and_inspection_streams(self):
        for command in PREPARERS:
            stdout, stderr = StringIO(), StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr), self.assertRaises(SystemExit) as caught:
                main([command, "--help"])
            self.assertEqual(caught.exception.code, 0)
            help_text = " ".join(stdout.getvalue().split())
            for phrase in ("manifest ID", "--language", "--environment", "--storage-profile",
                           "command definition < manifest < edition < invocation", "r2-output"):
                self.assertIn(phrase, help_text)
            self.assertEqual("--proofreading-profile" in help_text, command == "prep-subject")
            self.assertEqual("--chunking-profile" in help_text, command == "generate-chunks")
            self.assertEqual("--chapters" in help_text, command == "generate-chunks")
        stdout = StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit):
            main(["config", "resolve", "--help"])
        help_text = " ".join(stdout.getvalue().split())
        for phrase in ("stdout", "stderr", "--provenance", "without reading content", "exported JSON is not an executable input"):
            self.assertIn(phrase, help_text)

    def test_all_commands_routes_and_editions_dispatch_prepared_jobs_with_provenance(self):
        for command in PREPARERS:
            for route in ("local", "r2-output", "r2"):
                for subject, language in (("sub001_aps_example", "hi-IN"),
                                          ("sub123_spand_rahasya", "hi-IN"),
                                          ("sub123_spand_rahasya", "mr-IN")):
                    with self.subTest(command=command, route=route, subject=subject, language=language):
                        runner_name = RUNNERS[command]
                        unicode_prep = command == "prep-subject" and subject == "sub123_spand_rahasya"
                        if unicode_prep:
                            runner_name = "gurubodh.pipelines.dispatcher.run_unicode_docx_ingest"
                        with patch(runner_name, return_value={"processed_chapter_count": 1, "total_chunk_count": 2}) as runner:
                            self.invoke([command, *self.selectors(route, subject, language), "--overwrite"])
                        args, kwargs = runner.call_args
                        job = args[0] if unicode_prep else args[1]
                        self.assertIsInstance(job, TYPES[command])
                        self.assertEqual(job.provenance.input_mode, "composition")
                        self.assertEqual(job.provenance.manifest_id, subject)
                        self.assertEqual(job.provenance.edition, language)
                        self.assertNotIn("provenance", job.to_payload())
                        self.assertEqual(job["source"]["backend"], "r2" if route == "r2" else "local")
                        self.assertEqual(job["destination"]["backend"], "local" if route == "local" else "r2")
                        if command == "prep-subject":
                            self.assertTrue(args[2] if unicode_prep else args[3])
                            self.assertFalse(kwargs["resume"])
                        else:
                            self.assertTrue(kwargs["overwrite"])
                            self.assertNotIn("config_path", kwargs)

    def test_inspection_is_deterministic_valid_and_has_no_side_effects(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        forbidden = [
            *RUNNERS.values(), "gurubodh.cli.run_prepared_job",
            "gurubodh.storage.R2StorageClient.__init__", "gurubodh.storage.materialize_source",
            "gurubodh.proofreading.gemini.GeminiProofreader.__init__",
            "gurubodh.ml.embeddings.SentenceTransformerEmbeddingHelper.__init__",
            "gurubodh.ml.semantic_chunking.chunker.SemanticChunker.__init__",
            "gurubodh.prep_checkpoint.PrepCheckpointManager.__init__",
            "gurubodh.docx.text.extract_docx_text", "socket.socket", "subprocess.Popen",
        ]
        with ExitStack() as stack:
            for name in forbidden:
                stack.enter_context(patch(name, side_effect=AssertionError(name)))
            for name in ("mkdir", "write_text", "write_bytes", "unlink", "rename", "replace"):
                stack.enter_context(patch.object(Path, name, side_effect=AssertionError(name)))
            for command in PREPARERS:
                for route in ("local", "r2-output", "r2"):
                    argv = ["config", "resolve", "--command", command, *self.selectors(route)]
                    first = self.invoke(argv)
                    self.assertEqual(first, self.invoke(argv))
                    with_provenance, provenance = self.invoke([*argv, "--provenance"])
                    self.assertEqual(first, (with_provenance, ""))
                    payload = json.loads(first[0])
                    job = PREPARERS[command](payload, "CLI inspection")
                    self.assertEqual(job.to_payload(), payload)
                    self.assertEqual(json.loads(provenance)["storage_profile_id"], route)
            with patch.dict(os.environ, {}, clear=True):
                for command in PREPARERS:
                    self.resolve(command, "r2")
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_missing_mixed_and_unsupported_inputs_fail_before_resolution(self):
        with patch("gurubodh.cli.resolve_project_context", side_effect=AssertionError("unexpected project lookup")):
            for command in PREPARERS:
                self.error([command], "required")
                selectors = self.selectors()
                for option in ("--subject", "--language", "--environment", "--storage-profile"):
                    index = selectors.index(option)
                    self.error([command, *selectors[:index], *selectors[index + 2:]], option)
                self.error([command, *selectors, "--config", "job.json"], "unrecognized arguments")
                self.error([command, *selectors, "--model", "arbitrary"], "unrecognized arguments")
                self.error([command, *selectors, "--max-output-tokens", "123"], "unrecognized arguments")
            for command, flag, value in (("prep-subject", "--chapters", "001"),
                                          ("generate-docx", "--chapters", "001"),
                                          ("prep-subject", "--chunking-profile", "x-v1"),
                                          ("generate-chunks", "--proofreading-profile", "x-v1"),
                                          ("generate-docx", "--proofreading-profile", "x-v1")):
                self.error([command, *self.selectors(), flag, value], "unrecognized arguments")
                self.error(["config", "resolve", "--command", command, *self.selectors(), flag, value], "supported only")
            for command in ("generate-chunks", "generate-docx"):
                self.error([command, *self.selectors(), "--resume"], "unrecognized arguments")
            self.error(["prep-subject", *self.selectors(), "--overwrite", "--resume"], "mutually exclusive")
            self.error(["config", "resolve", "--command", "generate-docx", *self.selectors(), "--config", "job.json"], "unrecognized arguments")

    def test_chapter_selection_preserves_order_and_validation(self):
        payload, provenance = self.resolve("generate-chunks", extra=["--chapters", "012", "001", "--provenance"])
        self.assertEqual(payload["chapters"], ["012", "001"])
        self.assertEqual(json.loads(provenance)["invocation"]["chapters"], ["012", "001"])
        with patch(RUNNERS["generate-chunks"], return_value={"processed_chapter_count": 2, "total_chunk_count": 2}) as runner:
            self.invoke(["generate-chunks", *self.selectors(), "--chapters", "012", "001"])
        self.assertEqual(runner.call_args.args[1]["chapters"], ["012", "001"])
        for chapters in (["1"], ["0001"], ["001", "001"], ["००१"], ["001,002"]):
            for prefix in (["generate-chunks"], ["config", "resolve", "--command", "generate-chunks"]):
                self.error([*prefix, *self.selectors(), "--chapters", *chapters], "three-ASCII-digit")

    def test_profile_precedence_replaces_whole_profiles_for_inspection_and_execution(self):
        for command, kind, base_id in (("prep-subject", "proofreading", "gemini-3.6-flash-v1"),
                                       ("generate-chunks", "chunking", "bge-m3-semantic-window-v1")):
            relative = f"config/job-components/profiles/{kind}/{base_id}.json"
            base = json.loads((self.root / relative).read_text())
            for level, marker in (("manifest", 1), ("edition", 2), ("invocation", 3)):
                alternate = json.loads(json.dumps(base))
                alternate["profile_id"] = f"{level}-v1"
                alternate[kind]["max_retries" if kind == "proofreading" else "window_size"] = marker
                self.write(f"config/job-components/profiles/{kind}/{level}-v1.json", alternate)
            manifest_path = KINDS["subject-manifest"]
            manifest = json.loads((self.root / manifest_path).read_text())
            for level in ("command", "manifest", "edition", "invocation"):
                extra = []
                if level in ("manifest", "edition", "invocation"):
                    manifest["profile_overrides"] = {kind: "manifest-v1"}
                if level in ("edition", "invocation"):
                    manifest["editions"]["hi-IN"]["profile_overrides"] = {kind: "edition-v1"}
                if level == "invocation":
                    extra = [f"--{kind}-profile", "invocation-v1"]
                self.write(manifest_path, manifest)
                payload, provenance = self.resolve(command, extra=[*extra, "--provenance"])
                identity = base_id if level == "command" else f"{level}-v1"
                selected = json.loads((self.root / f"config/job-components/profiles/{kind}/{identity}.json").read_text())
                self.assertEqual(payload[kind], selected[kind])
                self.assertEqual(json.loads(provenance)["profiles"][0]["selected_by"], level)
                with patch(RUNNERS[command], return_value={"processed_chapter_count": 1, "total_chunk_count": 1}) as runner:
                    self.invoke([command, *self.selectors(), *extra])
                self.assertEqual(runner.call_args.args[1][kind], selected[kind])
            # Reset selections before testing the other profile kind.
            manifest.pop("profile_overrides", None)
            manifest["editions"]["hi-IN"].pop("profile_overrides", None)
            self.write(manifest_path, manifest)

    def test_cli_component_validation_is_independent_of_complete_job_schemas(self):
        class ReachedPreparation(Exception):
            pass

        # Stop exactly at the separate assembled-job preparation boundary.
        # All consumed components must have validated before this sentinel.
        for kind, relative in KINDS.items():
            command = "generate-chunks" if kind == "chunking-profile" else "prep-subject"
            path = self.root / relative
            original = path.read_bytes()
            for prefix in ([command], ["config", "resolve", "--command", command]):
                with without_job_schemas(), patch.dict(
                    "gurubodh.job_composition._PREPARERS", {command: lambda *args: (_ for _ in ()).throw(ReachedPreparation())}
                ):
                    with self.assertRaises(ReachedPreparation):
                        self.invoke([*prefix, *self.selectors()])
                    document = json.loads(original)
                    del document["component_schema_version"]
                    self.write(relative, document)
                    self.error([*prefix, *self.selectors()], "component_schema_version")
                    path.write_bytes(original)

    def test_configuration_errors_keep_stdout_empty_and_identify_component_location(self):
        document = json.loads((self.root / KINDS["proofreading-profile"]).read_text())
        del document["proofreading"]["max_retries"]
        self.write(KINDS["proofreading-profile"], document)
        self.error(["config", "resolve", "--command", "prep-subject", *self.selectors(), "--provenance"], "$.proofreading.max_retries")
        with patch.dict(os.environ, {}, clear=True):
            self.error(["config", "resolve", "--command", "generate-docx", *self.selectors()], "GURUBODH_CMS_LIBRARY_ROOT")

    def test_retired_aliases_and_loaders_are_unavailable(self):
        import gurubodh.config as configuration
        import gurubodh.pipelines.dispatcher as dispatcher
        for name in ("load_prep_subject_job", "load_generate_chunks_job", "load_generate_docx_job"):
            self.assertFalse(hasattr(configuration, name))
        for name in ("run_configured_job", "run_unicode_job", "run_legacy_job"):
            self.assertFalse(hasattr(dispatcher, name))
        with patch("gurubodh.cli.resolve_project_context", side_effect=AssertionError("project lookup")):
            for alias in ("legacy-convert", "unicode-ingest"):
                self.error([alias, "--config", "missing.json"], "invalid choice")

    def test_large_input_profile_selection_by_invocation_and_manifest(self):
        profile_id = "gemini-3.6-flash-large-input-v1"
        default, _ = self.resolve("prep-subject")
        self.assertEqual(default["proofreading"]["max_estimated_input_tokens_per_minute"], 20000)
        expected = dict(default["proofreading"], max_estimated_input_tokens_per_minute=40000)
        for selection in ("invocation", "manifest"):
            with self.subTest(selection=selection):
                extra = ["--proofreading-profile", profile_id]
                if selection == "manifest":
                    relative = "jobs/subjects/sub001_aps_example/manifest.json"
                    manifest = json.loads((self.root / relative).read_text())
                    manifest["profile_overrides"] = {"proofreading": profile_id}
                    self.write(relative, manifest)
                    extra = []
                with patch(RUNNERS["prep-subject"], return_value={"processed_chapter_count": 1}) as runner:
                    self.invoke(["prep-subject", *self.selectors(), *extra])
                self.assertEqual(runner.call_args.args[1]["proofreading"], expected)

    def test_lab_profile_selector_preserves_manifest_free_interface(self):
        for profile in (None, "gemini-3.6-flash-v1", "gemini-3.6-flash-large-input-v1"):
            extra = [] if profile is None else ["--proofreading-profile", profile]
            with patch("gurubodh.cli.run_lab_proofread", return_value={"run_directory": "lab-run"}) as runner:
                self.invoke(["lab", "proofread", "--source", "source.docx", "--locale", "mr-IN",
                             "--lab-root", str(self.root / "lab"), "--project-root", str(self.root), *extra])
            self.assertEqual(runner.call_args.args[1:3], ("source.docx", "mr-IN"))
            self.assertEqual(runner.call_args.kwargs["proofreading_profile_id"], profile)

    def test_project_discovery_is_preserved(self):
        for environment_root in (False, True):
            with patch("pathlib.Path.cwd", return_value=self.root / "jobs/subjects"), \
                 patch.dict(os.environ, {"GURUBODH_CLI_ROOT": str(self.root)} if environment_root else {}), \
                 patch(RUNNERS["generate-docx"], return_value={"processed_chapter_count": 1}) as runner:
                self.invoke(["generate-docx", *self.selectors()[2:]])
            self.assertEqual(runner.call_args.args[0].root, self.root)

    def test_exported_configuration_is_not_an_executable_input(self):
        for command in PREPARERS:
            payload, _ = self.resolve(command)
            path = self.write("resolved.json", payload)
            with patch(RUNNERS[command], side_effect=AssertionError("execution forbidden")):
                self.error([command, *self.selectors(), "--config", str(path)], "unrecognized arguments")

    def test_resume_reaches_both_prep_pipelines(self):
        for subject in ("sub001_aps_example", "sub123_spand_rahasya"):
            runner_name = (RUNNERS["prep-subject"] if subject == "sub001_aps_example"
                           else "gurubodh.pipelines.dispatcher.run_unicode_docx_ingest")
            with patch(runner_name) as runner:
                self.invoke(["prep-subject", *self.selectors(subject=subject), "--resume"])
            self.assertTrue(runner.call_args.kwargs["resume"])


if __name__ == "__main__":
    unittest.main()
