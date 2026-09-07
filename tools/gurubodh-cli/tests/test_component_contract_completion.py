"""S4 cross-kind ownership and exhaustive job-field ownership reconciliation."""

import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

import gurubodh.schema_validation as validation
import component_contract_cases as cases


CLI_ROOT = Path(__file__).parents[1]
MAPPING = CLI_ROOT / "tests/fixtures/job-components/assembled-job-field-mapping.json"
# Independent expected registration, not computed from production registration.
SCHEMAS = {
    "subject-manifest": "subject_manifest.schema.json",
    "command-definition": "command_definition.schema.json",
    "environment": "environment.schema.json",
    "storage-profile": "storage_profile.schema.json",
    "locale-definition": "locale_definition.schema.json",
    "proofreading-profile": "proofreading_profile.schema.json",
    "chunking-profile": "chunking_profile.schema.json",
}


def declared_paths(schema):
    """Inventory schema fields (including containers/items), resolving local refs only."""
    paths = set()

    def visit(node, path):
        if not isinstance(node, dict):
            return
        if "$ref" in node:
            ref = node["$ref"]
            if not ref.startswith("#/"):
                raise AssertionError(f"external property reference: {ref}")
            target = schema
            for part in ref[2:].split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
            visit(target, path)
        paths.add(path)
        for name, child in node.get("properties", {}).items():
            visit(child, f"{path}.{name}")
        for child in node.get("patternProperties", {}).values():
            visit(child, f"{path}.*")
        if "items" in node:
            visit(node["items"], f"{path}[]")
        for key in ("oneOf", "anyOf", "allOf"):
            for child in node.get(key, []):
                visit(child, path)
        for key in ("if", "then", "else"):
            if key in node:
                visit(node[key], path)

    visit(schema, "$")
    return paths


class AllComponentContractTests(unittest.TestCase):
    def test_all_seven_own_the_exact_schema_used_by_cached_validation(self):
        self.assertEqual(validation.COMPONENT_SCHEMAS, SCHEMAS)

        def check_local(node):
            if isinstance(node, dict):
                self.assertNotIn("default", node)
                for key in ("$ref", "$dynamicRef", "$recursiveRef"):
                    if key in node:
                        self.assertTrue(node[key].startswith("#/$defs/"), node[key])
                if node.get("type") == "object":
                    self.assertIs(node.get("additionalProperties"), False)
                for child in node.values():
                    check_local(child)
            elif isinstance(node, list):
                for child in node:
                    check_local(child)

        with cases.without_job_schemas():
            for kind, filename in SCHEMAS.items():
                with self.subTest(kind=kind):
                    raw = json.loads(validation.schema_path("job-components/schemas", filename).read_text())
                    check_local(raw)
                    Draft202012Validator.check_schema(raw)
                    cached = validation._validator("job-components/schemas", filename)
                    self.assertIs(type(cached), Draft202012Validator)
                    self.assertIs(cached, validation._validator("job-components/schemas", filename))
                    # Loading/validation may not synthesize missing schema properties.
                    self.assertEqual(cached.schema, raw)
                    self.assertTrue(declared_paths(raw))

    def test_all_existing_validation_cases_with_job_schema_access_forbidden(self):
        suite = cases.validation_suite()
        expected = suite.countTestCases()
        with cases.without_job_schemas():
            result = unittest.TestResult()
            suite.run(result)
        self.assertEqual(result.testsRun, expected)
        self.assertFalse(result.skipped)
        self.assertTrue(result.wasSuccessful(), "\n".join(
            detail for _, detail in result.errors + result.failures))


class FieldMappingTests(unittest.TestCase):
    def test_every_job_field_has_exactly_one_owner(self):
        inventories = {command: {} for command in ("prep", "chunks", "docx")}
        for row in json.loads(MAPPING.read_text(encoding="utf-8"))["fields"]:
            owner, presence = row["owner"], row["presence"]
            self.assertTrue(owner and presence, row)
            for command in row["commands"]:
                for field in row["paths"]:
                    self.assertNotIn(field, inventories[command], (command, field))
                    inventories[command][field] = (owner, presence)
        for short, command in (("prep", "prep-subject"), ("chunks", "generate-chunks"),
                               ("docx", "generate-docx")):
            schema = validation._validator("jobs", validation.JOB_SCHEMAS[command]).schema
            self.assertEqual(set(inventories[short]), declared_paths(schema), command)


if __name__ == "__main__":
    unittest.main()
