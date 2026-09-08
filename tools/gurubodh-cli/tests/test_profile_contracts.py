"""S1 contract cases: independent fixtures, real validators, no live providers."""

import copy
from importlib.metadata import PathDistribution
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

from gurubodh.errors import ConfigurationError, ProcessingError
from gurubodh.schema_validation import (
    COMPONENT_SCHEMAS,
    _validator,
    validate_artifact,
    validate_component,
    validate_job,
)


CLI_ROOT = Path(__file__).parents[1]
FIXTURES = CLI_ROOT / "tests" / "fixtures" / "job-components"
PROFILES = {
    "proofreading": ("gemini-3.6-flash-v1", "prep-subject"),
    "chunking": ("bge-m3-v1", "generate-chunks"),
}


def profile(kind):
    return json.loads((FIXTURES / kind / f"{PROFILES[kind][0]}.json").read_text())


class ProfileContractTests(unittest.TestCase):
    def assert_invalid(self, payload, kind, location, *, structural=True):
        original = copy.deepcopy(payload)
        if structural:
            filename = COMPONENT_SCHEMAS[f"{kind}-profile"]
            schema = _validator("job-components/schemas", filename).schema
            self.assertFalse(Draft202012Validator(schema).is_valid(payload))
        with self.assertRaises(ConfigurationError) as raised:
            validate_component(payload, f"{kind}-profile", "profiles/example.json")
        self.assertEqual(payload, original)
        self.assertIn(f"Config validation failed ({kind}-profile, profiles/example.json)", str(raised.exception))
        self.assertIn(location, str(raised.exception))
        return str(raised.exception)

    def test_complete_independent_fixtures_are_non_mutating(self):
        for kind in PROFILES:
            payload = profile(kind)
            original = copy.deepcopy(payload)
            with self.subTest(kind=kind):
                self.assertIsNone(validate_component(payload, f"{kind}-profile"))
                self.assertEqual(payload, original)
        self.assertEqual(profile("proofreading")["proofreading"]["model"], "gemini-3.6-flash")
        self.assertEqual(profile("proofreading")["proofreading"]["max_output_tokens"], 16384)
        self.assertEqual(len(profile("proofreading")["proofreading"]), 18)
        self.assertEqual(len(profile("chunking")["chunking"]), 11)

    def test_every_envelope_and_policy_field_is_required(self):
        # Deletions come from independently authored fixtures, not schema.required.
        for kind in PROFILES:
            for key in profile(kind):
                payload = profile(kind)
                del payload[key]
                with self.subTest(kind=kind, envelope=key):
                    self.assert_invalid(payload, kind, f"$.{key} is required")
            for key in profile(kind)[kind]:
                payload = profile(kind)
                del payload[kind][key]
                with self.subTest(kind=kind, policy=key):
                    self.assert_invalid(payload, kind, f"$.{kind}.{key} is required")

    def test_unknown_properties_and_wrong_kinds_fail(self):
        for kind in PROFILES:
            for nested in (False, True):
                payload = profile(kind)
                (payload[kind] if nested else payload)["unexpected"] = "do-not-echo"
                message = self.assert_invalid(payload, kind, "unexpected is not allowed")
                self.assertNotIn("do-not-echo", message)
            other = "chunking" if kind == "proofreading" else "proofreading"
            self.assert_invalid(profile(other), kind, f"$.{kind} is required")

    def test_versions_and_unsafe_or_unversioned_ids_fail(self):
        for kind in PROFILES:
            for value in (None, 1, "1.0.1", "2.0.0"):
                payload = profile(kind)
                payload["component_schema_version"] = value
                self.assert_invalid(payload, kind, "$.component_schema_version")
            for value in (None, 1, "", "unversioned", "a-v0", "a-v01", "../a-v1",
                          "/a-v1", "a/b-v1", "a\\b-v1", "https://a-v1", "a..b-v1",
                          "a--b-v1", "A-v1", "a_v1", " a-v1", "a-v1\n", "${ID}"):
                payload = profile(kind)
                payload["profile_id"] = value
                with self.subTest(kind=kind, value=value):
                    self.assert_invalid(payload, kind, "$.profile_id")
            payload = profile(kind)
            payload["profile_id"] = "custom-policy-2.1-v12"
            validate_component(payload, f"{kind}-profile")

    def test_resource_identity_is_explicit_and_diagnostics_do_not_echo_ids(self):
        for kind in PROFILES:
            payload = profile(kind)
            validate_component(payload, f"{kind}-profile", "unrelated-display-name.json",
                               expected_id=payload["profile_id"])
            with self.assertRaises(ConfigurationError) as raised:
                validate_component(payload, f"{kind}-profile", expected_id="secret-requested-id")
            self.assertIn("$.profile_id must match the selected resource ID", str(raised.exception))
            self.assertNotIn("secret-requested-id", str(raised.exception))
            self.assertNotIn(payload["profile_id"], str(raised.exception))

    def test_every_policy_field_rejects_an_object_value(self):
        for kind in PROFILES:
            for key in profile(kind)[kind]:
                payload = profile(kind)
                payload[kind][key] = {"secret": "do-not-echo"}
                with self.subTest(kind=kind, field=key):
                    message = self.assert_invalid(payload, kind, f"$.{kind}.{key}")
                    self.assertNotIn("do-not-echo", message)

    def test_policy_bounds_constants_and_boolean_types(self):
        cases = {
            "proofreading": {
                "enabled": [False, 1], "continue_on_error": [True, 0],
                "provider": ["other"], "model": [""], "max_output_tokens": [0, True],
                "max_input_characters": [0], "max_retries": [0, 1.5],
                "initial_retry_delay_seconds": [-1], "max_retry_delay_seconds": [-1],
                "min_request_interval_seconds": [-1], "max_requests_per_minute": [0],
                "max_estimated_input_tokens_per_minute": [0], "request_timeout_seconds": [0],
                "request_progress_interval_seconds": [0], "unavailable_max_retries": [0, 3],
                "unavailable_first_retry_delay_seconds": [0],
                "unavailable_second_retry_delay_seconds": [0], "unavailable_cooldown_seconds": [0],
            },
            "chunking": {
                "provider": ["other"], "model": ["other"],
                "model_revision": ["latest", "a" * 39, "A" * 40],
                "threshold_percentile": [-1, 101, True], "min_chars": [-1, 0.5],
                "window_size": [0], "batch_size": [0],
                "normalize_contextual_vectors": [1, None], "device": ["tpu", False],
                "local_files_only": [1, None], "strategy_version": ["semantic-window-v2"],
            },
        }
        for kind, settings in cases.items():
            for key, values in settings.items():
                for value in values:
                    payload = profile(kind)
                    payload[kind][key] = value
                    with self.subTest(kind=kind, key=key, value=value):
                        self.assert_invalid(payload, kind, f"$.{kind}.{key}")

    def test_tunable_policy_values_are_not_hardcoded_to_fixtures(self):
        payload = profile("proofreading")
        payload["proofreading"].update(max_output_tokens=8192, max_retries=1,
                                      initial_retry_delay_seconds=0,
                                      request_progress_interval_seconds=120)
        validate_component(payload, "proofreading-profile")
        for device in (None, "cpu", "mps", "cuda"):
            for threshold in (0, 100):
                payload = profile("chunking")
                payload["chunking"].update(device=device, threshold_percentile=threshold,
                                          min_chars=0, window_size=1, batch_size=1,
                                          normalize_contextual_vectors=False, local_files_only=False)
                validate_component(payload, "chunking-profile")

    def test_progress_interval_cannot_exceed_request_timeout(self):
        payload = profile("proofreading")
        payload["proofreading"]["request_progress_interval_seconds"] = 121
        self.assert_invalid(payload, "proofreading",
                            "$.proofreading.request_progress_interval_seconds must not exceed request_timeout_seconds",
                            structural=False)

    def test_non_json_values_and_non_object_roots_fail_in_configuration_domain(self):
        for value in (None, [], True, "text", 123):
            self.assert_invalid(value, "chunking", "$ must be object")
        for value in (float("nan"), float("inf"), object(), (1, 2)):
            payload = profile("chunking")
            payload["chunking"]["threshold_percentile"] = value
            with self.assertRaises(ConfigurationError) as raised:
                validate_component(payload, "chunking-profile")
            self.assertIn("$.chunking.threshold_percentile", str(raised.exception))

    def test_diagnostics_are_stable_and_value_safe(self):
        payload = profile("chunking")
        payload.pop("component_schema_version")
        payload["chunking"]["model_revision"] = "secret-revision-value"
        payload["z_unknown"] = "secret-extra-value"
        first = self.assert_invalid(payload, "chunking", "$.component_schema_version")
        second = self.assert_invalid(dict(reversed(list(payload.items()))), "chunking", "$.component_schema_version")
        self.assertEqual(first, second)
        self.assertNotIn("secret-revision-value", first)
        self.assertNotIn("secret-extra-value", first)
        self.assertLess(first.index("$.chunking.model_revision"), first.index("$.component_schema_version"))
        self.assertLess(first.index("$.component_schema_version"), first.index("$.z_unknown"))

    def test_component_schemas_own_complete_standalone_property_definitions(self):
        self.assertEqual(set(COMPONENT_SCHEMAS.values()),
                         {p.name for p in (CLI_ROOT / "config/job-components/schemas").glob("*.schema.json")})
        _validator.cache_clear()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            for kind in PROFILES:
                filename = COMPONENT_SCHEMAS[f"{kind}-profile"]
                validator = _validator("job-components/schemas", filename)
                self.assertIs(type(validator), Draft202012Validator)
                self.assertIs(validator, _validator("job-components/schemas", filename))
                validate_component(profile(kind), f"{kind}-profile")
                for keyword in ("default", "$ref", "$dynamicRef", "$recursiveRef"):
                    self.assertNotIn(json.dumps(keyword), json.dumps(validator.schema))
                settings = validator.schema["properties"][kind]
                self.assertEqual(set(settings["properties"]), set(profile(kind)[kind]))
                self.assertEqual(set(settings["required"]), set(profile(kind)[kind]))
                self.assertFalse(settings["additionalProperties"])
                # A plain validator gets only this document, with no registry.
                standalone = Draft202012Validator(validator.schema)
                standalone.validate(profile(kind))
                for key in profile(kind)[kind]:
                    incomplete = profile(kind)
                    del incomplete[kind][key]
                    self.assertFalse(standalone.is_valid(incomplete), (kind, key))

    def test_fixtures_match_maintained_policies_and_validate_in_existing_jobs(self):
        paths = list((CLI_ROOT / "jobs").rglob("*.json"))
        self.assertEqual(len(paths), 26)
        for kind, (_, command) in PROFILES.items():
            for path in sorted((CLI_ROOT / "jobs").rglob(f"{command}.*.json")):
                job = json.loads(path.read_text())
                with self.subTest(path=path):
                    self.assertEqual(job[kind], profile(kind)[kind])
                    job[kind] = profile(kind)[kind]
                    validate_job(job, command, path)

    def test_existing_error_domains_are_preserved(self):
        with self.assertRaises(ConfigurationError):
            validate_job({}, "prep-subject")
        with self.assertRaises(ProcessingError):
            validate_artifact({}, "chapter metadata")
        with self.assertRaises(ConfigurationError) as raised:
            validate_component({}, "secret-unknown-kind")
        self.assertNotIn("secret-unknown-kind", str(raised.exception))

    def test_component_validation_does_not_load_job_definition_schemas(self):
        _validator.cache_clear()
        self.addCleanup(_validator.cache_clear)
        from gurubodh.schema_validation import schema_path

        def missing_job(kind, filename):
            if kind == "jobs":
                raise AssertionError("Job component schemas must be independent")
            return schema_path(kind, filename)

        with patch("gurubodh.schema_validation.schema_path", side_effect=missing_job):
            for kind in PROFILES:
                validate_component(profile(kind), f"{kind}-profile")
                payload = profile(kind)
                del payload[kind]["provider"]
                self.assert_invalid(payload, kind, f"$.{kind}.provider is required")

    def test_missing_component_schema_fails_in_configuration_domain(self):
        from gurubodh.schema_validation import SchemaDefinitionError

        _validator.cache_clear()
        self.addCleanup(_validator.cache_clear)
        with patch("gurubodh.schema_validation.schema_path", side_effect=SchemaDefinitionError("Component schema missing")):
            with self.assertRaisesRegex(ConfigurationError, "Component schema missing"):
                validate_component(profile("chunking"), "chunking-profile")

    def test_unregistered_schema_reference_fails_without_network_or_uri_echo(self):
        from gurubodh.schema_validation import schema_path

        filename = COMPONENT_SCHEMAS["chunking-profile"]
        schema = json.loads(schema_path("job-components/schemas", filename).read_text())
        schema["properties"]["chunking"]["$ref"] = "https://example.invalid/secret-schema"
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / filename
            broken.write_text(json.dumps(schema))

            def replacement(kind, name):
                return broken if kind == "job-components/schemas" else schema_path(kind, name)

            _validator.cache_clear()
            self.addCleanup(_validator.cache_clear)
            with patch("gurubodh.schema_validation.schema_path", side_effect=replacement), \
                 patch("socket.socket", side_effect=AssertionError("network forbidden")):
                with self.assertRaises(ConfigurationError) as raised:
                    validate_component(profile("chunking"), "chunking-profile")
            self.assertIn("reference could not be resolved locally", str(raised.exception))
            self.assertNotIn("secret-schema", str(raised.exception))

    def test_installed_schema_lookup_honors_relocated_distribution_records(self):
        from pathlib import PurePosixPath

        from gurubodh.resource_discovery import _installed_resource_path

        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            metadata = prefix / "lib/python3.12/site-packages/gurubodh_cli-0.1.0.dist-info"
            metadata.mkdir(parents=True)
            (metadata / "METADATA").write_text("Name: gurubodh_cli\nVersion: 0.1.0\n")
            relative = "config/job-components/schemas/chunking_profile.schema.json"
            schema = prefix / relative
            schema.parent.mkdir(parents=True)
            schema.write_text("{}")
            (metadata / "RECORD").write_text(f"../../../{relative},,\n")
            with patch(
                "gurubodh.resource_discovery._distribution_for_import",
                return_value=PathDistribution(metadata),
            ):
                actual = _installed_resource_path(PurePosixPath(relative))
                self.assertEqual(actual.resolve(), schema.resolve())
                self.assertTrue(actual.is_file())
                self.assertIsNone(
                    _installed_resource_path(PurePosixPath("config/jobs/absent.schema.json"))
                )


if __name__ == "__main__":
    unittest.main()
