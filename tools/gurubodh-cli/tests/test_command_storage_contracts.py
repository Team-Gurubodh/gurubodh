"""S3 contracts using independent fixtures and real validation boundaries."""

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

from gurubodh.errors import ConfigurationError, ProcessingError
import gurubodh.schema_validation as validation


FIXTURES = Path(__file__).parents[1] / "tests/fixtures/job-components"
SCHEMAS = {
    "command-definition": "command_definition.schema.json",
    "environment": "environment.schema.json",
    "storage-profile": "storage_profile.schema.json",
}
COMMANDS = ("prep-subject", "generate-chunks", "generate-docx", "lab-proofread")
ROUTES = ("local", "r2-output", "r2")
CASES = (
    *(("command-definition", f"commands/{name}.json") for name in COMMANDS),
    ("environment", "environments/development.json"),
    *(("storage-profile", f"storage-profiles/{name}.json") for name in ROUTES),
)
IDENTITY = {"command-definition": "command_id", "environment": "environment_id",
            "storage-profile": "storage_profile_id"}
ROLE_FIELDS = ("source_document", "subject_artifact_source", "subject_artifact_destination")
CANONICAL = ("component_schema_version", "command_id", "job_schema_version",
             "source_role", "destination_role", "naming_fields", "default_profiles")
LOCAL = ("stores", "local_source_library")
R2 = ("stores", "r2_destination_library")


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def at(payload, parts):
    for part in parts:
        payload = payload[part]
    return payload


def required_objects(kind, payload):
    """Independent field inventories from the contract, not implementation schemas."""
    if kind == "command-definition":
        command = payload["command_id"]
        if command == "lab-proofread":
            return {(): ("component_schema_version", "command_id", "default_profiles"),
                    ("default_profiles",): ("proofreading",)}
        objects = {(): (*CANONICAL, "pipeline_by_encoding" if command == "prep-subject" else "pipeline"),
                   ("default_profiles",): ()}
        if command == "prep-subject":
            objects[("pipeline_by_encoding",)] = ("aps", "unicode")
            objects[("default_profiles",)] = ("proofreading",)
        elif command == "generate-chunks":
            objects[("default_profiles",)] = ("chunking",)
        return objects
    if kind == "environment":
        return {
            (): ("component_schema_version", "environment_id", "stores"), ("stores",): (),
            LOCAL: ("backend", "root_dir"), (*LOCAL, "root_dir"): ("$env",),
            ("stores", "local_destination_library"): ("backend", "root_dir"),
            ("stores", "local_destination_library", "root_dir"): ("$env",),
            ("stores", "r2_source_library"): ("backend", "bucket", "prefix", "url_base"),
            R2: ("backend", "bucket", "prefix", "url_base"),
        }
    return {(): ("component_schema_version", "storage_profile_id", *ROLE_FIELDS)}


