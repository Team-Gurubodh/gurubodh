"""S2 contracts using independent declarations and real validation boundaries."""

import copy
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

from gurubodh.errors import ConfigurationError
import gurubodh.schema_validation as validation


CLI_ROOT = Path(__file__).parents[1]
FIXTURES = CLI_ROOT / "tests/fixtures/job-components"
COMPONENTS = {
    "subject-manifest": "subjects/unicode-bilingual.json",
    "locale-definition": "locales/hi-IN.json",
}
EDITION = ("editions", "hi-IN")
SPLIT = (*EDITION, "chapter_split")
# Independent field inventories, not generated from the implementation schemas.
REQUIRED = {
    "subject-manifest": {
        (): ("component_schema_version", "manifest_id", "identity", "artifact_root", "editions"),
        ("identity",): ("category_code", "subject_code", "title_slug"),
        EDITION: ("release", "source_document", "chapter_split"),
        (*EDITION, "release"): ("version", "subversion"),
        (*EDITION, "source_document"): ("relative_path", "font_encoding", "file_format"),
        SPLIT: ("enabled", "pattern_type", "pattern", "flags"),
    },
    "locale-definition": {
        (): ("component_schema_version", "locale", "metadata_defaults"),
        ("metadata_defaults",): ("source_script", "output_text_encoding", "summary_chapter_markers"),
    },
}


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def component(kind):
    return fixture(COMPONENTS[kind])


def at(payload, parts):
    for part in parts:
        payload = payload[part]
    return payload


def location(parts):
    return "$" + "".join(f".{part}" for part in parts)


