"""Catalog discovery and validation without maintained inventories or pipelines."""

import copy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from catalog_validation import validate_catalog
from gurubodh.errors import ConfigurationError
from gurubodh.job_components import _DIRECTORIES
from gurubodh.legacy import font_detection


CLI_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = CLI_ROOT / "tests/fixtures/job-components"
MANIFEST = "jobs/subjects/sub001_aps_example/manifest.json"
PROOFREADING = "config/job-components/profiles/proofreading/gemini-3.6-flash-v1.json"
CHUNKING = "config/job-components/profiles/chunking/bge-m3-semantic-window-v1.json"
POLICY = "config/policies/source-fonts.json"


class ConfigurationCatalogTests(unittest.TestCase):
    def test_committed_catalog_is_valid(self):
        # No subject IDs, profile IDs, expected counts, or configured values.
        validate_catalog(CLI_ROOT)


class SyntheticCatalogValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        # These are independent component-contract inputs, never a copy of the
        # maintained catalog or an import of its historical migration baseline.
        for kind, directory in _DIRECTORIES.items():
            source = directory.removeprefix("profiles/")
            shutil.copytree(FIXTURES / source, self.root / "config/job-components" / directory)
        self.write(MANIFEST, json.loads((FIXTURES / "subjects/aps-hindi.json").read_text()))
        self.write(POLICY, {
            "schema_version": "1.0.0",
            "approved_unicode_font_families": ["Synthetic Unicode Family"],
        })

    def write(self, relative, document):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def read(self, relative):
        return json.loads((self.root / relative).read_text(encoding="utf-8"))

    def assert_invalid(self, relative, document, message):
        path = self.root / relative
        original = path.read_bytes()
        self.write(relative, document)
        try:
            with self.assertRaisesRegex(ConfigurationError, message):
                validate_catalog(self.root)
        finally:
            path.write_bytes(original)

    def test_discovers_new_subject_edition_and_unused_profile(self):
        (self.root / "config/job-components/locales/mr-IN.json").unlink()
        before = validate_catalog(self.root)
        manifest = self.read(MANIFEST)
        manifest["manifest_id"] = "sub002_synthetic"
        manifest["identity"]["subject_code"] = "SUB002"
        manifest["editions"]["mr-IN"] = copy.deepcopy(manifest["editions"]["hi-IN"])
        self.write("jobs/subjects/sub002_synthetic/manifest.json", manifest)
        self.write("config/job-components/locales/mr-IN.json",
                   json.loads((FIXTURES / "locales/mr-IN.json").read_text()))
        profile = self.read(PROOFREADING)
        profile["profile_id"] = "unused-v1"
        self.write("config/job-components/profiles/proofreading/unused-v1.json", profile)
        after = validate_catalog(self.root)
        self.assertEqual(set(after.components) - set(before.components), {
            ("subject-manifest", "sub002_synthetic"),
            ("locale-definition", "mr-IN"),
            ("proofreading-profile", "unused-v1"),
        })
        self.assertEqual(after.components, tuple(sorted(after.components)))
        self.assertEqual(after.policies, ("source-fonts",))
        with self.assertRaises(FrozenInstanceError):
            after.policies = ()
        (self.root / "config/job-components/locales/mr-IN.json").unlink()
        with self.assertRaisesRegex(ConfigurationError, r"sub002_synthetic/manifest.json.*\$.editions.mr-IN"):
            validate_catalog(self.root)

    def test_rejects_malformed_duplicate_and_non_utf8_json(self):
        path = self.root / MANIFEST
        for content in (b"{", b'{"manifest_id":"a","manifest_id":"b"}', b"\xff"):
            with self.subTest(content=content):
                path.write_bytes(content)
                with self.assertRaisesRegex(ConfigurationError, "valid UTF-8 JSON with unique properties"):
                    validate_catalog(self.root)

    def test_rejects_invalid_structure_values_and_identity(self):
        manifest = self.read(MANIFEST)
        cases = []
        invalid = copy.deepcopy(manifest)
        del invalid["identity"]
        cases.append((MANIFEST, invalid, r"\$.identity"))
        invalid = copy.deepcopy(manifest)
        invalid["editions"]["hi-IN"]["source_document"]["font_encoding"] = "unsupported"
        cases.append((MANIFEST, invalid, "font_encoding"))
        invalid = copy.deepcopy(manifest)
        invalid["manifest_id"] = "different_subject"
        cases.append((MANIFEST, invalid, "manifest_id must match"))
        invalid = self.read(PROOFREADING)
        invalid["profile_id"] = "different-v1"
        cases.append((PROOFREADING, invalid, "profile_id must match"))
        invalid = self.read(CHUNKING)
        invalid["chunking"]["window_size"] = 0
        cases.append((CHUNKING, invalid, "window_size"))
        invalid = self.read("config/job-components/environments/development.json")
        invalid["stores"]["local_source_library"]["backend"] = "unsupported"
        cases.append(("config/job-components/environments/development.json", invalid, "backend"))
        for relative, invalid, message in cases:
            with self.subTest(relative=relative, message=message):
                self.assert_invalid(relative, invalid, message)

    def test_rejects_regex_and_proofreading_relationship_errors(self):
        manifest = self.read(MANIFEST)
        manifest["editions"]["hi-IN"]["chapter_split"] = {
            "enabled": True, "pattern_type": "regex", "pattern": "[", "flags": [],
        }
        self.assert_invalid(MANIFEST, manifest, "valid Python regular expression")
        profile = self.read(PROOFREADING)
        profile["proofreading"]["request_progress_interval_seconds"] = (
            profile["proofreading"]["request_timeout_seconds"] + 1
        )
        self.assert_invalid(PROOFREADING, profile, "must not exceed request_timeout_seconds")

    def test_rejects_invalid_unused_component(self):
        profile = self.read(PROOFREADING)
        profile["profile_id"] = "unused-v1"
        profile["proofreading"]["max_retries"] = -1
        self.write("config/job-components/profiles/proofreading/unused-v1.json", profile)
        with self.assertRaisesRegex(ConfigurationError, "unused-v1.json.*max_retries"):
            validate_catalog(self.root)

    def test_checks_all_profile_declarations_including_hidden_ones(self):
        manifest = self.read(MANIFEST)
        valid = {"proofreading": "gemini-3.6-flash-v1", "chunking": "bge-m3-semantic-window-v1"}
        manifest["profile_overrides"] = dict(valid)
        manifest["editions"]["hi-IN"]["profile_overrides"] = dict(valid)
        self.write(MANIFEST, manifest)
        for command, name in (("prep-subject", "proofreading"), ("lab-proofread", "proofreading"),
                              ("generate-chunks", "chunking")):
            relative = f"config/job-components/commands/{command}.json"
            document = self.read(relative)
            document["default_profiles"][name] = "missing-v1"
            with self.subTest(command=command):
                self.assert_invalid(relative, document, rf"{command}.json.*\$.default_profiles.{name}")
        for level in ("manifest", "edition"):
            for name in valid:
                invalid = copy.deepcopy(manifest)
                owner = invalid if level == "manifest" else invalid["editions"]["hi-IN"]
                owner["profile_overrides"][name] = "missing-v1"
                field = r"\$.profile_overrides" if level == "manifest" else r"\$.editions.hi-IN.profile_overrides"
                with self.subTest(level=level, name=name):
                    self.assert_invalid(MANIFEST, invalid, rf"manifest.json.*{field}.{name}")

    def test_rejects_invalid_hidden_profile_and_locale(self):
        # The edition selects a valid profile; the manifest still declares an
        # invalid profile which every catalog check must validate independently.
        manifest = self.read(MANIFEST)
        manifest["profile_overrides"] = {"proofreading": "hidden-v1"}
        manifest["editions"]["hi-IN"]["profile_overrides"] = {"proofreading": "gemini-3.6-flash-v1"}
        self.write(MANIFEST, manifest)
        profile = self.read(PROOFREADING)
        profile["profile_id"] = "hidden-v1"
        profile["proofreading"]["enabled"] = "invalid"
        path = self.write("config/job-components/profiles/proofreading/hidden-v1.json", profile)
        with self.assertRaisesRegex(ConfigurationError, "hidden-v1.json.*enabled"):
            validate_catalog(self.root)
        path.unlink()
        manifest.pop("profile_overrides")
        self.write(MANIFEST, manifest)
        relative = "config/job-components/locales/hi-IN.json"
        locale = self.read(relative)
        locale["metadata_defaults"]["source_script"] = 42
        self.assert_invalid(relative, locale, "source_script")
        (self.root / relative).unlink()
        with self.assertRaisesRegex(ConfigurationError, r"manifest.json.*\$.editions.hi-IN"):
            validate_catalog(self.root)

    def test_checks_every_storage_role_against_environment_union(self):
        relative = "config/job-components/storage-profiles/local.json"
        profile = self.read(relative)
        for role in ("source_document", "subject_artifact_source", "subject_artifact_destination"):
            invalid = dict(profile, **{role: "missing_store"})
            with self.subTest(role=role):
                self.assert_invalid(relative, invalid, rf"local.json.*\$.{role}")
        environment = self.read("config/job-components/environments/development.json")
        source = environment["stores"].pop("local_source_library")
        self.write("config/job-components/environments/development.json", environment)
        self.write("config/job-components/environments/another.json", {
            "component_schema_version": "1.0.0", "environment_id": "another",
            "stores": {"local_source_library": source},
        })
        # No single environment supplies all roles, but each name exists.
        validate_catalog(self.root)

    def test_source_font_policy_uses_real_validation_and_restores_lookup(self):
        lookup = font_detection.bundled_resource_path
        for families, message in (([], "at least"), (["*"], "must match|not|shape"),
                                  (["Example", " example "], "normalization"),
                                  (["APS-DV-Prakash"], "legacy-font classification")):
            with self.subTest(families=families):
                self.assert_invalid(POLICY, {
                    "schema_version": "1.0.0", "approved_unicode_font_families": families,
                }, message)
                self.assertIs(font_detection.bundled_resource_path, lookup)
        validate_catalog(self.root)
        self.assertIs(font_detection.bundled_resource_path, lookup)

    def test_rejects_missing_or_malformed_required_policy(self):
        path = self.root / POLICY
        for content in (b"{", b'{"schema_version":"1.0.0","schema_version":"1.0.0"}'):
            with self.subTest(content=content):
                path.write_bytes(content)
                with self.assertRaises(ConfigurationError):
                    validate_catalog(self.root)
        path.unlink()
        with self.assertRaisesRegex(ConfigurationError, "required policy is missing"):
            validate_catalog(self.root)

    def test_rejects_missing_roots_without_bundled_fallback(self):
        for relative in ("jobs/subjects", "config/job-components", "config/policies"):
            with self.subTest(relative=relative):
                path = self.root / relative
                moved = path.with_name(path.name + "-saved")
                path.rename(moved)
                try:
                    with self.assertRaisesRegex(ConfigurationError, "required catalog root is missing"):
                        validate_catalog(self.root)
                finally:
                    moved.rename(path)

    def test_rejects_unsupported_placements_and_kinds(self):
        for relative in ("jobs/subjects/manifest.json", "jobs/subjects/nested/sub001/manifest.json",
                         "config/job-components/unknown/example.json",
                         "config/job-components/commands/nested/prep-subject.json",
                         "config/policies/unknown.json", "config/policies/nested/source-fonts.json"):
            with self.subTest(relative=relative):
                path = self.write(relative, {})
                try:
                    with self.assertRaisesRegex(ConfigurationError, "placement|kind|manifests must use"):
                        validate_catalog(self.root)
                finally:
                    path.unlink()
        self.write("config/job-components/schemas/example.schema.json", {})
        self.write("config/policies/example.schema.json", {})
        validate_catalog(self.root)

    def test_rejects_root_escapes_and_symlink_cycles(self):
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external)
            (outside / "profile.json").write_text("{}")
            links = (
                ("config/job-components/profiles/proofreading/escape-v1.json", outside / "profile.json"),
                ("jobs/subjects/outside", outside),
                ("config/policies/escape.json", outside / "profile.json"),
                ("config/job-components/cycle", self.root / "config/job-components"),
            )
            for relative, target in links:
                with self.subTest(relative=relative):
                    link = self.root / relative
                    link.symlink_to(target)
                    try:
                        with self.assertRaisesRegex(ConfigurationError, "unsafe catalog path"):
                            validate_catalog(self.root)
                    finally:
                        link.unlink()

    def test_rejects_nonfiles_dangling_links_and_unreadable_resources(self):
        relative = "config/job-components/profiles/proofreading/unreadable-v1.json"
        path = self.root / relative
        path.mkdir()
        with self.assertRaisesRegex(ConfigurationError, "regular JSON file"):
            validate_catalog(self.root)
        path.rmdir()
        path.symlink_to(self.root / "missing.json")
        with self.assertRaisesRegex(ConfigurationError, "missing, unreadable, or unsafe"):
            validate_catalog(self.root)
        path.unlink()
        read_bytes = Path.read_bytes

        def unreadable(resource):
            if resource == self.root / MANIFEST:
                raise PermissionError("synthetic unreadable resource")
            return read_bytes(resource)

        with patch.object(Path, "read_bytes", unreadable):
            with self.assertRaisesRegex(ConfigurationError, "resource is missing, unreadable, or has an unsafe path"):
                validate_catalog(self.root)

    def test_validation_is_read_only_and_does_not_bind_environment(self):
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        # Environment declarations retain unresolved $env values. No roots,
        # credentials, runtime job resolver, or source documents are needed.
        with patch.dict("os.environ", {}, clear=True):
            validate_catalog(self.root)
        after = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
