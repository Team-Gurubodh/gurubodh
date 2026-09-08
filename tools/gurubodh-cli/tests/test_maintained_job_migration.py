"""#288 Stage A: independent legacy snapshots and maintained selector parity."""

from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
import copy
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

from component_contract_cases import without_job_schemas
from gurubodh.cli import main
from gurubodh.config import load_generate_chunks_job, load_generate_docx_job, load_prep_subject_job
from gurubodh.errors import ConfigurationError, GurubodhError
from gurubodh.job_components import ComponentCatalog
from gurubodh.job_composition import resolve_job
from gurubodh.pipelines.generate_chunks import run_generate_chunks_job
from gurubodh.pipelines.generate_docx import run_generate_docx_job
from gurubodh.prep_checkpoint import compatibility_record
from gurubodh.prep_subject_checkpoints import JOB_STATE_RELATIVE_PATH, run_resumable_prep_job
from gurubodh.proofreading import ProofreadingError
from gurubodh.schema_validation import validate_artifact
from gurubodh.storage import destination_artifact_reference, source_reference
from test_generate_chunks_pipeline import FakeSegmenter
from test_prep_subject_checkpoints import FakeProofreader, FakeR2Client, prepare_unicode, write_docx

CLI_ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((CLI_ROOT / "tests/fixtures/maintained-jobs-stage-a.json").read_text())
CASES = BASELINE["jobs"]
LOADERS = {"prep-subject": load_prep_subject_job, "generate-chunks": load_generate_chunks_job,
           "generate-docx": load_generate_docx_job}
R2_SOURCE_URL_DIFFERENCES = {
    "jobs/subjects/sub039_aacharan_shastra/hi-IN/prep-subject.r2.json",
    "jobs/subjects/sub123_spand_rahasya/hi-IN/prep-subject.r2.json",
}


def configuration_differences(legacy, composed, path="$"):
    """Report exact differences; never erase undeclared representation changes."""
    if isinstance(legacy, dict) and isinstance(composed, dict):
        differences = {}
        for key in sorted(legacy.keys() | composed.keys()):
            location = path + "." + key
            if key not in legacy or key not in composed:
                differences[location] = {
                    "legacy": {"present": True, "value": legacy[key]} if key in legacy else {"present": False},
                    "composed": {"present": True, "value": composed[key]} if key in composed else {"present": False},
                }
            else:
                differences.update(configuration_differences(legacy[key], composed[key], location))
        return differences
    return {} if legacy == composed else {path: {"legacy": legacy, "composed": composed}}


def bind_roots(payload, environ):
    payload = copy.deepcopy(payload)
    for side in ("source", "destination"):
        if "root_dir" in payload[side]:
            payload[side]["root_dir"] = environ["GURUBODH_" + payload[side]["root_dir"]]
    return payload


def normalize(payload):
    # No model, policy, identity, source/key, release or artifact normalization.
    payload = copy.deepcopy(payload)
    for side in ("source", "destination"):
        payload[side].setdefault("backend", "local")
    split = payload.get("chapter_split", {})
    if split.get("pattern_type") == "regex":
        split["flags"] = sorted(set(split.get("flags", [])))
    return payload


class MaintainedJobMigrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.environ = {"GURUBODH_SOURCE_LIBRARY_ROOT": str(self.root / "source"),
                        "GURUBODH_CMS_LIBRARY_ROOT": str(self.root / "artifacts")}
        self.catalog = ComponentCatalog(CLI_ROOT)
        self.source_bytes = {}

    def pair(self, case):
        s = case["selectors"]
        path = self.root / "legacy.json"
        path.write_text(json.dumps(bind_roots(case["configuration"], self.environ), ensure_ascii=False))
        old = LOADERS[s["command"]](path)
        new = resolve_job(self.catalog, command=s["command"], manifest_id=s["subject"],
            locale=s["language"], environment_id=s["environment"],
            storage_profile_id=s["storage_profile"], environ=self.environ).job
        return old, new

    def test_inventory_snapshot_and_legacy_files_are_complete_and_unchanged(self):
        paths = {p.relative_to(CLI_ROOT).as_posix()
                 for p in (CLI_ROOT / "jobs/subjects").glob("*/*/*.json")}
        self.assertEqual(paths, {c["legacy_path"] for c in CASES})
        self.assertEqual(len(CASES), 26)
        self.assertEqual(Counter(c["selectors"]["command"] for c in CASES),
                         {"prep-subject": 11, "generate-chunks": 9, "generate-docx": 6})
        self.assertEqual(Counter((c["selectors"]["subject"], c["selectors"]["language"]) for c in CASES), {
            ("sub039_aacharan_shastra", "hi-IN"): 6, ("sub039_test_aps_font", "hi-IN"): 4,
            ("sub123_spand_rahasya", "hi-IN"): 9, ("sub123_spand_rahasya", "mr-IN"): 3,
            ("sub123_test_unicode_font", "hi-IN"): 4,
        })
        for case in CASES:
            with self.subTest(path=case["legacy_path"]):
                path = CLI_ROOT / case["legacy_path"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), case["legacy_sha256"])
                payload = json.loads(path.read_text())
                s = case["selectors"]
                self.assertEqual(payload["schema_version"], {
                    "prep-subject": "1.5.0", "generate-chunks": "1.2.0", "generate-docx": "1.0.0",
                }[s["command"]])
                for side in ("source", "destination"):
                    if "root_dir" in payload[side]:
                        payload[side]["root_dir"] = ("SOURCE_LIBRARY_ROOT"
                            if s["command"] == "prep-subject" and side == "source" else "CMS_LIBRARY_ROOT")
                self.assertEqual(payload, case["configuration"])
                self.assertEqual(Path(case["legacy_path"]).parts[-3:],
                    (s["subject"], s["language"], f"{s['command']}.{s['storage_profile']}.json"))

    def test_manifests_validate_independently(self):
        paths = sorted((CLI_ROOT / "jobs/subjects").glob("*/manifest.json"))
        self.assertEqual(len(paths), 4)
        with without_job_schemas():
            for path in paths:
                manifest = self.catalog.load("subject-manifest", path.parent.name).to_payload()
                self.assertNotIn("profile_overrides", manifest)
                self.assertNotIn("/Users/", path.read_text())
                for edition in manifest["editions"].values():
                    self.assertNotIn("profile_overrides", edition)
                target = self.root / path.relative_to(CLI_ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                for mutate in (lambda m: m.pop("artifact_root"), lambda m: m.update(unknown=True),
                               lambda m: m["editions"]["hi-IN"]["source_document"].update(relative_path="../escape.docx")):
                    invalid = copy.deepcopy(manifest)
                    mutate(invalid)
                    target.write_text(json.dumps(invalid))
                    with self.assertRaises(ConfigurationError):
                        ComponentCatalog(self.root).load("subject-manifest", manifest["manifest_id"])

    def test_manifests_preserve_every_legacy_edition(self):
        # The immutable baseline owns legacy parity; valid additional editions
        # have no legacy counterpart and must not be added to that snapshot.
        for case in CASES:
            selectors = case["selectors"]
            if selectors["command"] != "prep-subject" or selectors["storage_profile"] != "local":
                continue
            with self.subTest(subject=selectors["subject"], locale=selectors["language"]):
                manifest = self.catalog.load("subject-manifest", selectors["subject"]).to_payload()
                edition = manifest["editions"][selectors["language"]]
                old = case["configuration"]
                self.assertEqual(manifest["artifact_root"] + "/" + selectors["language"],
                                 old["destination"]["subject_dir"])
                self.assertEqual(manifest["identity"], {k: old["naming"][k] for k in
                                                     ("category_code", "subject_code", "title_slug")})
                self.assertEqual(edition["release"], {k: old["naming"][k] for k in ("version", "subversion")})
                self.assertEqual(edition["source_document"], {k: old["source"][k] for k in
                                                           ("relative_path", "font_encoding", "file_format")})
                self.assertEqual(edition["chapter_split"], normalize(old)["chapter_split"])

    def test_marathi_unicode_test_edition_resolves_across_storage_profiles(self):
        relative = "123_test_unicode_font/unicode_fonts/ms_word/sub123_spand_rahasya_mr-IN.docx"
        for route in ("local", "r2-output", "r2"):
            with self.subTest(route=route):
                job = resolve_job(self.catalog, command="prep-subject",
                    manifest_id="sub123_test_unicode_font", locale="mr-IN",
                    environment_id="development", storage_profile_id=route, environ=self.environ).job
                payload = job.to_payload()
                self.assertEqual(job.locale.language, "mr-IN")
                self.assertEqual(payload["pipeline"], "unicode-docx-ingest")
                self.assertEqual(payload["source"]["font_encoding"], "unicode")
                self.assertEqual(payload["source"]["file_format"], "docx")
                if route == "r2":
                    self.assertEqual(payload["source"]["backend"], "r2")
                    self.assertEqual(payload["source"]["key"], "source_library/" + relative)
                else:
                    self.assertEqual(payload["source"]["backend"], "local")
                    self.assertEqual(payload["source"]["root_dir"], self.environ["GURUBODH_SOURCE_LIBRARY_ROOT"])
                    self.assertEqual(payload["source"]["relative_path"], relative)
                self.assertEqual(payload["destination"]["backend"], "local" if route == "local" else "r2")
                self.assertEqual(payload["destination"]["subject_dir"], "123_test_unicode_font/mr-IN")
                self.assertEqual(payload["naming"], {
                    "category_code": "CAT001", "subject_code": "SUB123", "title_slug": "spand-rahasya",
                    "version": "01", "subversion": "01",
                })
                self.assertEqual(payload["chapter_split"], {
                    "enabled": True, "pattern_type": "regex",
                    "pattern": "स्पंद रहस्य.*?जानेवारी.*?2026", "flags": [],
                })
                self.assertIsNotNone(job.compiled_chapter_pattern.search("स्पंद रहस्य जानेवारी 2026"))
                self.assertIsNone(job.compiled_chapter_pattern.search("प्रबोधन जनवरी 2026"))

    def test_all_26_pairs_through_real_preparation_boundaries_report_exact_differences(self):
        for case in CASES:
            with self.subTest(path=case["legacy_path"]):
                old, new = self.pair(case)
                differences = configuration_differences(normalize(old.to_payload()), normalize(new.to_payload()))
                # #288 does not permit normalizing source.url_base. Retain and
                # report this difference for maintainer review in these two
                # cases, while rejecting any other difference in any field.
                expected = {"$.source.url_base": {
                    "legacy": {"present": False}, "composed": {"present": True, "value": None},
                }} if case["legacy_path"] in R2_SOURCE_URL_DIFFERENCES else {}
                self.assertEqual(differences, expected)
                self.assertEqual(old.locale, new.locale)
                self.assertEqual(destination_artifact_reference(old, Path("example.txt")),
                                 destination_artifact_reference(new, Path("example.txt")))
                self.assertIsNone(old.provenance)
                self.assertEqual(new.provenance.input_mode, "composition")
                self.assertNotIn("configuration_provenance", new.to_payload())
                if case["selectors"]["command"] == "prep-subject":
                    self.assertEqual(old.proofreading_settings, new.proofreading_settings)
                    self.assertEqual(old.compiled_chapter_pattern, new.compiled_chapter_pattern)
                    self.assertEqual(source_reference(old), source_reference(new))
                    self.assertEqual(compatibility_record(old, "a" * 64), compatibility_record(new, "a" * 64))
                elif case["selectors"]["command"] == "generate-chunks":
                    self.assertEqual(old.semantic_chunk_config, new.semantic_chunk_config)

    def test_all_26_maintained_selectors_inspect_via_cli(self):
        for case in CASES:
            s = case["selectors"]
            stdout, stderr = io.StringIO(), io.StringIO()
            arguments = ["config", "resolve", "--command", s["command"],
                         "--project-root", str(CLI_ROOT), "--provenance"]
            for option in ("subject", "language", "environment", "storage_profile"):
                arguments.extend(["--" + option.replace("_", "-"), s[option]])
            with self.subTest(path=case["legacy_path"]), patch.dict("os.environ", self.environ, clear=True), \
                 redirect_stdout(stdout), redirect_stderr(stderr):
                main(arguments)
                self.assertEqual(json.loads(stdout.getvalue()), self.pair(case)[1].to_payload())
                self.assertEqual(json.loads(stderr.getvalue())["manifest_id"], s["subject"])

    def source_document(self, job, client):
        # Fake conversion uses synthetic Unicode bytes, preserving all maintained
        # split settings and crossing real font/split/checkpoint/publication APIs.
        if job["source"]["font_encoding"] == "aps":
            title = "प्रबोधन क्र"
        elif job["metadata_defaults"]["language"] == "mr-IN":
            title = "स्पंद रहस्य जानेवारी 2026"
        else:
            title = "प्रबोधन जनवरी 2026"
        texts = [f"{title} {n}\nपाठ सही है।" for n in (1, 2)]
        paragraphs = "".join(f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>"
                             for text in texts for line in text.splitlines())
        xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
               f'<w:body>{paragraphs}</w:body></w:document>')
        path = self.root / "synthetic.docx"
        if title not in self.source_bytes:
            write_docx(path, xml)
            self.source_bytes[title] = path.read_bytes()
        else:
            path.write_bytes(self.source_bytes[title])
        if job["source"].get("backend", "local") == "r2":
            client.objects[job["source"]["key"]] = path.read_bytes()
        else:
            target = Path(job["source"]["root_dir"]) / job["source"]["relative_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        return texts

    def files(self, job, client):
        if job["destination"].get("backend", "local") == "r2":
            prefix = job["destination"]["prefix"] + "/" + job["destination"]["subject_dir"] + "/"
            return {key.removeprefix(prefix): value for key, value in client.objects.items()
                    if key.startswith(prefix)}
        subject = Path(job["destination"]["root_dir"]) / job["destination"]["subject_dir"]
        return {path.relative_to(subject).as_posix(): path.read_bytes()
                for path in subject.rglob("*") if path.is_file()}

    def reports(self, files, command):
        reports = [json.loads(value) for name, value in files.items()
                   if name.startswith(f"run_reports/{command}/") and name.endswith(".json")]
        self.assertTrue(reports)
        for report in reports:
            validate_artifact(report, "audit report")
        return reports

    def prep(self, job, texts, client, *, overwrite=False, resume=False, outcomes=None):
        reader = FakeProofreader(texts if outcomes is None else outcomes)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            run_resumable_prep_job(job, "Stage A comparison", overwrite, resume,
                None if job.provenance else self.root / "legacy.json", prepare_unicode,
                proofreader=reader, r2_client=client)
        return reader

    def test_all_11_prep_jobs_resume_across_modes_and_invalidate_derived_outputs(self):
        for case in CASES:
            if case["selectors"]["command"] != "prep-subject":
                continue
            for composed_first in (False, True):
                with self.subTest(path=case["legacy_path"], composed_first=composed_first):
                    shutil.rmtree(self.environ["GURUBODH_CMS_LIBRARY_ROOT"], ignore_errors=True)
                    old, new = self.pair(case)
                    client = FakeR2Client()
                    texts = self.source_document(new, client)
                    first, resumed = (new, old) if composed_first else (old, new)
                    sentinels = ["chapters/semantic_chunks/stale.json", "chapters/msword/stale.docx"]
                    for name in sentinels:
                        if new["destination"]["backend"] == "r2":
                            client.objects[f"cms_library/{new['destination']['subject_dir']}/{name}"] = b"stale"
                        else:
                            path = Path(new["destination"]["root_dir"]) / new["destination"]["subject_dir"] / name
                            path.parent.mkdir(parents=True, exist_ok=True)
                            path.write_bytes(b"stale")
                    failure = ProofreadingError("api_error", "deterministic interruption", retryable=True)
                    with self.assertRaisesRegex(GurubodhError, "incomplete"):
                        self.prep(first, texts, client, overwrite=True, outcomes=[texts[0], failure])
                    self.assertTrue(all(name in self.files(new, client) for name in sentinels))
                    reader = self.prep(resumed, texts, client, resume=True, outcomes=[texts[1]])
                    self.assertEqual(len(reader.calls), 1)
                    files = self.files(new, client)
                    self.assertTrue(all(name not in files for name in sentinels))
                    state = json.loads(files[JOB_STATE_RELATIVE_PATH.as_posix()])
                    self.assertEqual(state["state"], "succeeded")
                    self.assertTrue(state["replacement_authorized"])
                    reports = self.reports(files, "prep-subject")
                    self.assertEqual({r["run_identity"]["status"] for r in reports}, {"incomplete", "succeeded"})
                    self.assertEqual({r["configuration_provenance"]["input_mode"] for r in reports},
                                     {"complete_config", "composition"})
                    canonical = {name: value for name, value in files.items()
                                 if name.startswith("chapters/text_and_metadata/") and name.endswith(".txt")}
                    self.assertEqual(len(canonical), 2)
                    for value in canonical.values():
                        self.assertIn(value.decode().strip(), texts)

    def canonical_files(self, files):
        return {name: value for name, value in files.items()
                if name.startswith("chapters/text_and_metadata/")
                or name == "chapters/chapter_content_manifest.json"}

    def test_all_11_prep_pairs_publish_identical_canonical_text_identity_and_metadata(self):
        for case in CASES:
            if case["selectors"]["command"] != "prep-subject":
                continue
            with self.subTest(path=case["legacy_path"]):
                outputs, summaries = [], []
                for job in self.pair(case):
                    shutil.rmtree(self.environ["GURUBODH_CMS_LIBRARY_ROOT"], ignore_errors=True)
                    client = FakeR2Client()
                    texts = self.source_document(job, client)
                    # Make artifact time deterministic instead of dropping any
                    # metadata, integrity hashes or canonical manifest fields.
                    with patch("gurubodh.proofreading.artifacts.utc_now", return_value="2026-09-08T00:00:00Z"):
                        self.prep(job, texts, client)
                    files = self.files(job, client)
                    outputs.append(self.canonical_files(files))
                    report = self.reports(files, "prep-subject")[0]
                    self.assertEqual(report["run_identity"]["status"], "succeeded")
                    summaries.append({key: report[key] for key in
                                      ("processing_summary", "lifecycle", "publication", "command_details")})
                self.assertTrue(outputs[0])
                self.assertEqual(outputs[0], outputs[1])
                self.assertEqual(summaries[0], summaries[1])

    def test_all_15_derived_pairs_preserve_canonical_and_match_outputs_and_lifecycle(self):
        import zipfile

        for case in CASES:
            s = case["selectors"]
            command = s["command"]
            if command == "prep-subject":
                continue
            with self.subTest(path=case["legacy_path"]):
                # r2-output consumes LOCAL canonical artifacts. Preparing only
                # its R2 destination would not make its downstream input ready.
                prep_case = next(c for c in CASES if c["selectors"] == {
                    **s, "command": "prep-subject",
                    "storage_profile": "r2" if s["storage_profile"] == "r2" else "local"})
                outputs, summaries = [], []
                for job in self.pair(case):
                    shutil.rmtree(self.environ["GURUBODH_CMS_LIBRARY_ROOT"], ignore_errors=True)
                    client = FakeR2Client()
                    seed = self.pair(prep_case)[0]
                    texts = self.source_document(seed, client)
                    with patch("gurubodh.proofreading.artifacts.utc_now", return_value="2026-09-08T00:00:00Z"):
                        self.prep(seed, texts, client)
                    canonical = self.canonical_files(self.files(seed, client))
                    runner = run_generate_chunks_job if command == "generate-chunks" else run_generate_docx_job
                    options = {"segmenter": FakeSegmenter()} if command == "generate-chunks" else {}
                    context = SimpleNamespace(root=CLI_ROOT)
                    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), \
                         patch("zipfile.time.localtime", return_value=time.struct_time((2026, 9, 8, 0, 0, 0, 1, 251, 0))), \
                         patch("gurubodh.pipelines.generate_docx.utc_now", return_value="2026-09-08T00:00:00Z"):
                        runner(context, job, r2_client=client, **options)
                        before = self.files(job, client)
                        with self.assertRaises(GurubodhError):
                            runner(context, job, r2_client=client, **options)
                        after = self.files(job, client)
                        # Refusal to overwrite preserves every published byte.
                        self.assertEqual({k: v for k, v in before.items() if not k.startswith("run_reports/")},
                                         {k: v for k, v in after.items() if not k.startswith("run_reports/")})
                        runner(context, job, overwrite=True, r2_client=client, **options)
                    files = self.files(job, client)
                    self.assertEqual(canonical, self.canonical_files(self.files(seed, client)))
                    prefix = "chapters/semantic_chunks/" if command == "generate-chunks" else "chapters/msword/"
                    output = {name: value for name, value in files.items() if name.startswith(prefix)}
                    self.assertTrue(output)
                    self.assertEqual(len(output), 3)  # two chapters plus readiness manifest
                    # Compare every uncompressed DOCX member, excluding only ZIP
                    # container timestamps. Chunk JSON and manifests stay exact.
                    for name, value in output.items():
                        if name.endswith(".docx"):
                            with zipfile.ZipFile(io.BytesIO(value)) as archive:
                                output[name] = {member: archive.read(member) for member in archive.namelist()}
                        elif name.endswith("semantic_chunks_manifest.json"):
                            manifest = json.loads(value)
                            # Run-specific report names are expected to differ;
                            # prove that every reference resolves before comparing
                            # all remaining readiness/output contract fields.
                            for reference in manifest["audit_reports"].values():
                                relative = reference.get("path") or reference["key"].removeprefix(
                                    f"cms_library/{job['destination']['subject_dir']}/")
                                self.assertIn(relative, files)
                            del manifest["audit_reports"]
                            output[name] = manifest
                    outputs.append(output)
                    reports = self.reports(files, command)
                    self.assertEqual(len(reports), 3)
                    self.assertEqual({r["run_identity"]["status"] for r in reports}, {"succeeded", "failed"})
                    self.assertEqual({r["configuration_provenance"]["input_mode"] for r in reports},
                                     {"composition" if job.provenance else "complete_config"})
                    summaries.append(sorted((r["run_identity"]["status"], r["run_identity"]["overwrite"],
                        r["lifecycle"]["current_state"], tuple(t["state"] for t in r["lifecycle"]["transitions"]))
                        for r in reports))
                self.assertEqual(outputs[0], outputs[1])
                self.assertEqual(summaries[0], summaries[1])