class CommandStorageContractTests(unittest.TestCase):
    def setUp(self):
        validation._validator.cache_clear()
        self.addCleanup(validation._validator.cache_clear)
        self.standalones = {}

    def standalone(self, kind):
        if kind not in self.standalones:
            schema = json.loads(validation.schema_path("job-components/schemas", SCHEMAS[kind]).read_text())
            Draft202012Validator.check_schema(schema)
            self.standalones[kind] = Draft202012Validator(schema)
        return self.standalones[kind]

    def assert_valid(self, payload, kind):
        before = copy.deepcopy(payload)
        self.standalone(kind).validate(payload)
        self.assertIsNone(validation.validate_component(payload, kind))
        self.assertEqual(payload, before)

    def assert_invalid(self, payload, kind, parts=()):
        before = copy.deepcopy(payload)
        self.assertFalse(self.standalone(kind).is_valid(payload))
        with self.assertRaises(ConfigurationError) as raised:
            validation.validate_component(payload, kind, "fixture.json")
        self.assertEqual(payload, before)
        message = str(raised.exception)
        self.assertIn(f"Config validation failed ({kind}, fixture.json)", message)
        self.assertIn("$" + "".join("['$env']" if p == "$env" else f".{p}" for p in parts), message)
        self.assertNotIn("secret-value", message)
        self.assertNotIsInstance(raised.exception, ProcessingError)
        return message

    def test_representative_declarations_and_explicit_values(self):
        for kind, name in CASES:
            with self.subTest(name=name):
                self.assertEqual(validation.COMPONENT_SCHEMAS[kind], SCHEMAS[kind])
                self.assert_valid(fixture(name), kind)
        self.assertEqual(fixture("commands/generate-docx.json")["default_profiles"], {})
        environment = fixture("environments/development.json")
        environment["stores"] = {"custom_store-2": environment["stores"]["r2_destination_library"]}
        environment["environment_id"] = "custom_env-2"
        self.assert_valid(environment, "environment")
        environment["stores"]["custom_store-2"]["url_base"] = "https://example.test/library"
        self.assert_valid(environment, "environment")
        route = fixture("storage-profiles/local.json")
        route["storage_profile_id"] = "custom_route-2"
        route["source_document"] = "not_loaded_here"
        self.assert_valid(route, "storage-profile")

    def test_every_required_property_without_defaults(self):
        for kind, name in CASES:
            for parts, fields in required_objects(kind, fixture(name)).items():
                for field in fields:
                    with self.subTest(name=name, parts=parts, field=field):
                        payload = fixture(name)
                        del at(payload, parts)[field]
                        self.assert_invalid(payload, kind, (*parts, field))

    def test_unknown_fields_and_object_types_at_each_boundary(self):
        for kind, name in CASES:
            for parts in required_objects(kind, fixture(name)):
                with self.subTest(name=name, parts=parts):
                    payload = fixture(name)
                    at(payload, parts)["unexpected"] = "secret-value"
                    self.assert_invalid(payload, kind, (*parts, "unexpected"))
                    for wrong in (None, [], "secret-value", True, 7):
                        payload = fixture(name)
                        if parts:
                            at(payload, parts[:-1])[parts[-1]] = wrong
                        else:
                            payload = wrong
                        self.assert_invalid(payload, kind, parts)

    def test_property_types_and_versions(self):
        for kind, name in CASES:
            for parts, fields in required_objects(kind, fixture(name)).items():
                for field in fields:
                    if isinstance(at(fixture(name), parts)[field], dict):
                        continue
                    for wrong in (None, True, 7, [], {"bad": "secret-value"}):
                        if field == "url_base" and wrong is None:
                            continue
                        with self.subTest(name=name, parts=parts, field=field, wrong=wrong):
                            payload = fixture(name)
                            at(payload, parts)[field] = wrong
                            self.assert_invalid(payload, kind, (*parts, field))
            for version in ("", "1.0.1", "2.0.0", "1.0.0\n"):
                payload = fixture(name)
                payload["component_schema_version"] = version
                self.assert_invalid(payload, kind, ("component_schema_version",))

    def test_resource_identity_and_wrong_kinds(self):
        for kind, name in CASES:
            payload = fixture(name)
            key = IDENTITY[kind]
            validation.validate_component(payload, kind, "unrelated.json", expected_id=payload[key])
            validation.validate_component(payload, kind, "unrelated.json")
            with self.assertRaises(ConfigurationError) as raised:
                validation.validate_component(payload, kind, expected_id="secret-value")
            self.assertIn(f"$.{key} must match the selected resource ID", str(raised.exception))
            self.assertNotIn("secret-value", str(raised.exception))
            for other in SCHEMAS.keys() - {kind}:
                self.assert_invalid(payload, other)
        with self.assertRaises(ConfigurationError):
            validation.validate_component({}, "unknown-kind")

    def test_id_and_store_reference_grammar(self):
        bad_ids = ("", "../a", "/a", "a/b", "a\\b", "https://a", "a.b", "a__b",
                   "a--b", "A", " a", "a\n", "a-", "_a", "$" "{ID}", "a\x00b", "१२३")
        for kind, name, fields in (
            ("environment", "environments/development.json", ("environment_id",)),
            ("storage-profile", "storage-profiles/local.json", ("storage_profile_id", *ROLE_FIELDS)),
        ):
            for field in fields:
                for value in bad_ids:
                    payload = fixture(name)
                    payload[field] = value
                    self.assert_invalid(payload, kind, (field,))
        for value in bad_ids:
            payload = fixture("environments/development.json")
            payload["stores"][value] = payload["stores"].pop("local_source_library")
            self.assert_invalid(payload, "environment", ("stores",))

    def test_command_specific_pipelines_roles_and_names(self):
        for name in COMMANDS:
            original = fixture(f"commands/{name}.json")
            for command_id in ("", "unknown", "prep-subject\n", "../prep-subject"):
                payload = copy.deepcopy(original)
                payload["command_id"] = command_id
                self.assert_invalid(payload, "command-definition", ("command_id",))
            if name == "lab-proofread":
                for key in (*CANONICAL[2:-1], "pipeline", "pipeline_by_encoding", "chapters", "job"):
                    payload = copy.deepcopy(original)
                    payload[key] = "secret-value"
                    self.assert_invalid(payload, "command-definition", (key,))
                continue
            for field, value in (
                ("job_schema_version", "9.0.0"), ("source_role", "local_source_library"),
                ("destination_role", "subject_artifact_source"), ("chapters", ["001"]), ("job", {}),
            ):
                payload = copy.deepcopy(original)
                payload[field] = value
                self.assert_invalid(payload, "command-definition", (field,))
            for names in ([], original["naming_fields"][:-1],
                          original["naming_fields"] + ["category_code"],
                          original["naming_fields"] + ["extra"], ["secret-value"], [None]):
                payload = copy.deepcopy(original)
                payload["naming_fields"] = names
                self.assert_invalid(payload, "command-definition", ("naming_fields",))
            payload = copy.deepcopy(original)
            payload["naming_fields"].reverse()
            self.assert_valid(payload, "command-definition")
            if name == "prep-subject":
                for encoding, pipeline in (("aps", "unicode-docx-ingest"), ("unicode", "legacy-docx-to-unicode")):
                    payload = copy.deepcopy(original)
                    payload["pipeline_by_encoding"][encoding] = pipeline
                    self.assert_invalid(payload, "command-definition", ("pipeline_by_encoding", encoding))
                payload = copy.deepcopy(original)
                payload["pipeline"] = "unicode-docx-ingest"
            else:
                payload = copy.deepcopy(original)
                payload["pipeline"] = "prep-subject"
                self.assert_invalid(payload, "command-definition", ("pipeline",))
                payload = copy.deepcopy(original)
                payload["pipeline_by_encoding"] = {}
            self.assert_invalid(payload, "command-definition")

    def test_complete_profile_references_and_docx_empty_object(self):
        for name in COMMANDS:
            original = fixture(f"commands/{name}.json")
            key = "chunking" if name == "generate-chunks" else "proofreading"
            for profiles in ({"model": "secret-value"}, {"other": "a-v1"}, None, "a-v1"):
                payload = copy.deepcopy(original)
                payload["default_profiles"] = profiles
                self.assert_invalid(payload, "command-definition", ("default_profiles",))
            if name == "generate-docx":
                for key in ("proofreading", "chunking"):
                    payload = copy.deepcopy(original)
                    payload["default_profiles"] = {key: "a-v1"}
                    self.assert_invalid(payload, "command-definition", ("default_profiles", key))
                continue
            for value in ("", "unversioned", "a-v0", "a-v01", "a-v1\n", "../a-v1",
                          "https://a-v1", {"model": "secret-value"}):
                payload = copy.deepcopy(original)
                payload["default_profiles"][key] = value
                self.assert_invalid(payload, "command-definition", ("default_profiles", key))
            payload = copy.deepcopy(original)
            payload["default_profiles"][key] = "custom-2.1-policy-v12"
            self.assert_valid(payload, "command-definition")
            payload["default_profiles"]["proofreading" if key == "chunking" else "chunking"] = "a-v1"
            self.assert_invalid(payload, "command-definition", ("default_profiles",))

    def test_backend_shapes_and_explicit_values(self):
        for parts, field, values in (
            (LOCAL, "backend", ("s3", "LOCAL", "r2", "")),
            (LOCAL, "root_dir", ("/literal/path", {"$env": "ROOT", "default": "/guessed"})),
            (R2, "backend", ("local", "s3", "R2")),
            (R2, "bucket", ("",)), (R2, "url_base", (False, 0, {}, [])),
        ):
            for value in values:
                payload = fixture("environments/development.json")
                at(payload, parts)[field] = value
                self.assert_invalid(payload, "environment", parts)
        for parts, field in ((LOCAL, "bucket"), (LOCAL, "url_base"), (R2, "root_dir")):
            payload = fixture("environments/development.json")
            at(payload, parts)[field] = "secret-value"
            self.assert_invalid(payload, "environment", (*parts, field))
        payload = fixture("environments/development.json")
        payload["stores"] = {}
        self.assert_invalid(payload, "environment", ("stores",))

    def test_environment_reference_and_safe_prefix_grammar(self):
        for value in ("", "1ROOT", "$" "{ROOT}", "$ROOT", "ROOT/path", "ROOT\n", " ROOT", "RÖÖT"):
            payload = fixture("environments/development.json")
            at(payload, (*LOCAL, "root_dir"))["$env"] = value
            self.assert_invalid(payload, "environment", (*LOCAL, "root_dir"))
        for value in ("ROOT", "_root2", "mixed_CASE_3"):
            payload = fixture("environments/development.json")
            at(payload, (*LOCAL, "root_dir"))["$env"] = value
            self.assert_valid(payload, "environment")
        for value in ("", "/root", "a/", "a//b", ".", "..", "./a", "../a", "a/./b",
                      "a/../b", "a/.", "a/..", "a\\b", "C:/a", "https://host/a",
                      "$" "{ROOT}/a", "$(ROOT)/a", "{{root}}/a", "a\x00b", "a\nb", "a\x7fb"):
            payload = fixture("environments/development.json")
            at(payload, R2)["prefix"] = value
            self.assert_invalid(payload, "environment", (*R2, "prefix"))
        for value in ("cms_library", "a..b/.hidden", "ग्रंथ/Source Documents"):
            payload = fixture("environments/development.json")
            at(payload, R2)["prefix"] = value
            self.assert_valid(payload, "environment")

    def test_safe_grouped_diagnostics_and_malformed_dynamic_keys(self):
        payload = fixture("environments/development.json")
        del payload["component_schema_version"]
        del at(payload, R2)["url_base"]
        at(payload, R2)["bucket"] = {"token": "secret-value"}
        first = self.assert_invalid(payload, "environment")
        second = self.assert_invalid(dict(reversed(list(payload.items()))), "environment")
        self.assertEqual(first, second)
        self.assertLess(first.index("$.component_schema_version"), first.index("$.stores"))
        for parts in (("stores",), R2, (*LOCAL, "root_dir"), ()):
            payload = fixture("environments/development.json")
            at(payload, parts)["secret-value\n/path"] = {"unexpected": "secret-value"}
            self.assert_invalid(payload, "environment", parts)
        payload = fixture("environments/development.json")
        payload["stores"]["secret-value\n/path"] = {"backend": "local", "root_dir": {}}
        self.assert_invalid(payload, "environment", ("stores",))

    def test_non_json_values_and_no_runtime_lookup(self):
        for kind in SCHEMAS:
            for payload in ((1, 2), {1: "secret-value"}, float("nan"), object()):
                with self.assertRaises(ConfigurationError):
                    validation.validate_component(payload, kind)
            with self.assertRaises(ConfigurationError) as raised:
                validation.validate_component({"secret-value\n/path": object()}, kind)
            self.assertNotIn("secret-value", str(raised.exception))
        for kind, name in CASES:
            payload = fixture(name)
            self.standalone(kind)
            validation.validate_component(payload, kind)
            with patch.object(Path, "read_text", side_effect=AssertionError("unexpected read")), \
                 patch.dict(os.environ, {}, clear=True), \
                 patch("os.getenv", side_effect=AssertionError("environment lookup forbidden")), \
                 patch("socket.socket", side_effect=AssertionError("network forbidden")):
                validation.validate_component(payload, kind)

    def test_standalone_ownership_cache_and_forbidden_job_schemas(self):
        original_read = Path.read_text
        original_path = validation.schema_path

        def guarded_read(path, *args, **kwargs):
            if "config" in path.parts and "jobs" in path.parts:
                raise AssertionError("job schema access forbidden")
            return original_read(path, *args, **kwargs)

        def components_only(kind, filename):
            self.assertEqual(kind, "job-components/schemas")
            return original_path(kind, filename)

        def check_owned(node):
            if isinstance(node, dict):
                self.assertNotIn("default", node)
                for key in ("$ref", "$dynamicRef", "$recursiveRef"):
                    if key in node:
                        self.assertTrue(node[key].startswith("#/$defs/"), node[key])
                if node.get("type") == "object":
                    self.assertIs(node.get("additionalProperties"), False)
                for child in node.values():
                    check_owned(child)
            elif isinstance(node, list):
                for child in node:
                    check_owned(child)

        with patch.object(Path, "read_text", guarded_read), \
             patch.object(validation, "schema_path", side_effect=components_only), \
             patch("socket.socket", side_effect=AssertionError("network forbidden")):
            for kind, name in CASES:
                cached = validation._validator("job-components/schemas", SCHEMAS[kind])
                self.assertIs(cached, validation._validator("job-components/schemas", SCHEMAS[kind]))
                check_owned(cached.schema)
                self.assert_valid(fixture(name), kind)
                for parts, fields in required_objects(kind, fixture(name)).items():
                    for field in fields:
                        payload = fixture(name)
                        del at(payload, parts)[field]
                        self.assert_invalid(payload, kind, (*parts, field))
                    payload = fixture(name)
                    at(payload, parts)["unexpected"] = "secret-value"
                    self.assert_invalid(payload, kind, (*parts, "unexpected"))

    def test_shared_profile_binding_and_unchanged_bge_settings(self):
        for name in ("prep-subject", "lab-proofread"):
            command = fixture(f"commands/{name}.json")
            self.assert_valid(command, "command-definition")
            self.assertEqual(command["default_profiles"], {"proofreading": "gemini-3.6-flash-v1"})
            profile = fixture("proofreading/gemini-3.6-flash-v1.json")
            validation.validate_component(profile, "proofreading-profile",
                                          expected_id=command["default_profiles"]["proofreading"])
            self.assertEqual(profile["proofreading"]["model"], "gemini-3.6-flash")
            self.assertEqual(profile["proofreading"]["max_output_tokens"], 16384)
        command = fixture("commands/generate-chunks.json")
        profile = fixture("chunking/bge-m3-semantic-window-v1.json")
        validation.validate_component(profile, "chunking-profile",
                                      expected_id=command["default_profiles"]["chunking"])
        self.assertEqual(profile["chunking"], fixture("chunking/bge-m3-v1.json")["chunking"])


if __name__ == "__main__":
    unittest.main()
