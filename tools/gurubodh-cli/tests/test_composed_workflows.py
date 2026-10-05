"""Independent jobs and composed jobs preserve shared publication contracts."""

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile
from xml.etree import ElementTree

from synthetic_jobs import FIXTURES, job_payload, write_catalog
from policy_fixtures import synthetic_source_fonts
from gurubodh.config import prepare_generate_chunks_job, prepare_generate_docx_job, prepare_prep_subject_job
from gurubodh.errors import GurubodhError
from gurubodh.job_components import ComponentCatalog
from gurubodh.job_composition import resolve_job
from gurubodh.prep_checkpoint import compatibility_record
from gurubodh.prep_subject_checkpoints import run_resumable_prep_job
from gurubodh.pipelines.generate_chunks import run_generate_chunks_job
from gurubodh.pipelines.generate_docx import run_generate_docx_job
from gurubodh.schema_validation import validate_artifact
from gurubodh.storage import destination_artifact_reference, source_reference
from test_generate_chunks_pipeline import FakeSegmenter
from test_prep_subject_checkpoints import FakeProofreader, FakeR2Client, prepare_unicode, write_docx


EDITIONS = (("sub001_aps_example", "hi-IN"), ("sub123_spand_rahasya", "hi-IN"),
            ("sub123_spand_rahasya", "mr-IN"))
ROUTES = ("local", "r2-output", "r2")
PREPARERS = {"prep-subject": prepare_prep_subject_job, "generate-chunks": prepare_generate_chunks_job,
             "generate-docx": prepare_generate_docx_job}


class SyntheticComposedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.project = self.root / "project"
        self.fixtures = self.root / "fixtures"
        shutil.copytree(FIXTURES, self.fixtures)
        # Output transfers need publishable chapters. The original disabled
        # Marathi split stays in the resolver matrix; this disposable fixture
        # supplies the independent Marathi regex success/failure example.
        path = self.fixtures / "subjects/unicode-bilingual.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["editions"]["mr-IN"]["chapter_split"] = {
            "enabled": True, "pattern_type": "regex", "pattern": "^मराठी प्रबोधन [१२]$", "flags": ["MULTILINE"],
        }
        path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        write_catalog(self.project, fixture_root=self.fixtures)
        self.catalog = ComponentCatalog(self.project, resource_root=self.project)
        self.enterContext(synthetic_source_fonts())
        self.enterContext(patch("socket.socket", side_effect=AssertionError("network forbidden")))
        self.enterContext(patch("time.sleep", side_effect=AssertionError("real sleeps forbidden")))
        self.source_bytes = {}

    def pair(self, command, manifest, locale, route, root):
        explicit = PREPARERS[command](job_payload(command, root=root, manifest_id=manifest,
            locale=locale, storage_profile_id=route, fixture_root=self.fixtures))
        composed = resolve_job(self.catalog, command=command, manifest_id=manifest, locale=locale,
            environment_id="development", storage_profile_id=route, environ={
                "GURUBODH_SOURCE_LIBRARY_ROOT": str(root / "source"),
                "GURUBODH_CMS_LIBRARY_ROOT": str(root / "artifacts"),
            }).job
        self.assertEqual(explicit.to_payload(), composed.to_payload())
        self.assertEqual(explicit.locale, composed.locale)
        self.assertIsNone(explicit.provenance)
        self.assertEqual(composed.provenance.input_mode, "composition")
        self.assertEqual(destination_artifact_reference(explicit, Path("example.txt")),
                         destination_artifact_reference(composed, Path("example.txt")))
        if command == "prep-subject":
            self.assertEqual(explicit.proofreading_settings, composed.proofreading_settings)
            self.assertEqual(explicit.compiled_chapter_pattern, composed.compiled_chapter_pattern)
            self.assertEqual(source_reference(explicit), source_reference(composed))
            self.assertEqual(compatibility_record(explicit, "a" * 64), compatibility_record(composed, "a" * 64))
            if locale == "mr-IN":
                self.assertIsNotNone(composed.compiled_chapter_pattern.search("मराठी प्रबोधन १\nपाठ।"))
                self.assertIsNone(composed.compiled_chapter_pattern.search("प्रबोधन 1\nपाठ।"))
        elif command == "generate-chunks":
            self.assertEqual(explicit.semantic_chunk_config, composed.semantic_chunk_config)
        return explicit, composed

    def source_document(self, job, client):
        language = job.locale.language
        # Explicit fixture expectations, independent of resolver outputs.
        texts = (["प्रबोधन 1\nपहला सही पाठ।", "प्रबोधन 2\nदूसरा सही पाठ।"] if language == "hi-IN" else
                 ["मराठी प्रबोधन १\nपहिला बरोबर पाठ।", "मराठी प्रबोधन २\nदुसरा बरोबर पाठ।"])
        key = tuple(texts)
        if key not in self.source_bytes:
            paragraphs = "".join(
                '<w:p><w:r><w:rPr><w:rFonts w:ascii="Mangal" /></w:rPr>'
                f'<w:t>{line}</w:t></w:r></w:p>' for text in texts for line in text.splitlines())
            path = self.root / "source.docx"
            write_docx(path, '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                       f'<w:body>{paragraphs}</w:body></w:document>')
            self.source_bytes[key] = path.read_bytes()
        content = self.source_bytes[key]
        if job["source"]["backend"] == "r2":
            client.objects[job["source"]["key"]] = content
        else:
            path = Path(job["source"]["root_dir"]) / job["source"]["relative_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return texts

    def prep(self, job, texts, client):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), \
             patch("gurubodh.proofreading.artifacts.utc_now", return_value="2026-10-05T00:00:00Z"):
            # This transfer exercises font parsing, splitting, checkpointing and
            # publication; APS conversion golden/runtime tests retain conversion.
            run_resumable_prep_job(job, "Synthetic workflow", False, False, prepare_unicode,
                                  proofreader=FakeProofreader(texts), r2_client=client)

    def files(self, job, client):
        destination = job["destination"]
        if destination["backend"] == "r2":
            prefix = f"{destination['prefix']}/{destination['subject_dir']}/"
            return {key.removeprefix(prefix): value for key, value in client.objects.items() if key.startswith(prefix)}
        subject = Path(destination["root_dir"]) / destination["subject_dir"]
        return {path.relative_to(subject).as_posix(): path.read_bytes() for path in subject.rglob("*") if path.is_file()}

    def reference_name(self, reference, job):
        self.assertEqual(reference["backend"], job["destination"]["backend"])
        if reference["backend"] == "local":
            return reference["path"]
        self.assertEqual(reference["bucket"], "gurubodh-library-dev")
        prefix = f"{job['destination']['prefix']}/{job['destination']['subject_dir']}/"
        self.assertTrue(reference["key"].startswith(prefix))
        return reference["key"].removeprefix(prefix)

    def canonical_files(self, files):
        return {name: value for name, value in files.items() if name.startswith("chapters/text_and_metadata/")
                or name == "chapters/chapter_content_manifest.json"}

    def assert_canonical(self, files, texts, job):
        canonical = self.canonical_files(files)
        actual_texts = {name: value for name, value in canonical.items() if name.endswith(".txt")}
        self.assertEqual(len(actual_texts), len(texts))
        self.assertEqual(sorted(value.decode("utf-8") for value in actual_texts.values()),
                         sorted(text + "\n" for text in texts))
        manifest = json.loads(canonical["chapters/chapter_content_manifest.json"])
        validate_artifact(manifest, "chapter content manifest")
        self.assertEqual([c["generated_chapter_number"] for c in manifest["chapters"]],
                         [f"{n:03d}" for n in range(1, len(texts) + 1)])
        for chapter in manifest["chapters"]:
            text_name = self.reference_name(chapter["text_artifact"], job)
            metadata_name = self.reference_name(chapter["metadata_artifact"], job)
            metadata = json.loads(canonical[metadata_name])
            validate_artifact(metadata, "chapter metadata")
            self.assertEqual(metadata["document"]["language"], job.locale.language)
            self.assertEqual(metadata["integrity"]["artifacts"]["text"]["value"],
                             hashlib.sha256(canonical[text_name]).hexdigest())
            identity = metadata["content_identity"]
            self.assertEqual(identity["normalized_content_sha256"],
                             hashlib.sha256(canonical[text_name].decode("utf-8").strip().encode("utf-8")).hexdigest())
            self.assertEqual(chapter["content_key"], identity["content_key"])
            self.assertEqual(chapter["normalized_content_sha256"], identity["normalized_content_sha256"])
        return canonical

    def reports(self, files, command):
        reports = [json.loads(value) for name, value in files.items()
                   if name.startswith(f"run_reports/{command}/") and name.endswith(".json")]
        self.assertTrue(reports)
        for report in reports:
            validate_artifact(report, "audit report")
        return reports

    def test_prep_inputs_preserve_canonical_contract(self):
        for manifest, locale in EDITIONS:
            for route in ROUTES:
                with self.subTest(manifest=manifest, locale=locale, route=route):
                    outputs, summaries = [], []
                    for mode in (0, 1):
                        root = self.root / f"{manifest}-{locale}-{route}"
                        # Fresh storage at an identical logical address retains
                        # exact absolute-path contracts in readiness manifests.
                        shutil.rmtree(root, ignore_errors=True)
                        job = self.pair("prep-subject", manifest, locale, route, root)[mode]
                        client = FakeR2Client()
                        texts = self.source_document(job, client)
                        self.prep(job, texts, client)
                        files = self.files(job, client)
                        outputs.append(self.assert_canonical(files, texts, job))
                        report, = self.reports(files, "prep-subject")
                        self.assertEqual(report["run_identity"]["status"], "succeeded")
                        self.assertEqual(report["configuration_provenance"]["input_mode"],
                                         "in_memory" if mode == 0 else "composition")
                        summaries.append({key: report[key] for key in
                                          ("processing_summary", "lifecycle", "publication", "command_details")})
                    self.assertEqual(outputs[0], outputs[1])
                    self.assertEqual(summaries[0], summaries[1])

    def test_derived_inputs_preserve_output_and_lifecycle_contract(self):
        for manifest, locale in EDITIONS:
            for route in ROUTES:
                for command, runner in (("generate-chunks", run_generate_chunks_job),
                                        ("generate-docx", run_generate_docx_job)):
                    with self.subTest(manifest=manifest, locale=locale, route=route, command=command):
                        outputs, summaries = [], []
                        for mode in (0, 1):
                            root = self.root / f"{manifest}-{locale}-{route}-{command}"
                            shutil.rmtree(root, ignore_errors=True)
                            client = FakeR2Client()
                            # Mixed routing consumes local canonical artifacts.
                            seed = self.pair("prep-subject", manifest, locale,
                                             "r2" if route == "r2" else "local", root)[mode]
                            texts = self.source_document(seed, client)
                            self.prep(seed, texts, client)
                            canonical = self.assert_canonical(self.files(seed, client), texts, seed)
                            job = self.pair(command, manifest, locale, route, root)[mode]
                            options = {"segmenter": FakeSegmenter()} if command == "generate-chunks" else {}
                            context = SimpleNamespace(root=self.project)
                            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), \
                                 patch("zipfile.time.localtime", return_value=time.struct_time((2026, 10, 5, 0, 0, 0, 0, 278, 0))), \
                                 patch("gurubodh.pipelines.generate_docx.utc_now", return_value="2026-10-05T00:00:00Z"):
                                runner(context, job, r2_client=client, **options)
                                before = self.files(job, client)
                                with self.assertRaises(GurubodhError):
                                    runner(context, job, r2_client=client, **options)
                                after = self.files(job, client)
                                self.assertEqual({k: v for k, v in before.items() if not k.startswith("run_reports/")},
                                                 {k: v for k, v in after.items() if not k.startswith("run_reports/")})
                                runner(context, job, overwrite=True, r2_client=client, **options)
                            files = self.files(job, client)
                            self.assertEqual(canonical, self.assert_canonical(self.files(seed, client), texts, seed))
                            prefix = "chapters/semantic_chunks/" if command == "generate-chunks" else "chapters/msword/"
                            output = {name: value for name, value in files.items() if name.startswith(prefix)}
                            self.assertEqual(len(output), len(texts) + 1)
                            for name, value in output.items():
                                if name.endswith(".docx"):
                                    with zipfile.ZipFile(io.BytesIO(value)) as archive:
                                        xml = ElementTree.fromstring(archive.read("word/document.xml"))
                                        document_text = "\n".join(node.text or "" for node in xml.iter(
                                            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
                                        self.assertTrue(any(text in document_text for text in texts))
                                        output[name] = {member: archive.read(member) for member in archive.namelist()}
                                elif name.endswith("_manifest.json"):
                                    readiness = json.loads(value)
                                    validate_artifact(readiness, "semantic chunks manifest" if command == "generate-chunks"
                                                      else "DOCX manifest")
                                    self.assertEqual(len(readiness["chapters"]), len(texts))
                                    self.assertEqual(readiness["source_candidate_manifest"]["sha256"],
                                        hashlib.sha256(canonical["chapters/chapter_content_manifest.json"]).hexdigest())
                                    for chapter in readiness["chapters"]:
                                        artifact = chapter["chunk_artifact" if command == "generate-chunks" else "docx_artifact"]
                                        checksum = chapter["chunk_artifact_sha256" if command == "generate-chunks" else "docx_sha256"]
                                        self.assertEqual(checksum, hashlib.sha256(files[self.reference_name(artifact, job)]).hexdigest())
                                    for reference in readiness.get("audit_reports", {}).values():
                                        self.assertIn(self.reference_name(reference, job), files)
                                    readiness.pop("audit_reports", None)
                                    output[name] = readiness
                                elif name.endswith(".json"):
                                    chunks = json.loads(value)
                                    validate_artifact(chunks, "semantic chunks")
                                    expected = texts[int(chunks["document"]["chapter_number"]) - 1]
                                    self.assertEqual([chunk["text"] for chunk in chunks["chunks"]], [expected])
                                    self.assertEqual(chunks["chunks"][0]["chunk_text_sha256"],
                                                     hashlib.sha256(expected.encode("utf-8")).hexdigest())
                            outputs.append(output)
                            reports = self.reports(files, command)
                            self.assertEqual(len(reports), 3)
                            self.assertEqual({r["run_identity"]["status"] for r in reports}, {"succeeded", "failed"})
                            self.assertEqual({r["configuration_provenance"]["input_mode"] for r in reports},
                                             {"in_memory" if mode == 0 else "composition"})
                            summaries.append(sorted((r["run_identity"]["status"], r["run_identity"]["overwrite"],
                                r["lifecycle"]["current_state"], tuple(t["state"] for t in r["lifecycle"]["transitions"]))
                                for r in reports))
                        self.assertEqual(outputs[0], outputs[1])
                        self.assertEqual(summaries[0], summaries[1])


if __name__ == "__main__":
    unittest.main()
