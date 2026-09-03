import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

from gurubodh.config import (
    load_generate_chunks_job,
    load_generate_docx_job,
    load_prep_subject_job,
)
from gurubodh.schema_validation import (
    ARTIFACT_SCHEMAS,
    JOB_SCHEMAS,
    SchemaDefinitionError,
    _validator,
    validate_job,
    write_json_artifact,
)


CLI_ROOT = Path(__file__).parents[1]


class SchemaValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.temp_dir = Path(self.temporary.name)

    def maintained_job(self, command):
        return json.loads(
            next((CLI_ROOT / "jobs").rglob(f"{command}.local.json")).read_text(
                encoding="utf-8"
            )
        )

    def write_job(self, payload, name="job.json"):
        path = self.temp_dir / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_every_maintained_job_validates_through_its_actual_loader(self):
        loaders = {
            "prep-subject": load_prep_subject_job,
            "generate-chunks": load_generate_chunks_job,
            "generate-docx": load_generate_docx_job,
        }

        for path in sorted((CLI_ROOT / "jobs").rglob("*.json")):
            command = path.name.split(".", 1)[0]
            with self.subTest(path=path):
                loaded = loaders[command](path)
                self.assertEqual(loaded["pipeline"], json.loads(path.read_text())["pipeline"])

    def test_job_validation_is_non_mutating_and_uses_explicit_draft_2020_12(self):
        payload = self.maintained_job("generate-chunks")
        original = copy.deepcopy(payload)

        validate_job(payload, "generate-chunks", "jobs/example.json")

        self.assertEqual(payload, original)
        validator = _validator("jobs", JOB_SCHEMAS["generate-chunks"])
        self.assertIs(type(validator), Draft202012Validator)
        self.assertIs(validator, _validator("jobs", JOB_SCHEMAS["generate-chunks"]))

    def test_unknown_properties_are_rejected_at_root_and_nested_boundaries(self):
        cases = []
        prep = self.maintained_job("prep-subject")
        prep["unexpected_root"] = True
        cases.append((load_prep_subject_job, prep, "$.unexpected_root is not allowed"))

        chunks = self.maintained_job("generate-chunks")
        chunks["chunking"]["unexpected_option"] = True
        cases.append((load_generate_chunks_job, chunks, "$.chunking.unexpected_option is not allowed"))

        docx = self.maintained_job("generate-docx")
        docx["naming"]["unexpected_name"] = "value"
        cases.append((load_generate_docx_job, docx, "$.naming.unexpected_name is not allowed"))

        for index, (loader, payload, expected) in enumerate(cases):
            with self.subTest(expected=expected), self.assertRaises(SystemExit) as raised:
                loader(self.write_job(payload, f"unknown-{index}.json"))
            self.assertIn(expected, str(raised.exception))

    def test_schema_rules_cover_required_type_const_pattern_numeric_conditionals_and_uniqueness(self):
        cases = []

        prep = self.maintained_job("prep-subject")
        prep.pop("source")
        cases.append((load_prep_subject_job, prep, "$.source is required"))

        prep = self.maintained_job("prep-subject")
        prep["chapter_split"]["enabled"] = "yes"
        cases.append((load_prep_subject_job, prep, "$.chapter_split.enabled must be boolean; found string"))

        docx = self.maintained_job("generate-docx")
        docx["schema_version"] = "9.9.9"
        cases.append((load_generate_docx_job, docx, '$.schema_version must equal "1.0.0"'))

        prep = self.maintained_job("prep-subject")
        prep["naming"]["category_code"] = "category"
        cases.append((load_prep_subject_job, prep, "$.naming.category_code must match ^CAT[0-9]{3}$"))

        prep = self.maintained_job("prep-subject")
        prep["proofreading"].pop("request_timeout_seconds")
        cases.append((load_prep_subject_job, prep, "$.proofreading.request_timeout_seconds is required"))

        chunks = self.maintained_job("generate-chunks")
        chunks["chunking"]["threshold_percentile"] = 101
        cases.append((load_generate_chunks_job, chunks, "$.chunking.threshold_percentile must be at most 100"))

        chunks = self.maintained_job("generate-chunks")
        chunks["chunking"].pop("strategy_version")
        cases.append((load_generate_chunks_job, chunks, "$.chunking.strategy_version is required"))

        chunks = self.maintained_job("generate-chunks")
        chunks["chunking"]["strategy_version"] = "semantic-window-v2"
        cases.append((load_generate_chunks_job, chunks, '$.chunking.strategy_version must equal "semantic-window-v1"'))

        docx = self.maintained_job("generate-docx")
        docx["source"].pop("root_dir")
        cases.append((load_generate_docx_job, docx, "$.source.root_dir is required"))

        chunks = self.maintained_job("generate-chunks")
        chunks["chapters"] = ["001", "001"]
        cases.append((load_generate_chunks_job, chunks, "$.chapters must not contain duplicate items"))

        for index, (loader, payload, expected) in enumerate(cases):
            with self.subTest(expected=expected), self.assertRaises(SystemExit) as raised:
                loader(self.write_job(payload, f"constraint-{index}.json"))
            self.assertIn(expected, str(raised.exception))

    def test_runtime_only_regex_and_subject_identity_checks_remain_enforced(self):
        prep = self.maintained_job("prep-subject")
        prep["chapter_split"] = {
            "enabled": True,
            "pattern_type": "regex",
            "pattern": "[",
            "flags": [],
        }
        with self.assertRaisesRegex(SystemExit, "not a valid regex"):
            load_prep_subject_job(self.write_job(prep, "bad-regex.json"))

        chunks = self.maintained_job("generate-chunks")
        chunks["destination"]["subject_dir"] = "different-subject/hi-IN"
        with self.assertRaisesRegex(SystemExit, "same language-qualified root"):
            load_generate_chunks_job(self.write_job(chunks, "mismatched-root.json"))

    def test_diagnostics_are_deterministic_and_do_not_echo_values(self):
        payload = self.maintained_job("generate-docx")
        payload.pop("schema_version")
        payload["z_unknown"] = "credential-like-secret-value"

        messages = []
        for name in ("first.json", "second.json"):
            with self.assertRaises(SystemExit) as raised:
                load_generate_docx_job(self.write_job(payload, name))
            messages.append(str(raised.exception).split(f", {self.temp_dir / name}", 1)[1])

        self.assertEqual(messages[0], messages[1])
        self.assertLess(messages[0].index("$.schema_version"), messages[0].index("$.z_unknown"))
        self.assertNotIn("credential-like-secret-value", messages[0])

    def test_all_bundled_artifact_schemas_compile_and_cache(self):
        self.assertEqual(
            set(ARTIFACT_SCHEMAS.values()),
            {path.name for path in (CLI_ROOT / "config" / "artifacts").glob("*.schema.json")},
        )
        self.assertEqual(
            set(JOB_SCHEMAS.values()),
            {path.name for path in (CLI_ROOT / "config" / "jobs").glob("*.schema.json")},
        )
        for artifact_name, filename in ARTIFACT_SCHEMAS.items():
            with self.subTest(artifact=artifact_name):
                validator = _validator("artifacts", filename)
                self.assertIs(type(validator), Draft202012Validator)
                self.assertIs(validator, _validator("artifacts", filename))

    def test_invalid_bundled_schema_fails_with_a_clear_definition_error(self):
        malformed = self.temp_dir / "malformed.schema.json"
        malformed.write_text("{", encoding="utf-8")
        with patch("gurubodh.schema_validation.schema_path", return_value=malformed):
            with self.assertRaisesRegex(SchemaDefinitionError, "unreadable or malformed"):
                _validator("jobs", "malformed-for-test.schema.json")

        invalid = self.temp_dir / "invalid.schema.json"
        invalid.write_text(
            json.dumps(
                {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "not-a-json-type",
                }
            ),
            encoding="utf-8",
        )
        with patch("gurubodh.schema_validation.schema_path", return_value=invalid):
            with self.assertRaisesRegex(SchemaDefinitionError, "Draft 2020-12 JSON Schema is invalid"):
                _validator("jobs", "invalid-for-test.schema.json")

    def test_invalid_artifact_payloads_fail_before_a_file_is_written(self):
        valid = {
            "schema_version": 1,
            "identity_contract_version": 1,
            "subject": {
                "category_code": "CAT001",
                "subject_code": "SUB123",
                "language": "hi-IN",
            },
            "chapters": [
                {
                    "generated_chapter_number": "001",
                    "content_key": "00000000-0000-5000-8000-000000000000",
                    "normalized_content_sha256": "a" * 64,
                    "metadata_artifact": {},
                    "text_artifact": {},
                }
            ],
        }
        valid_path = self.temp_dir / "valid.json"
        write_json_artifact(valid_path, valid, "chapter content manifest")
        self.assertTrue(valid_path.is_file())

        mutations = [
            ("missing.json", lambda payload: payload["chapters"][0].pop("content_key"), "$.chapters[0].content_key is required"),
            ("unexpected.json", lambda payload: payload["chapters"][0].update({"extra": True}), "$.chapters[0].extra is not allowed"),
            ("checksum.json", lambda payload: payload["chapters"][0].update({"normalized_content_sha256": "bad"}), "$.chapters[0].normalized_content_sha256 must match"),
        ]
        for filename, mutate, expected in mutations:
            payload = copy.deepcopy(valid)
            mutate(payload)
            output = self.temp_dir / filename
            with self.subTest(filename=filename), self.assertRaises(SystemExit) as raised:
                write_json_artifact(output, payload, "chapter content manifest")
            self.assertFalse(output.exists())
            message = str(raised.exception)
            self.assertIn("Artifact validation failed (chapter content manifest", message)
            self.assertIn(str(output), message)
            self.assertIn(expected, message)


if __name__ == "__main__":
    unittest.main()
