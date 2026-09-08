"""Production resolution against independent fixtures and real preparation APIs."""

from contextlib import ExitStack
from dataclasses import FrozenInstanceError, fields
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from component_contract_cases import without_job_schemas
from gurubodh.config import (
    load_generate_chunks_job, load_generate_docx_job, load_prep_subject_job,
)
from gurubodh.contracts import GenerateChunksJob, GenerateDocxJob, PrepSubjectJob
from gurubodh.errors import ConfigurationError
from gurubodh.job_components import ComponentCatalog
from gurubodh.job_composition import resolve_job, resolve_lab_proofreading
from gurubodh.ml.semantic_chunking.chunker import SemanticChunker
from gurubodh.ml.semantic_chunking.config import SemanticChunkConfig
from gurubodh.prep_checkpoint import compatibility_record
from gurubodh.proofreading.settings import ProofreadingSettings


CLI_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = CLI_ROOT / "tests/fixtures/job-components"
KINDS = {
    "command-definition": "config/job-components/commands/prep-subject.json",
    "environment": "config/job-components/environments/development.json",
    "storage-profile": "config/job-components/storage-profiles/local.json",
    "locale-definition": "config/job-components/locales/hi-IN.json",
    "proofreading-profile": "config/job-components/profiles/proofreading/gemini-3.6-flash-v1.json",
    "chunking-profile": "config/job-components/profiles/chunking/bge-m3-semantic-window-v1.json",
    "subject-manifest": "jobs/subjects/sub001_aps_example/manifest.json",
}
IDENTITIES = {
    "command-definition": "prep-subject", "environment": "development",
    "storage-profile": "local", "locale-definition": "hi-IN",
    "proofreading-profile": "gemini-3.6-flash-v1",
    "chunking-profile": "bge-m3-semantic-window-v1", "subject-manifest": "sub001_aps_example",
}


class CompositionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        shutil.copytree(CLI_ROOT / "config/job-components", self.root / "config/job-components")
        for filename in ("aps-hindi", "unicode-bilingual"):
            document = json.loads((FIXTURES / f"subjects/{filename}.json").read_text())
            self.write(f"jobs/subjects/{document['manifest_id']}/manifest.json", document)
        alternate = self.read(KINDS["proofreading-profile"])
        alternate["profile_id"] = "example-proofreading-v2"
        self.write("config/job-components/profiles/proofreading/example-proofreading-v2.json", alternate)
        self.catalog = ComponentCatalog(self.root)
        self.environ = {"GURUBODH_SOURCE_LIBRARY_ROOT": str(self.root / "source"),
                        "GURUBODH_CMS_LIBRARY_ROOT": str(self.root / "artifacts")}

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def read(self, relative):
        return json.loads((self.root / relative).read_text(encoding="utf-8"))

    def resolve(self, **options):
        arguments = dict(command="prep-subject", manifest_id="sub001_aps_example", locale="hi-IN",
                         environment_id="development", storage_profile_id="local", environ=self.environ)
        arguments.update(options)
        return resolve_job(self.catalog, **arguments)

    def test_shared_catalog_matches_independent_declarations(self):
        expected = []
        for directory, kind in (("commands", "command-definition"), ("environments", "environment"),
                                ("storage-profiles", "storage-profile"), ("locales", "locale-definition")):
            expected.extend((kind, path.stem, path) for path in (FIXTURES / directory).glob("*.json"))
        expected.extend((kind + "-profile", identity, FIXTURES / kind / f"{identity}.json")
                        for kind, identity in (("proofreading", "gemini-3.6-flash-v1"),
                                               ("chunking", "bge-m3-semantic-window-v1")))
        self.assertEqual(len(expected), 12)
        with without_job_schemas():
            for kind, identity, path in expected:
                self.assertEqual(ComponentCatalog(CLI_ROOT).load(kind, identity).to_payload(),
                                 json.loads(path.read_text()))

    def test_every_loaded_kind_validates_without_job_schema_access(self):
        with without_job_schemas():
            for kind, relative in KINDS.items():
                with self.subTest(kind=kind):
                    before = (self.root / relative).read_bytes()
                    document = self.catalog.load(kind, IDENTITIES[kind]).to_payload()
                    for key in document:
                        invalid = copy.deepcopy(document)
                        del invalid[key]
                        self.write(relative, invalid)
                        with self.assertRaises(ConfigurationError):
                            self.catalog.load(kind, IDENTITIES[kind])
                    (self.root / relative).write_bytes(before)
                    self.assertEqual(self.catalog.load(kind, IDENTITIES[kind]).content, before)

    def test_command_route_edition_matrix(self):
        examples = (
            ("sub001_aps_example", "hi-IN", "aps", "library/aps_example/hi-IN",
             "001_aps/legacy fonts/प्रबोधन.docx", "SUB001", "aps-example", "01", "01"),
            ("sub123_spand_rahasya", "hi-IN", "unicode", "library/spand/hi-IN",
             "123_spand/unicode/hi-IN.docx", "SUB123", "spand-rahasya", "01", "02"),
            ("sub123_spand_rahasya", "mr-IN", "unicode", "library/spand/mr-IN",
             "123_spand/unicode/mr-IN.docx", "SUB123", "spand-rahasya", "03", "01"),
        )
        for manifest, locale, encoding, subject_dir, relative, subject, slug, version, subversion in examples:
            for route in ("local", "r2-output", "r2"):
                for command, job_type in (("prep-subject", PrepSubjectJob),
                                          ("generate-chunks", GenerateChunksJob),
                                          ("generate-docx", GenerateDocxJob)):
                    with self.subTest(manifest=manifest, locale=locale, route=route, command=command):
                        resolved = self.resolve(command=command, manifest_id=manifest,
                                                locale=locale, storage_profile_id=route)
                        self.assertIsInstance(resolved.job, job_type)
                        payload = resolved.job.to_payload()
                        source = ({"backend": "r2", "bucket": "gurubodh-library-dev", "url_base": None}
                                  if route == "r2" else {"backend": "local", "root_dir": self.environ[
                                      "GURUBODH_SOURCE_LIBRARY_ROOT" if command == "prep-subject"
                                      else "GURUBODH_CMS_LIBRARY_ROOT"]})
                        destination = ({"backend": "local", "root_dir": self.environ["GURUBODH_CMS_LIBRARY_ROOT"]}
                                       if route == "local" else {"backend": "r2", "bucket": "gurubodh-library-dev",
                                                                "url_base": None, "prefix": "cms_library"})
                        destination["subject_dir"] = subject_dir
                        names = {"category_code": "CAT001", "subject_code": subject, "title_slug": slug}
                        if command != "generate-docx":
                            names.update(version=version, subversion=subversion)
                        if command != "prep-subject":
                            names["language"] = locale
                            source["subject_dir"] = subject_dir
                            if route == "r2":
                                source["prefix"] = "cms_library"
                        else:
                            source.update(font_encoding=encoding, file_format="docx")
                            if route == "r2":
                                source["key"] = "source_library/" + relative
                            else:
                                source["relative_path"] = relative
                        expected = {
                            "schema_version": {"prep-subject": "1.5.0", "generate-chunks": "1.2.0",
                                               "generate-docx": "1.0.0"}[command],
                            "pipeline": ({"aps": "legacy-docx-to-unicode", "unicode": "unicode-docx-ingest"}[encoding]
                                         if command == "prep-subject" else command),
                            "source": source, "destination": destination, "naming": names,
                        }
                        if command == "prep-subject":
                            expected["proofreading"] = json.loads((FIXTURES / "proofreading/gemini-3.6-flash-v1.json").read_text())["proofreading"]
                            expected["chapter_split"] = (
                                {"enabled": True, "pattern_type": "literal", "pattern": "प्रबोधन"} if encoding == "aps" else
                                {"enabled": True, "pattern_type": "regex", "pattern": "^प्रबोधन", "flags": ["MULTILINE"]}
                                if locale == "hi-IN" else {"enabled": False})
                            expected["metadata_defaults"] = {
                                "language": locale, "source_script": "Devanagari", "output_text_encoding": "UTF-8",
                                "summary_chapter_markers": ["उपसंहार", "उपसंहारात्मक", "उपसंभारात्मक", "उपसंभारात्त्मक", "उपसंभार"],
                            }
                        elif command == "generate-chunks":
                            expected["chunking"] = json.loads((FIXTURES / "chunking/bge-m3-semantic-window-v1.json").read_text())["chunking"]
                        self.assertEqual(payload, expected)

    def test_whole_profile_precedence_and_no_partial_merge(self):
        for kind, command, field in (("proofreading", "prep-subject", "max_output_tokens"),
                                     ("chunking", "generate-chunks", "batch_size")):
            base = self.read(KINDS[f"{kind}-profile"])
            for identity, value in (("standard-v1", 32), ("careful-v1", 16),
                                    ("edition-v1", 8), ("review-v1", 4)):
                document = copy.deepcopy(base)
                document["profile_id"] = identity
                document[kind][field] = value
                self.write(f"config/job-components/profiles/{kind}/{identity}.json", document)
            command_path = f"config/job-components/commands/{command}.json"
            definition = self.read(command_path)
            definition["default_profiles"][kind] = "standard-v1"
            self.write(command_path, definition)
            for manifest_choice, edition_choice, invocation, expected, level in (
                (None, None, None, "standard-v1", "command"),
                ({}, {}, None, "standard-v1", "command"),
                ({kind: "careful-v1"}, {}, None, "careful-v1", "manifest"),
                ({kind: "careful-v1"}, {kind: "edition-v1"}, None, "edition-v1", "edition"),
                ({kind: "careful-v1"}, {kind: "edition-v1"}, "review-v1", "review-v1", "invocation"),
                (None, None, "review-v1", "review-v1", "invocation"),
            ):
                manifest = json.loads((FIXTURES / "subjects/aps-hindi.json").read_text())
                if manifest_choice is not None:
                    manifest["profile_overrides"] = manifest_choice
                if edition_choice is not None:
                    manifest["editions"]["hi-IN"]["profile_overrides"] = edition_choice
                self.write(KINDS["subject-manifest"], manifest)
                with self.subTest(kind=kind, expected=expected, level=level):
                    options = {"command": command, f"{kind}_profile_id": invocation}
                    result = self.resolve(**options)
                    self.assertEqual(result.inputs.profiles[0].profile_id, expected)
                    self.assertEqual(result.inputs.profiles[0].selected_by, level)
                    path = f"config/job-components/profiles/{kind}/{expected}.json"
                    selected = self.read(path)
                    self.assertEqual(result.job[kind], selected[kind])
                    for setting in selected[kind]:
                        incomplete = copy.deepcopy(selected)
                        del incomplete[kind][setting]
                        self.write(path, incomplete)
                        with self.assertRaises(ConfigurationError):
                            self.resolve(**options)
                    self.write(path, selected)

    def test_only_selected_applicable_profiles_are_loaded(self):
        manifest = self.read(KINDS["subject-manifest"])
        manifest["profile_overrides"] = {"proofreading": "absent-v1", "chunking": "absent-v1"}
        self.write(KINDS["subject-manifest"], manifest)
        self.resolve(command="generate-docx")
        self.resolve(proofreading_profile_id="gemini-3.6-flash-v1")
        with self.assertRaises(ConfigurationError):
            self.resolve()

    def test_invocation_chapters_and_irrelevant_options(self):
        result = self.resolve(command="generate-chunks", chapters=["012", "001"])
        self.assertEqual(result.job["chapters"], ["012", "001"])
        self.assertEqual(result.inputs.chapters, ("012", "001"))
        self.assertNotIn("chapters", self.resolve(command="generate-chunks").job)
        for value in ([], ["001", "001"], ["1"], ["0001"], ["001\n"], ["००१"], [1], "001", ("001",), [{}]):
            with self.subTest(value=value), self.assertRaises(ConfigurationError):
                self.resolve(command="generate-chunks", chapters=value)
        for options in ({"chapters": ["001"]}, {"chunking_profile_id": "bge-m3-semantic-window-v1"},
                        {"command": "generate-chunks", "proofreading_profile_id": "gemini-3.6-flash-v1"},
                        {"command": "generate-docx", "proofreading_profile_id": "gemini-3.6-flash-v1"},
                        {"proofreading_profile_id": {"max_retries": 1}}, {"command": "lab-proofread"}):
            with self.subTest(options=options), self.assertRaises(ConfigurationError):
                self.resolve(**options)
        with self.assertRaises(TypeError):
            self.resolve(max_retries=1)

    def test_only_consumed_stores_and_root_names_are_resolved(self):
        class NamedReadsOnly(dict):
            def __init__(self, values):
                super().__init__(values)
                self.reads = []

            def get(self, key):
                self.reads.append(key)
                if key not in self:
                    raise AssertionError("unused or credential environment read")
                return super().get(key)

            def __iter__(self):
                raise AssertionError("environment enumeration")

            def keys(self):
                raise AssertionError("environment enumeration")

        for command in ("prep-subject", "generate-chunks", "generate-docx"):
            env = NamedReadsOnly({})
            self.assertEqual(self.resolve(command=command, storage_profile_id="r2", environ=env).inputs.root_bindings, ())
            self.assertEqual(env.reads, [])
        for command, variable in (("prep-subject", "GURUBODH_SOURCE_LIBRARY_ROOT"),
                                   ("generate-chunks", "GURUBODH_CMS_LIBRARY_ROOT"),
                                   ("generate-docx", "GURUBODH_CMS_LIBRARY_ROOT")):
            env = NamedReadsOnly({variable: self.environ[variable]})
            self.resolve(command=command, storage_profile_id="r2-output", environ=env)
            self.assertEqual(env.reads, [variable])
        env = NamedReadsOnly({"GURUBODH_CMS_LIBRARY_ROOT": self.environ["GURUBODH_CMS_LIBRARY_ROOT"]})
        self.resolve(command="generate-docx", environ=env)
        self.assertEqual(env.reads, ["GURUBODH_CMS_LIBRARY_ROOT"])
        route = self.read(KINDS["storage-profile"])
        route["source_document"] = "absent_store"
        self.write(KINDS["storage-profile"], route)
        self.resolve(command="generate-docx")
        with self.assertRaisesRegex(ConfigurationError, r"source_document.*missing store.*absent_store"):
            self.resolve()

    def test_used_roots_fail_safely_and_unused_declarations_still_validate(self):
        for value in (None, "", "   ", "relative/SECRET", "~/SECRET", "/SECRET/$EXPANSION", "/SECRET\x00", "/SECRET\n"):
            env = dict(self.environ)
            if value is None:
                del env["GURUBODH_SOURCE_LIBRARY_ROOT"]
            else:
                env["GURUBODH_SOURCE_LIBRARY_ROOT"] = value
            with self.subTest(value=value), self.assertRaises(ConfigurationError) as caught:
                self.resolve(environ=env)
            error = str(caught.exception)
            self.assertIn("environments/development.json", error)
            self.assertIn("$.stores.local_source_library.root_dir", error)
            self.assertIn("GURUBODH_SOURCE_LIBRARY_ROOT", error)
            self.assertNotIn("SECRET", error)
        environment = self.read(KINDS["environment"])
        del environment["stores"]["local_source_library"]["root_dir"]
        self.write(KINDS["environment"], environment)
        with self.assertRaises(ConfigurationError):
            self.resolve(storage_profile_id="r2", environ={})

    def test_credentials_and_model_cache_are_not_library_root_bindings(self):
        environment = self.read(KINDS["environment"])
        for variable in ("GEMINI_API_KEY", "CLOUDFLARE_R2_ACCOUNT_ID", "CLOUDFLARE_R2_ACCESS_KEY_ID",
                         "CLOUDFLARE_R2_SECRET_ACCESS_KEY", "GURUBODH_MODEL_CACHE_DIR"):
            environment["stores"]["local_source_library"]["root_dir"]["$env"] = variable
            self.write(KINDS["environment"], environment)
            with self.assertRaisesRegex(ConfigurationError, "non-secret library root"):
                self.resolve(environ={variable: "/SECRET"})

    def test_lookup_rejects_unsafe_absent_and_wrong_resources(self):
        for kind in KINDS:
            for identity in ("../outside", "/absolute", "https://host", "name/part", "name\\part", "name\n", "", None):
                with self.subTest(kind=kind, identity=identity), self.assertRaises(ConfigurationError):
                    self.catalog.load(kind, identity)
            path = self.root / KINDS[kind]
            original = path.read_bytes()
            path.unlink()
            with self.assertRaises(ConfigurationError):
                self.catalog.load(kind, IDENTITIES[kind])
            path.mkdir()
            with self.assertRaises(ConfigurationError):
                self.catalog.load(kind, IDENTITIES[kind])
            path.rmdir()
            for content in (b'{"secret": ', b'\xff', b'{"secret": 1, "secret": 2}', b'null'):
                path.write_bytes(content)
                with self.assertRaises(ConfigurationError) as caught:
                    self.catalog.load(kind, IDENTITIES[kind])
                self.assertNotIn("secret", str(caught.exception))
            document = json.loads(original)
            document["component_schema_version"] = "2.0.0"
            self.write(KINDS[kind], document)
            with self.assertRaises(ConfigurationError):
                self.catalog.load(kind, IDENTITIES[kind])
            path.write_bytes(original)
        # Existing resource of another kind, and a same-kind resource with another ID.
        self.write(KINDS["proofreading-profile"], self.read(KINDS["chunking-profile"]))
        with self.assertRaises(ConfigurationError):
            self.catalog.load("proofreading-profile", "gemini-3.6-flash-v1")
        environment = self.read(KINDS["environment"])
        environment["environment_id"] = "another-environment"
        self.write(KINDS["environment"], environment)
        with self.assertRaisesRegex(ConfigurationError, "selected resource ID"):
            self.catalog.load("environment", "development")
        with self.assertRaises(ConfigurationError):
            self.catalog.load("unknown-kind", "anything")

    def test_symlink_escape_is_rejected_before_reading_target(self):
        with tempfile.TemporaryDirectory() as outside:
            for kind, relative in KINDS.items():
                path = self.root / relative
                content = path.read_bytes()
                external = Path(outside) / "input.json"
                external.write_bytes(content)
                path.unlink()
                path.symlink_to(external)
                with self.subTest(kind=kind), self.assertRaisesRegex(ConfigurationError, "fixed directory"):
                    self.catalog.load(kind, IDENTITIES[kind])
                path.unlink()
                path.write_bytes(content)
            directory = self.root / "config/job-components/environments"
            shutil.move(directory, Path(outside) / "environments")
            directory.symlink_to(Path(outside) / "environments", target_is_directory=True)
            with self.assertRaises(ConfigurationError):
                self.catalog.load("environment", "development")

    def test_missing_edition_and_unsafe_declared_paths_fail(self):
        with self.assertRaisesRegex(ConfigurationError, r"editions.mr-IN"):
            self.resolve(locale="mr-IN")
        for bad_path in ("../escape.docx", "/absolute.docx", "one//two.docx", "one/../two.docx", "one\\two.docx"):
            document = self.read(KINDS["subject-manifest"])
            document["editions"]["hi-IN"]["source_document"]["relative_path"] = bad_path
            self.write(KINDS["subject-manifest"], document)
            with self.assertRaises(ConfigurationError):
                self.resolve(storage_profile_id="r2")

    def test_resolution_has_no_execution_or_output_side_effects(self):
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        forbidden = [
            "gurubodh.storage.R2StorageClient.__init__", "gurubodh.storage.materialize_source",
            "gurubodh.proofreading.gemini.GeminiProofreader.__init__",
            "gurubodh.ml.embeddings.SentenceTransformerEmbeddingHelper.__init__",
            "gurubodh.ml.semantic_chunking.chunker.SemanticChunker.__init__",
            "gurubodh.prep_checkpoint.PrepCheckpointManager.__init__",
            "socket.socket", "subprocess.Popen",
        ]
        with ExitStack() as stack:
            for name in forbidden:
                stack.enter_context(patch(name, side_effect=AssertionError(name)))
            for name in ("mkdir", "write_text", "write_bytes", "unlink", "rename", "replace"):
                stack.enter_context(patch.object(Path, name, side_effect=AssertionError(name)))
            for command in ("prep-subject", "generate-chunks", "generate-docx"):
                for route in ("local", "r2-output", "r2"):
                    self.resolve(command=command, storage_profile_id=route)
            resolve_lab_proofreading(self.catalog)
            with self.assertRaises(ConfigurationError):
                self.resolve(environ={})
        after = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_resolution_inputs_are_immutable_and_never_reread(self):
        chapters = ["001"]
        first = self.resolve(command="generate-chunks", chapters=chapters)
        second = self.resolve(command="generate-chunks", chapters=chapters)
        self.assertEqual(first, second)
        before = first.job.to_payload()
        chapters.append("002")
        self.environ["GURUBODH_CMS_LIBRARY_ROOT"] = "/different"
        for snapshot in first.inputs.components:
            payload = snapshot.to_payload()
            payload.clear()
            (self.root / snapshot.origin).write_text("{}")
            self.assertNotEqual(snapshot.to_payload(), {})
            with self.assertRaises(FrozenInstanceError):
                snapshot.content = b"{}"
        with patch.object(Path, "read_bytes", side_effect=AssertionError("reread")):
            self.assertEqual(first.inputs.chapters, ("001",))
            self.assertEqual(first.job.to_payload(), before)
            self.assertNotIn("/different", dict(first.inputs.root_bindings).values())
            self.assertEqual(first.inputs.components[0].to_payload()["command_id"], "generate-chunks")
        with self.assertRaises(ConfigurationError):
            self.resolve(command="generate-chunks")

    def test_lab_and_canonical_share_complete_json_policy(self):
        canonical = self.resolve()
        lab = resolve_lab_proofreading(self.catalog)
        self.assertEqual(lab.settings, canonical.job.proofreading_settings)
        self.assertEqual(lab.selection.profile_id, "gemini-3.6-flash-v1")
        self.assertEqual(lab.settings.model, "gemini-3.6-flash")
        self.assertEqual(lab.settings.max_output_tokens, 16384)
        self.assertEqual(len(lab.components), 2)
        selected = self.read(KINDS["proofreading-profile"])
        for setting in selected["proofreading"]:
            incomplete = copy.deepcopy(selected)
            del incomplete["proofreading"][setting]
            self.write(KINDS["proofreading-profile"], incomplete)
            with self.assertRaises(ConfigurationError):
                resolve_lab_proofreading(self.catalog)

    def test_all_runtime_policy_parameters_are_required(self):
        proof = resolve_lab_proofreading(self.catalog).settings
        chunk = self.resolve(command="generate-chunks").job.semantic_chunk_config
        for record in (proof, chunk):
            values = {field.name: getattr(record, field.name) for field in fields(record)}
            for name in values:
                if name == "cache_dir":
                    continue  # Runtime environment input, not a JSON policy setting.
                incomplete = dict(values)
                del incomplete[name]
                with self.subTest(record=type(record).__name__, field=name), self.assertRaises(TypeError):
                    type(record)(**incomplete)
        for factory in (ProofreadingSettings, SemanticChunkConfig, SemanticChunkConfig.from_env, SemanticChunker):
            with self.assertRaises(TypeError):
                factory()
        with self.assertRaises(TypeError):
            SemanticChunker(None)

    def test_all_26_complete_jobs_keep_effective_settings_and_checkpoint_identity(self):
        # Comparison fixtures only: migrate no maintained subject manifests.
        maintained = CLI_ROOT / "jobs/subjects"
        for path in sorted(maintained.glob("*/*/prep-subject.local.json")):
            complete = json.loads(path.read_text())
            manifest_id, locale = path.parent.parent.name, path.parent.name
            relative = f"jobs/subjects/{manifest_id}/manifest.json"
            naming = complete["naming"]
            target = self.root / relative
            manifest = self.read(relative) if target.is_file() else {
                "component_schema_version": "1.0.0", "manifest_id": manifest_id,
                "identity": {key: naming[key] for key in ("category_code", "subject_code", "title_slug")},
                "artifact_root": complete["destination"]["subject_dir"].removesuffix("/" + locale),
                "editions": {},
            }
            # Replace the representative manifest when it shares a maintained ID.
            if manifest_id == "sub123_spand_rahasya" and locale == "hi-IN":
                manifest["artifact_root"] = complete["destination"]["subject_dir"].removesuffix("/" + locale)
                manifest["editions"] = {}
                manifest.pop("profile_overrides", None)
            split = copy.deepcopy(complete["chapter_split"])
            if split.get("pattern_type") == "regex":
                split["flags"] = split.get("flags", [])
            manifest["editions"][locale] = {
                "release": {"version": naming["version"], "subversion": naming["subversion"]},
                "source_document": {key: complete["source"][key]
                                    for key in ("relative_path", "font_encoding", "file_format")},
                "chapter_split": split,
            }
            self.write(relative, manifest)
        loaders = {"prep-subject": load_prep_subject_job, "generate-chunks": load_generate_chunks_job,
                   "generate-docx": load_generate_docx_job}
        count = 0
        for path in sorted(maintained.glob("*/*/*.json")):
            command, route, extension = path.name.split(".")
            with self.subTest(path=path.relative_to(maintained)):
                original = json.loads(path.read_text())
                # Replace only machine-specific library roots in the file-loaded
                # comparison. Preserve optional legacy omissions in its payload.
                for side in ("source", "destination"):
                    if "root_dir" in original[side]:
                        variable = ("GURUBODH_SOURCE_LIBRARY_ROOT" if command == "prep-subject" and side == "source"
                                    else "GURUBODH_CMS_LIBRARY_ROOT")
                        original[side]["root_dir"] = self.environ[variable]
                legacy_file = self.write("comparison.json", original)
                legacy = loaders[command](legacy_file)
                composed = self.resolve(command=command, storage_profile_id=route,
                                        manifest_id=path.parent.parent.name, locale=path.parent.name).job
                self.assertEqual(legacy.to_payload(), original)
                normalized = copy.deepcopy(original)
                for side in ("source", "destination"):
                    normalized[side].setdefault("backend", "local")
                    if normalized[side]["backend"] == "r2":
                        normalized[side].setdefault("url_base", None)
                if command == "prep-subject":
                    if normalized["chapter_split"].get("pattern_type") == "regex":
                        normalized["chapter_split"].setdefault("flags", [])
                    self.assertEqual(legacy.proofreading_settings, composed.proofreading_settings)
                    self.assertEqual(legacy.compiled_chapter_pattern, composed.compiled_chapter_pattern)
                    self.assertEqual(compatibility_record(legacy, "a" * 64), compatibility_record(composed, "a" * 64))
                elif command == "generate-chunks":
                    self.assertEqual(legacy.semantic_chunk_config, composed.semantic_chunk_config)
                self.assertEqual(composed.to_payload(), normalized)
                count += 1
        self.assertEqual(count, 26)


if __name__ == "__main__":
    unittest.main()
