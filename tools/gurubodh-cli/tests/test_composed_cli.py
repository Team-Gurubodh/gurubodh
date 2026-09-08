"""Issue #286: public invocation, inspection, and temporary compatibility."""

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
    load_generate_chunks_job, load_generate_docx_job, load_prep_subject_job,
    prepare_generate_chunks_job, prepare_generate_docx_job, prepare_prep_subject_job,
)
from gurubodh.contracts import GenerateChunksJob, GenerateDocxJob, PrepSubjectJob
from test_job_composition import CLI_ROOT, FIXTURES, KINDS


PREPARERS = {"prep-subject": prepare_prep_subject_job,
             "generate-chunks": prepare_generate_chunks_job, "generate-docx": prepare_generate_docx_job}
LOADERS = {"prep-subject": load_prep_subject_job,
           "generate-chunks": load_generate_chunks_job, "generate-docx": load_generate_docx_job}
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
                           "mutually exclusive", "Retires after maintainer comparison acceptance",
                           "command definition < manifest < edition < invocation", "r2-output"):
                self.assertIn(phrase, help_text)
            self.assertEqual("--proofreading-profile" in help_text, command == "prep-subject")
            self.assertEqual("--chunking-profile" in help_text, command == "generate-chunks")
            self.assertEqual("--chapters" in help_text, command == "generate-chunks")
        stdout = StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit):
            main(["config", "resolve", "--help"])
        help_text = " ".join(stdout.getvalue().split())
        for phrase in ("stdout", "stderr", "--provenance", "without reading content", "permanent file-based replay is not promised"):
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
                            self.assertIsNone(args[3] if unicode_prep else args[4])
                            self.assertFalse(kwargs["resume"])
                        else:
                            self.assertTrue(kwargs["overwrite"])
                            self.assertIsNone(kwargs["config_path"])

    def test_inspection_is_deterministic_valid_replayable_and_has_no_side_effects(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        forbidden = [
            *RUNNERS.values(), "gurubodh.cli.run_prepared_job", "gurubodh.cli.run_configured_job",
            "gurubodh.storage.R2StorageClient.__init__", "gurubodh.storage.materialize_source",
            "gurubodh.proofreading.gemini.GeminiProofreader.__init__",
            "gurubodh.ml.embeddings.SentenceTransformerEmbeddingHelper.__init__",
            "gurubodh.ml.semantic_chunking.chunker.SemanticChunker.__init__",
            "gurubodh.prep_checkpoint.PrepCheckpointManager.__init__",
            "gurubodh.docx.text.extract_docx_text", "socket.socket", "subprocess.Popen",
        ]
        exports = []
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
                    exports.append((command, payload))
            with patch.dict(os.environ, {}, clear=True):
                for command in PREPARERS:
                    self.resolve(command, "r2")
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        for command, payload in exports:
            path = self.write("export.json", payload)
            self.assertEqual(LOADERS[command](path).to_payload(), payload)

    def test_missing_mixed_and_unsupported_inputs_fail_before_resolution(self):
        with patch("gurubodh.cli.resolve_project_context", side_effect=AssertionError("unexpected project lookup")):
            for command in PREPARERS:
                self.error([command], "Composed mode requires explicit")
                selectors = self.selectors()
                for option in ("--subject", "--language", "--environment", "--storage-profile"):
                    index = selectors.index(option)
                    self.error([command, *selectors[:index], *selectors[index + 2:]], option)
                for option, value in (("--subject", "example"), ("--language", "hi-IN"),
                                      ("--environment", "development"), ("--storage-profile", "r2")):
                    self.error([command, "--config", "job.json", option, value], "mutually exclusive")
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
                self.error([command, "--config", "job.json", "--resume"], "unrecognized arguments")
            for mode in (["--config", "job.json"], self.selectors()):
                self.error(["prep-subject", *mode, "--overwrite", "--resume"], "mutually exclusive")
            for flag, values, command in (("--proofreading-profile", ["x-v1"], "prep-subject"),
                                          ("--chunking-profile", ["x-v1"], "generate-chunks"),
                                          ("--chapters", ["001"], "generate-chunks")):
                self.error([command, "--config", "job.json", flag, *values], "mutually exclusive")
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

    def test_complete_jobs_remain_exact_without_loading_components(self):
        paths = sorted((CLI_ROOT / "jobs/subjects").glob("*/*/*.json"))
        self.assertEqual(len(paths), 26)
        with patch("gurubodh.cli.ComponentCatalog", side_effect=AssertionError("complete jobs must not compose")):
            for path in paths:
                command = path.name.split(".")[0]
                payload = json.loads(path.read_text())
                runner_name = RUNNERS[command]
                unicode_prep = command == "prep-subject" and payload["source"]["font_encoding"] == "unicode"
                if unicode_prep:
                    runner_name = "gurubodh.pipelines.dispatcher.run_unicode_docx_ingest"
                with patch(runner_name, return_value={"processed_chapter_count": 1, "total_chunk_count": 1}) as runner:
                    self.invoke([command, "--project-root", str(self.root), "--config", str(path)])
                job = runner.call_args.args[0 if unicode_prep else 1]
                self.assertEqual(job.to_payload(), payload)
                # Historical loading leaves audit provenance to AuditContext;
                # it must not acquire composed provenance or JSON defaults.
                self.assertIsNone(job.provenance)

    def test_resume_dispatch_and_deprecated_entry_points_keep_file_compatibility(self):
        with patch(RUNNERS["prep-subject"]) as runner:
            self.invoke(["prep-subject", *self.selectors(), "--resume"])
        self.assertTrue(runner.call_args.kwargs["resume"])
        self.assertFalse(runner.call_args.args[3])
        for command, runner_name, filename, job_index in (
            ("legacy-convert", RUNNERS["prep-subject"], "sub039_test_aps_font", 1),
            ("unicode-ingest", "gurubodh.pipelines.dispatcher.run_unicode_docx_ingest", "sub123_test_unicode_font", 0),
        ):
            path = CLI_ROOT / f"jobs/subjects/{filename}/hi-IN/prep-subject.local.json"
            with patch(runner_name) as runner, patch("gurubodh.cli.ComponentCatalog", side_effect=AssertionError("composition")):
                self.invoke([command, "--project-root", str(self.root), "--config", str(path), "--overwrite"])
            self.assertIsInstance(runner.call_args.args[job_index], PrepSubjectJob)
            self.assertEqual(runner.call_args.kwargs["config_path"], path)
            self.assertEqual(runner.call_args.args[job_index + 1], f"python3 -m gurubodh {command}")
            self.assertTrue(runner.call_args.args[job_index + 2])

    def test_lab_profile_selector_preserves_manifest_free_interface(self):
        for profile in (None, "gemini-3.6-flash-v1"):
            extra = [] if profile is None else ["--proofreading-profile", profile]
            with patch("gurubodh.cli.run_lab_proofread", return_value={"run_directory": "lab-run"}) as runner:
                self.invoke(["lab", "proofread", "--source", "source.docx", "--locale", "mr-IN",
                             "--lab-root", str(self.root / "lab"), "--project-root", str(self.root), *extra])
            self.assertEqual(runner.call_args.args[1:3], ("source.docx", "mr-IN"))
            self.assertEqual(runner.call_args.kwargs["proofreading_profile_id"], profile)

    def test_project_discovery_and_relative_complete_config_resolution_are_preserved(self):
        payload, _ = self.resolve("generate-docx")
        self.write("comparison.json", payload)
        for environment_root in (False, True):
            for composed in (False, True):
                arguments = self.selectors()[2:] if composed else ["--config", "comparison.json"]
                with patch("pathlib.Path.cwd", return_value=self.root / "jobs/subjects"), \
                     patch.dict(os.environ, {"GURUBODH_CLI_ROOT": str(self.root)} if environment_root else {}), \
                     patch(RUNNERS["generate-docx"], return_value={"processed_chapter_count": 1}) as runner:
                    self.invoke(["generate-docx", *arguments])
                self.assertEqual(runner.call_args.args[0].root, self.root)
                self.assertEqual(runner.call_args.kwargs["config_path"], None if composed else self.root / "comparison.json")

    def test_exported_configuration_dispatches_through_complete_config_mode(self):
        for command in PREPARERS:
            payload, _ = self.resolve(command)
            path = self.write("resolved.json", payload)
            with patch(RUNNERS[command], return_value={"processed_chapter_count": 1, "total_chunk_count": 1}) as runner:
                self.invoke([command, "--project-root", str(self.root), "--config", str(path)])
            self.assertEqual(runner.call_args.args[1].to_payload(), payload)

    def test_resume_reaches_both_prep_pipelines_in_both_input_modes(self):
        for subject in ("sub001_aps_example", "sub123_spand_rahasya"):
            selectors = self.selectors(subject=subject)
            stdout, _ = self.invoke(["config", "resolve", "--command", "prep-subject", *selectors])
            self.write("resolved.json", json.loads(stdout))
            runner_name = (RUNNERS["prep-subject"] if subject == "sub001_aps_example"
                           else "gurubodh.pipelines.dispatcher.run_unicode_docx_ingest")
            for arguments in (selectors, ["--project-root", str(self.root), "--config", "resolved.json"]):
                with patch(runner_name) as runner:
                    self.invoke(["prep-subject", *arguments, "--resume"])
                self.assertTrue(runner.call_args.kwargs["resume"])


if __name__ == "__main__":
    unittest.main()