class SubjectLocaleContractTests(unittest.TestCase):
    def assert_invalid(self, payload, kind, parts=(), *, structural=True):
        original = copy.deepcopy(payload)
        if structural:
            schema = validation._validator("job-components/schemas", validation.COMPONENT_SCHEMAS[kind]).schema
            self.assertFalse(Draft202012Validator(schema).is_valid(payload))
        with self.assertRaises(ConfigurationError) as raised:
            validation.validate_component(payload, kind, "fixture.json")
        self.assertEqual(payload, original)
        message = str(raised.exception)
        self.assertIn(f"Config validation failed ({kind}, fixture.json)", message)
        self.assertIn(location(parts), message)
        self.assertNotIn("secret-value", message)
        return message

    def test_representative_fixtures_and_explicit_empty_values(self):
        for kind, names in (
            ("subject-manifest", ("subjects/aps-hindi.json", "subjects/unicode-bilingual.json")),
            ("locale-definition", ("locales/hi-IN.json", "locales/mr-IN.json")),
        ):
            for name in names:
                with self.subTest(name=name):
                    payload = fixture(name)
                    original = copy.deepcopy(payload)
                    self.assertIsNone(validation.validate_component(payload, kind))
                    self.assertEqual(payload, original)
        payload = component("subject-manifest")
        payload["profile_overrides"] = {}
        at(payload, EDITION)["profile_overrides"] = {}
        at(payload, SPLIT)["flags"] = []
        validation.validate_component(payload, "subject-manifest")
        payload = component("locale-definition")
        payload["metadata_defaults"]["summary_chapter_markers"] = []
        validation.validate_component(payload, "locale-definition")
        payload = component("subject-manifest")
        del payload["editions"]["hi-IN"]
        validation.validate_component(payload, "subject-manifest")

    def test_every_required_field_fails_without_defaults(self):
        for kind, objects in REQUIRED.items():
            for parts, keys in objects.items():
                for key in keys:
                    with self.subTest(kind=kind, parts=parts, key=key):
                        payload = component(kind)
                        del at(payload, parts)[key]
                        self.assert_invalid(payload, kind, (*parts, key))
        # A complete Hindi edition cannot fill missing Marathi values.
        payload = component("subject-manifest")
        del payload["editions"]["mr-IN"]["release"]
        self.assert_invalid(payload, "subject-manifest", ("editions", "mr-IN", "release"))

    def test_all_owned_objects_reject_unknown_fields_and_wrong_types(self):
        for kind, objects in REQUIRED.items():
            paths = list(objects)
            if kind == "subject-manifest":
                paths += [("editions",), ("profile_overrides",), (*EDITION, "profile_overrides")]
            for parts in paths:
                with self.subTest(kind=kind, parts=parts):
                    payload = component(kind)
                    at(payload, parts)["unexpected"] = "secret-value"
                    self.assert_invalid(payload, kind, (*parts, "unexpected"))
                    for value in (None, [], "secret-value", True, 1):
                        payload = component(kind)
                        if parts:
                            at(payload, parts[:-1])[parts[-1]] = value
                        else:
                            payload = value
                        self.assert_invalid(payload, kind, parts)

    def test_scalar_and_array_fields_reject_wrong_types(self):
        for kind, objects in REQUIRED.items():
            for parts, keys in objects.items():
                for key in keys:
                    original = at(component(kind), parts)[key]
                    if isinstance(original, dict):
                        continue
                    for value in (None, {"value": "secret-value"}, 1):
                        with self.subTest(kind=kind, parts=parts, key=key, value=value):
                            payload = component(kind)
                            at(payload, parts)[key] = value
                            self.assert_invalid(payload, kind, (*parts, key))

    def test_versions_ids_and_resource_identity(self):
        for kind, id_key in (("subject-manifest", "manifest_id"), ("locale-definition", "locale")):
            for value in (None, 1, "1.0.1", "2.0.0"):
                payload = component(kind)
                payload["component_schema_version"] = value
                self.assert_invalid(payload, kind, ("component_schema_version",))
            payload = component(kind)
            validation.validate_component(payload, kind, "unrelated-display.json", expected_id=payload[id_key])
            validation.validate_component(payload, kind, "not-the-resource.json")
            with self.assertRaises(ConfigurationError) as raised:
                validation.validate_component(payload, kind, expected_id="secret-value")
            self.assertIn(f"$.{id_key} must match the selected resource ID", str(raised.exception))
            self.assertNotIn("secret-value", str(raised.exception))
            self.assertNotIn(payload[id_key], str(raised.exception))
        for value in ("", "../a", "/a", "a/b", "a\\b", "https://a", "a.b", "a__b",
                      "a--b", "A", " a", "a\n", "a-", "${ID}"):
            payload = component("subject-manifest")
            payload["manifest_id"] = value
            self.assert_invalid(payload, "subject-manifest", ("manifest_id",))
        for value in ("a", "subject-123", "sub123_spand_rahasya"):
            payload = component("subject-manifest")
            payload["manifest_id"] = value
            validation.validate_component(payload, "subject-manifest")

    def test_locales_encodings_formats_and_metadata_constants(self):
        for value in ("hi", "en-US", "mr-in", "", "hi-IN\n"):
            payload = component("locale-definition")
            payload["locale"] = value
            self.assert_invalid(payload, "locale-definition", ("locale",))
            payload = component("subject-manifest")
            payload["editions"][value] = payload["editions"].pop("hi-IN")
            self.assert_invalid(payload, "subject-manifest", ("editions",))
        payload = component("subject-manifest")
        payload["editions"] = {}
        self.assert_invalid(payload, "subject-manifest", ("editions",))
        for key, values in (("font_encoding", ("shreelipi", "UTF-8", "")),
                            ("file_format", ("DOCX", "doc", "pdf", ""))):
            for value in values:
                payload = component("subject-manifest")
                at(payload, (*EDITION, "source_document"))[key] = value
                self.assert_invalid(payload, "subject-manifest", (*EDITION, "source_document", key))
        for key, values in (("source_script", ("Latin", "")),
                            ("output_text_encoding", ("utf-8", "UTF-16", "")),
                            ("summary_chapter_markers", ([""], [None], [1], [{}], "marker"))):
            for value in values:
                payload = component("locale-definition")
                payload["metadata_defaults"][key] = value
                self.assert_invalid(payload, "locale-definition", ("metadata_defaults", key))
        for key in ("language", "proofreading_instruction", "provider"):
            payload = component("locale-definition")
            payload["metadata_defaults"][key] = "secret-value"
            self.assert_invalid(payload, "locale-definition", ("metadata_defaults", key))

    def test_identity_and_release_patterns(self):
        cases = {
            ("identity", "category_code"): ("cat001", "CAT01", "CAT0001", "CAT001\n"),
            ("identity", "subject_code"): ("SUB01", "SUB001\n", "SUB१२३"),
            ("identity", "title_slug"): ("", "bad_slug", "-title", "title\n", "two words"),
            (*EDITION, "release", "version"): (1, "1", "001", "०१", "01\n"),
            (*EDITION, "release", "subversion"): (1, "1", "001", "", "01\n"),
        }
        for parts, values in cases.items():
            for value in values:
                payload = component("subject-manifest")
                at(payload, parts[:-1])[parts[-1]] = value
                self.assert_invalid(payload, "subject-manifest", parts)

    def test_safe_paths_without_normalization(self):
        paths = (("artifact_root",), (*EDITION, "source_document", "relative_path"))
        for parts in paths:
            for value in ("", "/root", "a/", "a//b", ".", "..", "./a", "../a", "a/./b",
                          "a/../b", "a/.", "a/..", "a\\b", "C:/a", "https://host/a", "file:a",
                          "${ROOT}/a", "$(ROOT)/a", "{{root}}/a", "a\x00b", "a\nb", "a\x7fb"):
                with self.subTest(parts=parts, value=value):
                    payload = component("subject-manifest")
                    at(payload, parts[:-1])[parts[-1]] = value
                    self.assert_invalid(payload, "subject-manifest", parts)
            for value in ("library/spand", "a", "a..b/.hidden", "ग्रंथ/Source Document.docx"):
                payload = component("subject-manifest")
                at(payload, parts[:-1])[parts[-1]] = value
                original = copy.deepcopy(payload)
                validation.validate_component(payload, "subject-manifest")
                self.assertEqual(payload, original)

    def test_split_shapes_require_explicit_applicable_fields(self):
        valid = [
            {"enabled": False},
            {"enabled": True, "pattern_type": "literal", "pattern": "[not a regex"},
            {"enabled": True, "pattern_type": "regex", "pattern": "^chapter", "flags": []},
            {"enabled": True, "pattern_type": "regex", "pattern": "^chapter",
             "flags": ["IGNORECASE", "MULTILINE", "DOTALL", "VERBOSE"]},
        ]
        invalid = [
            {}, {"enabled": True}, {"enabled": 1},
            {"enabled": False, "pattern_type": "regex"},
            {"enabled": False, "pattern": "unused"}, {"enabled": False, "flags": []},
            {"enabled": True, "pattern_type": "literal", "pattern": "x", "flags": []},
            {"enabled": True, "pattern_type": "regex", "pattern": "x"},
            {"enabled": True, "pattern_type": "other", "pattern": "x"},
        ]
        for shape in valid + invalid:
            with self.subTest(shape=shape):
                payload = component("subject-manifest")
                at(payload, EDITION)["chapter_split"] = shape
                if shape in valid:
                    validation.validate_component(payload, "subject-manifest")
                else:
                    self.assert_invalid(payload, "subject-manifest", SPLIT)
        for key, values in (("pattern", ("", None, 1)),
                            ("flags", (None, "MULTILINE", ["ASCII"], ["IGNORECASE", "IGNORECASE"], [1]))):
            for value in values:
                payload = component("subject-manifest")
                at(payload, SPLIT)[key] = value
                self.assert_invalid(payload, "subject-manifest", (*SPLIT, key))

    def test_regex_semantics_use_declared_flags_and_safe_errors(self):
        for pattern in ("[secret-value", "(?P<secret-value>x)", "x{999999999999999999999}"):
            payload = component("subject-manifest")
            at(payload, SPLIT)["pattern"] = pattern
            message = self.assert_invalid(payload, "subject-manifest", (*SPLIT, "pattern"), structural=False)
            self.assertIn("valid Python regular expression", message)
        # VERBOSE makes the unmatched '[' a comment; without it compilation fails.
        payload = component("subject-manifest")
        at(payload, SPLIT).update(pattern="x # [secret-value", flags=["VERBOSE"])
        validation.validate_component(payload, "subject-manifest")
        at(payload, SPLIT)["flags"] = []
        self.assert_invalid(payload, "subject-manifest", (*SPLIT, "pattern"), structural=False)

    def test_profile_overrides_are_only_complete_profile_ids(self):
        for parts in (("profile_overrides",), (*EDITION, "profile_overrides")):
            for key in ("proofreading", "chunking"):
                for value in (None, {}, {"model": "secret-value"}, "unversioned", "a-v0", "a-v01",
                              "../a-v1", "a/b-v1", "a\\b-v1", "https://a-v1", "a_v1", "A-v1", "a-v1\n"):
                    payload = component("subject-manifest")
                    at(payload, parts)[key] = value
                    self.assert_invalid(payload, "subject-manifest", (*parts, key))
            payload = component("subject-manifest")
            at(payload, parts)["model"] = "secret-value"
            self.assert_invalid(payload, "subject-manifest", (*parts, "model"))
            payload = component("subject-manifest")
            at(payload, parts[:-1])[parts[-1]] = {"chunking": "custom-policy-2.1-v12"}
            # No existence lookup or invocation selection at this boundary.
            validation.validate_component(payload, "subject-manifest")

    def test_wrong_kinds_and_non_json_values(self):
        for kind, other in (("subject-manifest", "locale-definition"),
                            ("locale-definition", "subject-manifest")):
            self.assert_invalid(component(other), kind)
        for value in ((1, 2), {1: "value"}, float("nan"), object()):
            with self.assertRaises(ConfigurationError):
                validation.validate_component(value, "subject-manifest")

    def test_diagnostics_are_deterministic_and_value_safe(self):
        payload = component("subject-manifest")
        del payload["component_schema_version"]
        payload["artifact_root"] = "/secret-value"
        at(payload, SPLIT)["flags"] = ["secret-value"]
        first = self.assert_invalid(payload, "subject-manifest")
        second = self.assert_invalid(dict(reversed(list(payload.items()))), "subject-manifest")
        self.assertEqual(first, second)
        self.assertLess(first.index("$.artifact_root"), first.index("$.component_schema_version"))

    def test_schemas_are_standalone_and_do_not_load_jobs(self):
        original_schema_path = validation.schema_path
        original_read = Path.read_text

        def no_jobs(kind, filename):
            self.assertEqual(kind, "job-components/schemas")
            return original_schema_path(kind, filename)

        def guarded_read(path, *args, **kwargs):
            if "config" in path.parts and "jobs" in path.parts:
                raise AssertionError("Job schema read forbidden")
            return original_read(path, *args, **kwargs)

        def check_owned(node):
            if isinstance(node, dict):
                self.assertNotIn("default", node)
                for key in ("$ref", "$dynamicRef", "$recursiveRef"):
                    if key in node:
                        self.assertTrue(node[key].startswith("#/$defs/"), node[key])
                if node.get("type") == "object":
                    self.assertIs(node["additionalProperties"], False)
                for child in node.values():
                    check_owned(child)
            elif isinstance(node, list):
                for child in node:
                    check_owned(child)

        validation._validator.cache_clear()
        self.addCleanup(validation._validator.cache_clear)
        with patch("gurubodh.schema_validation.schema_path", side_effect=no_jobs), \
             patch.object(Path, "read_text", guarded_read), \
             patch("socket.socket", side_effect=AssertionError("network forbidden")):
            for kind in COMPONENTS:
                filename = validation.COMPONENT_SCHEMAS[kind]
                cached = validation._validator("job-components/schemas", filename)
                self.assertIs(cached, validation._validator("job-components/schemas", filename))
                check_owned(cached.schema)
                Draft202012Validator.check_schema(cached.schema)
                standalone = Draft202012Validator(cached.schema)
                standalone.validate(component(kind))
                validation.validate_component(component(kind), kind)
                for parts, keys in REQUIRED[kind].items():
                    for key in keys:
                        payload = component(kind)
                        del at(payload, parts)[key]
                        self.assertFalse(standalone.is_valid(payload), (parts, key))
                        self.assert_invalid(payload, kind, (*parts, key))
                    payload = component(kind)
                    at(payload, parts)["unexpected"] = "secret-value"
                    self.assertFalse(standalone.is_valid(payload))
                    self.assert_invalid(payload, kind, (*parts, "unexpected"))


class SubjectLocaleMappingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def test_declared_fields_fit_existing_preparation_boundaries(self):
        # Explicit test construction checks the documented mapping; it is not a resolver.
        from gurubodh.config import (
            prepare_generate_chunks_job, prepare_generate_docx_job, prepare_prep_subject_job,
        )

        manifests = (fixture("subjects/aps-hindi.json"), fixture("subjects/unicode-bilingual.json"))
        proof = fixture("proofreading/gemini-3.6-flash-v1.json")["proofreading"]
        chunking = fixture("chunking/bge-m3-v1.json")["chunking"]
        for manifest in manifests:
            for language, edition in manifest["editions"].items():
                with self.subTest(manifest=manifest["manifest_id"], language=language):
                    locale = fixture(f"locales/{language}.json")
                    before = copy.deepcopy((manifest, locale))
                    naming = {**manifest["identity"], **edition["release"]}
                    subject_dir = manifest["artifact_root"] + "/" + language
                    prep = {
                        "schema_version": "1.5.0",
                        "pipeline": "legacy-docx-to-unicode" if edition["source_document"]["font_encoding"] == "aps" else "unicode-docx-ingest",
                        "source": {"backend": "local", "root_dir": str(self.root / "source"), **edition["source_document"]},
                        "destination": {"backend": "local", "root_dir": str(self.root / "artifacts"), "subject_dir": subject_dir},
                        "naming": naming,
                        "chapter_split": copy.deepcopy(edition["chapter_split"]),
                        "metadata_defaults": {"language": language, **locale["metadata_defaults"]},
                        "proofreading": proof,
                    }
                    prepared = prepare_prep_subject_job(prep)
                    self.assertEqual(prepared.to_payload(), prep)
                    if manifest["manifest_id"] == "sub123_spand_rahasya" and language == "hi-IN":
                        self.assertTrue(prepared.compiled_chapter_pattern.flags & re.MULTILINE)
                        self.assertIsNotNone(prepared.compiled_chapter_pattern.search("text\nप्रबोधन"))
                    else:
                        self.assertIsNone(prepared.compiled_chapter_pattern)
                    # The S3 store supplies the prefix; S2 contributes the safe source path.
                    r2_prep = copy.deepcopy(prep)
                    r2_prep["source"] = {
                        "backend": "r2", "bucket": "fixture-bucket",
                        "key": "source_library/" + edition["source_document"]["relative_path"],
                        "font_encoding": edition["source_document"]["font_encoding"],
                        "file_format": edition["source_document"]["file_format"],
                        "url_base": None,
                    }
                    self.assertEqual(prepare_prep_subject_job(r2_prep).to_payload(), r2_prep)
                    derived_store = {"backend": "local", "root_dir": str(self.root / "artifacts"), "subject_dir": subject_dir}
                    chunks = {
                        "schema_version": "1.2.0", "pipeline": "generate-chunks",
                        "source": dict(derived_store), "destination": dict(derived_store),
                        "naming": {**naming, "language": language}, "chunking": chunking,
                    }
                    self.assertEqual(prepare_generate_chunks_job(chunks).to_payload(), chunks)
                    docx = {
                        "schema_version": "1.0.0", "pipeline": "generate-docx",
                        "source": dict(derived_store), "destination": dict(derived_store),
                        "naming": {**manifest["identity"], "language": language},
                    }
                    self.assertEqual(prepare_generate_docx_job(docx).to_payload(), docx)
                    self.assertNotIn("version", docx["naming"])
                    self.assertNotIn("subversion", docx["naming"])
                    self.assertEqual((manifest, locale), before)
        # Expectations independent of the mapping formula and deliberately unlike manifest_id.
        bilingual = manifests[1]
        self.assertEqual(bilingual["artifact_root"] + "/hi-IN", "library/spand/hi-IN")
        self.assertEqual(bilingual["artifact_root"] + "/mr-IN", "library/spand/mr-IN")
        self.assertEqual(bilingual["editions"]["hi-IN"]["release"], {"version": "01", "subversion": "02"})
        self.assertEqual(bilingual["editions"]["mr-IN"]["release"], {"version": "03", "subversion": "01"})


if __name__ == "__main__":
    unittest.main()
