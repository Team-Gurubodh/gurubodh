"""Issue #285: safe audit identity and independent checkpoint compatibility."""

import copy
from dataclasses import FrozenInstanceError
import hashlib
import io
import json
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_job_composition as composition_cases
from test_job_composition import KINDS
from test_prep_subject_checkpoints import (
    FakeProofreader, FakeR2Client, prepare_unicode, write_docx,
)
from gurubodh.audit import AuditContext, AuditWriter, report_paths, safe_configuration_snapshot
from gurubodh.config import load_prep_subject_job, prepare_prep_subject_job
from gurubodh.configuration_provenance import canonical_json, configuration_digest, provenance_markdown
from gurubodh.errors import GurubodhError
from gurubodh.prep_checkpoint import compatibility_record
from gurubodh.prep_subject_checkpoints import run_resumable_prep_job, JOB_STATE_RELATIVE_PATH
from gurubodh.proofreading import ProofreadingError
from gurubodh.schema_validation import validate_artifact
from gurubodh.pipelines.generate_chunks import run_generate_chunks_job
from gurubodh.pipelines.generate_docx import run_generate_docx_job
from test_generate_chunks_pipeline import FakeSegmenter


class ConfigurationProvenanceTests(unittest.TestCase):
    setUp = composition_cases.CompositionTests.setUp
    read = composition_cases.CompositionTests.read
    write = composition_cases.CompositionTests.write
    resolve = composition_cases.CompositionTests.resolve

    def context(self, job):
        return AuditContext.create("prep-subject", "test", self.root, config=job)

    def envelope(self, job):
        writer = AuditWriter(self.context(job), report_paths(self.root, "test"))
        return writer.build_envelope(
            status="succeeded", job_identity=None, processing_summary={}, lifecycle=None,
            publication={"backend": "local", "status": "succeeded"}, failure=None,
            command_details={},
        )

    def test_canonical_json_encoding_and_number_contract(self):
        expected = '{"a":[null,true,1,0,1.25],"ह":"पाठ"}'.encode("utf-8")
        self.assertEqual(canonical_json({"ह": "पाठ", "a": [None, True, 1.0, -0.0, 1.25]}), expected)
        for value in (float("nan"), float("inf"), object(), {1: "value"}):
            with self.subTest(value=type(value)), self.assertRaises(ValueError):
                canonical_json(value)
        self.assertNotEqual(canonical_json({"a": None}), canonical_json({}))
        self.assertNotEqual(canonical_json([1, 2]), canonical_json([2, 1]))

    def test_profile_rename_reformat_and_operational_change_have_distinct_identities(self):
        first = self.resolve().job
        renamed = self.resolve(proofreading_profile_id="example-proofreading-v2").job
        self.assertEqual(first.to_payload(), renamed.to_payload())
        self.assertEqual(first.provenance.assembled_configuration_sha256,
                         renamed.provenance.assembled_configuration_sha256)
        self.assertNotEqual(first.provenance.components, renamed.provenance.components)
        self.assertEqual(renamed.provenance.profiles[0].selected_by, "invocation")
        self.assertEqual(renamed.provenance.to_payload()["invocation"]["profiles"],
                         {"proofreading": "example-proofreading-v2"})
        for component in first.provenance.components:
            path = self.root / component.resource_reference
            data = json.loads(path.read_text())
            path.write_text(json.dumps(dict(reversed(list(data.items()))), ensure_ascii=False))
        reformatted = self.resolve().job
        self.assertEqual(first.provenance, reformatted.provenance)
        profile = self.read(KINDS["proofreading-profile"])
        profile["proofreading"]["max_retries"] += 1
        self.write(KINDS["proofreading-profile"], profile)
        operational = self.resolve().job
        self.assertNotEqual(first.provenance.assembled_configuration_sha256,
                            operational.provenance.assembled_configuration_sha256)
        for equivalent in (renamed, reformatted, operational):
            self.assertEqual(compatibility_record(first, "a" * 64),
                             compatibility_record(equivalent, "a" * 64))

    def test_output_affecting_changes_keep_existing_fingerprint_contract(self):
        first = self.resolve().job
        changes = [
            ("proofreading", "model", "gemini-other"),
            ("proofreading", "max_output_tokens", 8192),
            ("proofreading", "max_input_characters", 15000),
            ("chapter_split", "pattern", "different"),
            ("naming", "version", "02"),
        ]
        for section, field, value in changes:
            payload = first.to_payload()
            payload[section][field] = value
            changed = prepare_prep_subject_job(payload)
            with self.subTest(field=field):
                self.assertNotEqual(compatibility_record(first, "a" * 64),
                                    compatibility_record(changed, "a" * 64))
        self.assertNotEqual(compatibility_record(first, "a" * 64),
                            compatibility_record(first, "b" * 64))

    def test_snapshots_are_isolated_from_files_environment_and_returned_payloads(self):
        job = self.resolve().job
        before = job.provenance.to_payload()
        for component in job.provenance.components:
            (self.root / component.resource_reference).write_text("{}")
        self.environ.clear()
        context = self.context(job)
        job.provenance.to_payload()["components"].clear()
        self.assertEqual(context.configuration_provenance.to_payload(), before)
        job.to_payload().clear()
        self.assertEqual(context.configuration_snapshot, job.to_payload())
        self.assertNotIn("provenance", job.to_payload())
        self.assertNotIn("configuration_provenance", job.to_payload())
        with self.assertRaises(FrozenInstanceError):
            job.provenance.edition = "mr-IN"
        context.configuration_snapshot["proofreading"]["max_retries"] += 1
        writer = AuditWriter(context, report_paths(self.root, "mutated"))
        with self.assertRaisesRegex(GurubodhError, "snapshot differs"):
            writer.build_envelope(status="succeeded", job_identity=None, processing_summary={},
                                  lifecycle=None, publication={}, failure=None, command_details={})
        job["proofreading"]["max_retries"] += 1
        with self.assertRaisesRegex(ValueError, "resolve the job again"):
            self.context(job)
        self.assertEqual(context.configuration_provenance.to_payload(), before)

    def test_selected_stores_bindings_and_unused_environment_declarations(self):
        first = self.resolve(command="generate-docx").job
        self.assertEqual(first.provenance.environment_bindings, ("GURUBODH_CMS_LIBRARY_ROOT",))
        environment = self.read(KINDS["environment"])
        environment["stores"]["local_source_library"]["root_dir"]["$env"] = "UNUSED_ROOT"
        environment["stores"]["r2_source_library"]["bucket"] = "unused-bucket"
        self.write(KINDS["environment"], environment)
        second = self.resolve(command="generate-docx").job
        self.assertEqual(first.provenance.assembled_configuration_sha256,
                         second.provenance.assembled_configuration_sha256)
        self.assertNotEqual(first.provenance.components, second.provenance.components)
        exported = json.dumps(self.envelope(second))
        self.assertNotIn("UNUSED_ROOT", exported)
        self.assertNotIn("unused-bucket", exported)
        r2 = self.resolve(command="generate-docx", storage_profile_id="r2", environ={}).job
        self.assertEqual(r2.provenance.environment_bindings, ())
        with patch.dict("os.environ", {"GURUBODH_MODEL_CACHE_DIR": "/safe/cache"}):
            chunks = self.resolve(command="generate-chunks").job
        self.assertIn("GURUBODH_MODEL_CACHE_DIR", chunks.provenance.environment_bindings)
        self.assertNotIn("/safe/cache", json.dumps(chunks.provenance.to_payload()))
        environment["stores"]["local_destination_library"]["root_dir"]["$env"] = "_destinationRoot"
        self.write(KINDS["environment"], environment)
        custom = self.resolve(command="generate-docx", environ={"_destinationRoot": "/library"}).job
        self.assertEqual(custom.provenance.environment_bindings, ("_destinationRoot",))
        validate_artifact(self.envelope(custom), "audit report")

    def test_secret_redaction_precedes_export_and_digest_including_metadata_extensions(self):
        payload = self.resolve().job.to_payload()
        payload["metadata_defaults"]["innocent_extension"] = {"text": "PRIVATE CHAPTER", "auth": "SECRET"}
        payload["metadata_defaults"]["PRIVATE KEY"] = "PRIVATE VALUE"
        payload["source"]["api_key"] = "SECRET"
        payload["source"]["url_base"] = "https://user:SECRET@example.org/library?signature=SECRET#SECRET"
        payload["source"]["prompt_body"] = "PRIVATE PROMPT"
        snapshot = safe_configuration_snapshot(payload)
        serialized = canonical_json(snapshot).decode("utf-8")
        for forbidden in ("SECRET", "PRIVATE", "innocent_extension", "signature", "user:"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(snapshot["source"]["url_base"], "https://example.org/library")
        changed = copy.deepcopy(payload)
        changed["source"]["api_key"] = "OTHER SECRET"
        changed["metadata_defaults"]["innocent_extension"] = "OTHER CHAPTER"
        self.assertEqual(configuration_digest(payload), configuration_digest(changed))
        self.assertEqual(configuration_digest(snapshot), hashlib.sha256(canonical_json(snapshot)).hexdigest())

    def test_schema_versions_validate_before_writes_and_historical_reports_remain_readable(self):
        report = self.envelope(self.resolve().job)
        validate_artifact(report, "audit report")
        old = copy.deepcopy(report)
        old["schema_version"] = "2.0.0"
        del old["configuration_provenance"]
        validate_artifact(old, "audit report")
        self.assertEqual(provenance_markdown(old), [])
        for change in (lambda r: r.pop("configuration_provenance"),
                       lambda r: r["configuration_provenance"].update(schema_version="2.0.0"),
                       lambda r: r["configuration_provenance"].update(assembled_configuration_sha256="bad"),
                       lambda r: r["configuration_provenance"].update(unexpected="value")):
            bad = copy.deepcopy(report)
            change(bad)
            writer = AuditWriter(self.context(self.resolve().job), report_paths(self.root, "bad"))
            with patch.object(writer, "build_envelope", return_value=bad), \
                 patch("gurubodh.audit._write_bytes_atomically") as write, \
                 self.assertRaises(GurubodhError):
                writer.write(status="succeeded", job_identity=None, processing_summary={},
                             lifecycle=None, publication={}, failure=None, command_details={},
                             renderer=lambda _: "unused")
            write.assert_not_called()

    def unicode_job(self, route="local"):
        relative = "jobs/subjects/sub123_spand_rahasya/manifest.json"
        manifest = self.read(relative)
        manifest["editions"]["hi-IN"]["chapter_split"] = {
            "enabled": True, "pattern_type": "regex", "pattern": "^CHAPTER", "flags": ["MULTILINE"],
        }
        self.write(relative, manifest)
        job = self.resolve(manifest_id="sub123_spand_rahasya", storage_profile_id=route).job
        path = Path(job["source"]["root_dir"]) / job["source"]["relative_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        write_docx(path)
        return job

    def test_complete_composed_overwrite_resume_local_and_fake_r2(self):
        for route in ("local", "r2-output"):
            for composed_first in (False, True):
                with self.subTest(route=route, composed_first=composed_first):
                    composed = self.unicode_job(route)
                    config_path = self.write("comparison.json", composed.to_payload())
                    complete = load_prep_subject_job(config_path)
                    first, resumed = (composed, complete) if composed_first else (complete, composed)
                    self.assertEqual(compatibility_record(first, "a" * 64), compatibility_record(resumed, "a" * 64))
                    client = FakeR2Client() if route == "r2-output" else None
                    subject = Path(self.environ["GURUBODH_CMS_LIBRARY_ROOT"]) / composed["destination"]["subject_dir"]
                    if client is None and subject.exists():
                        import shutil
                        shutil.rmtree(subject)
                    failure = ProofreadingError("api_error", "Temporary provider failure", retryable=True,
                        request_diagnostics={"raw_response": "PRIVATE provider body",
                                             "attempts": [{"attempt": 1, "http_status": 503,
                                                           "authorization": "PRIVATE provider body"}]})
                    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                        with self.assertRaisesRegex(GurubodhError, "incomplete"):
                            run_resumable_prep_job(first, "test", True, False,
                                None if composed_first else config_path, prepare_unicode,
                                proofreader=FakeProofreader(["CHAPTER 1\nसही।", failure]), r2_client=client)
                        run_resumable_prep_job(resumed, "test", False, True,
                            config_path if composed_first else None, prepare_unicode,
                            proofreader=FakeProofreader(["CHAPTER 2\nसही।"]), r2_client=client)
                    if client:
                        records = [json.loads(data) for key, data in client.objects.items()
                                   if "/run_reports/prep-subject/" in key and key.endswith(".json")]
                        state = json.loads(next(data for key, data in client.objects.items()
                                                if key.endswith(str(JOB_STATE_RELATIVE_PATH))))
                        markdown = "\n".join(data.decode() for key, data in client.objects.items()
                                             if "/run_reports/" in key and key.endswith(".md"))
                    else:
                        records = [json.loads(path.read_text()) for path in (subject / "run_reports/prep-subject").glob("*.json")]
                        state = json.loads((subject / JOB_STATE_RELATIVE_PATH).read_text())
                        markdown = "\n".join(path.read_text() for path in (subject / "run_reports").rglob("*.md"))
                    self.assertTrue(state["replacement_authorized"])
                    self.assertEqual(state["state"], "succeeded")
                    self.assertEqual({r["run_identity"]["status"] for r in records}, {"succeeded", "incomplete"})
                    self.assertEqual({r["configuration_provenance"]["input_mode"] for r in records}, {"complete_config", "composition"})
                    self.assertEqual(len({r["configuration_provenance"]["assembled_configuration_sha256"] for r in records}), 1)
                    for report in records:
                        validate_artifact(report, "audit report")
                        self.assertIn(report["configuration_provenance"]["assembled_configuration_sha256"], markdown)
                        if report["configuration_provenance"]["input_mode"] == "composition":
                            self.assertIsNone(report["run_identity"]["config_path"])
                    self.assertNotIn("PRIVATE provider body", json.dumps(records))

    def test_derived_composed_success_and_failure_audits_local_and_fake_r2(self):
        for route in ("local", "r2-output"):
            prep = self.unicode_job(route)
            client = FakeR2Client() if route == "r2-output" else None
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                run_resumable_prep_job(prep, "test", False, False, None, prepare_unicode,
                    proofreader=FakeProofreader(["CHAPTER 1\nसही।", "CHAPTER 2\nसही।"]), r2_client=client)
            for command, runner in (("generate-docx", run_generate_docx_job),
                                    ("generate-chunks", run_generate_chunks_job)):
                with self.subTest(route=route, command=command):
                    job = self.resolve(command=command, manifest_id="sub123_spand_rahasya",
                        storage_profile_id="r2" if client else "local",
                        **({"chapters": ["001"]} if command == "generate-chunks" else {})).job
                    options = {"segmenter": FakeSegmenter()} if command == "generate-chunks" else {}
                    context = SimpleNamespace(root=self.root)
                    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                        runner(context, job, r2_client=client, **options)
                        with self.assertRaises(GurubodhError):
                            runner(context, job, r2_client=client, **options)
                    if client:
                        records = [json.loads(data) for key, data in client.objects.items()
                                   if f"/run_reports/{command}/" in key and key.endswith(".json")]
                        markdown = "\n".join(data.decode() for key, data in client.objects.items()
                                             if f"/run_reports/{command}/" in key and key.endswith(".md"))
                    else:
                        directory = Path(job["destination"]["root_dir"]) / job["destination"]["subject_dir"] / "run_reports" / command
                        records = [json.loads(path.read_text()) for path in directory.glob("*.json")]
                        markdown = "\n".join(path.read_text() for path in directory.glob("*.md"))
                    self.assertEqual({r["run_identity"]["status"] for r in records}, {"succeeded", "failed"})
                    for report in records:
                        validate_artifact(report, "audit report")
                        self.assertEqual(report["configuration_provenance"], job.provenance.to_payload())
                        self.assertIsNone(report["run_identity"]["config_path"])
                        self.assertIn(job.provenance.assembled_configuration_sha256, markdown)
                        if command == "generate-docx" and report["run_identity"]["status"] == "succeeded":
                            self.assertIn("reference", report["command_details"]["chapters"][0]["source_text"])

    def test_preflight_failure_has_provenance_without_creating_checkpoint(self):
        for route in ("local", "r2-output"):
            with self.subTest(route=route):
                job = self.unicode_job(route)
                (Path(job["source"]["root_dir"]) / job["source"]["relative_path"]).unlink()
                client = FakeR2Client() if route == "r2-output" else None
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(Exception):
                    run_resumable_prep_job(job, "test", False, False, None,
                                          prepare_unicode, r2_client=client)
                if client:
                    records = [json.loads(data) for key, data in client.objects.items()
                               if "/run_reports/" in key and key.endswith(".json")]
                    self.assertFalse(any(key.endswith(str(JOB_STATE_RELATIVE_PATH)) for key in client.objects))
                else:
                    subject = Path(job["destination"]["root_dir"]) / job["destination"]["subject_dir"]
                    records = [json.loads(path.read_text()) for path in subject.rglob("run_reports/**/*.json")]
                    self.assertFalse((subject / JOB_STATE_RELATIVE_PATH).exists())
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]["run_identity"]["status"], "failed")
                self.assertEqual(records[0]["configuration_provenance"], job.provenance.to_payload())

    def test_unexpected_execution_failure_retains_provenance(self):
        job = self.unicode_job()
        with patch("gurubodh.prep_subject_checkpoints.GeminiProofreader", side_effect=RuntimeError("Provider initialization failed")), \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), \
             self.assertRaisesRegex(RuntimeError, "initialization failed"):
            run_resumable_prep_job(job, "test", False, False, None, prepare_unicode)
        subject = Path(job["destination"]["root_dir"]) / job["destination"]["subject_dir"]
        reports = list(subject.rglob("run_reports/**/*.json"))
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text())
        self.assertEqual(report["run_identity"]["status"], "failed")
        self.assertEqual(report["failure"]["stage"], "execution")
        self.assertEqual(report["configuration_provenance"], job.provenance.to_payload())

    def test_historical_regex_records_resume_with_composed_provenance(self):
        from gurubodh.prep_checkpoint import PrepCheckpointManager, compatibility_record_from_inputs
        from test_prep_subject_checkpoints import incomplete_checkpoint_state
        for stored_flags, current_flags in ((None, []), ([], []),
                (["MULTILINE", "IGNORECASE"], ["IGNORECASE", "MULTILINE"])):
            job = self.unicode_job()
            relative = "jobs/subjects/sub123_spand_rahasya/manifest.json"
            manifest = self.read(relative)
            manifest["editions"]["hi-IN"]["chapter_split"]["flags"] = current_flags
            self.write(relative, manifest)
            job = self.resolve(manifest_id="sub123_spand_rahasya").job
            inputs = compatibility_record(job, "a" * 64)["output_affecting_inputs"]
            if stored_flags is None:
                inputs["chapter_split"].pop("flags")
            else:
                inputs["chapter_split"]["flags"] = stored_flags
            legacy = compatibility_record_from_inputs(inputs, "a" * 64)
            state_path = Path(job["destination"]["root_dir"]) / job["destination"]["subject_dir"] / JOB_STATE_RELATIVE_PATH
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(incomplete_checkpoint_state(legacy)))
            manager = PrepCheckpointManager(job, resume=True, overwrite=False, progress=lambda _: None)
            try:
                manager.open()
                self.assertEqual(manager.begin("a" * 64), "started")
            finally:
                manager.close()


if __name__ == "__main__":
    unittest.main()
