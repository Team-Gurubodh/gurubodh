"""Issue #287 resource ownership and discovery boundaries."""

from contextlib import chdir
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from gurubodh.errors import ConfigurationError
from gurubodh.job_components import ComponentCatalog
from gurubodh.job_composition import resolve_job, resolve_lab_proofreading
from gurubodh.project import resolve_project_context


CLI_ROOT = Path(__file__).parents[1].resolve()
FIXTURES = CLI_ROOT / "tests/fixtures/job-components"


class ResourceDiscoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.project = self.root / "project"
        self.project.mkdir()
        for filename in ("aps-hindi.json", "unicode-bilingual.json"):
            document = json.loads((FIXTURES / "subjects" / filename).read_text())
            target = self.project / "jobs/subjects" / document["manifest_id"] / "manifest.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

    def resolve(self, catalog, command="prep-subject", subject="sub001_aps_example"):
        return resolve_job(
            catalog,
            command=command,
            manifest_id=subject,
            locale="hi-IN",
            environment_id="development",
            storage_profile_id="r2",
            environ={},
        ).job

    def test_manifest_only_project_uses_one_bundled_reusable_catalog(self):
        context = resolve_project_context(self.project)
        self.assertEqual(context.root, self.project)
        self.assertEqual(context.resource_root, CLI_ROOT)
        self.assertEqual(
            context.legacy_converter,
            (CLI_ROOT / "scripts/legacy_font_convert.js").resolve(),
        )
        catalog = ComponentCatalog(context.root, context.resource_root)
        for command in ("prep-subject", "generate-chunks", "generate-docx"):
            with self.subTest(command=command):
                job = self.resolve(catalog, command)
                self.assertEqual(job["source"]["backend"], "r2")
                self.assertEqual(job["destination"]["backend"], "r2")
        lab = resolve_lab_proofreading(catalog)
        self.assertEqual(lab.settings.model, "gemini-3.6-flash")
        self.assertEqual(lab.settings.max_output_tokens, 16384)

    def test_manifest_only_and_checkout_catalogs_resolve_identical_jobs(self):
        complete = self.root / "complete"
        shutil.copytree(CLI_ROOT / "config", complete / "config")
        shutil.copytree(self.project / "jobs", complete / "jobs")
        external_catalog = ComponentCatalog(self.project, CLI_ROOT)
        checkout_catalog = ComponentCatalog(complete)
        for command in ("prep-subject", "generate-chunks", "generate-docx"):
            with self.subTest(command=command):
                external = self.resolve(external_catalog, command)
                checkout = self.resolve(checkout_catalog, command)
                self.assertEqual(external.to_payload(), checkout.to_payload())
                self.assertEqual(
                    external.provenance.to_payload(), checkout.provenance.to_payload()
                )

    def test_explicit_project_catalog_wins_as_a_whole_and_never_falls_back(self):
        project_components = self.project / "config/job-components"
        environment_dir = project_components / "environments"
        environment_dir.mkdir(parents=True)
        environment = json.loads(
            (CLI_ROOT / "config/job-components/environments/development.json").read_text()
        )
        environment["stores"]["r2_source_library"]["bucket"] = "selected-project-catalog"
        (environment_dir / "development.json").write_text(json.dumps(environment))

        context = resolve_project_context(self.project)
        self.assertEqual(context.resource_root, self.project)
        catalog = ComponentCatalog(context.root, context.resource_root)
        selected = catalog.load("environment", "development").to_payload()
        self.assertEqual(
            selected["stores"]["r2_source_library"]["bucket"],
            "selected-project-catalog",
        )
        with self.assertRaisesRegex(ConfigurationError, "commands/prep-subject.json"):
            catalog.load("command-definition", "prep-subject")

    def test_unrelated_working_directory_resources_are_never_candidates(self):
        unrelated = self.root / "unrelated"
        fake = unrelated / "config/job-components/environments/development.json"
        fake.parent.mkdir(parents=True)
        fake.write_text('{"not": "a component"}', encoding="utf-8")
        with chdir(unrelated):
            context = resolve_project_context(self.project)
            loaded = ComponentCatalog(context.root, context.resource_root).load(
                "environment", "development"
            )
        self.assertEqual(loaded.to_payload()["environment_id"], "development")
        self.assertEqual(loaded.origin, "config/job-components/environments/development.json")

    def test_missing_packaged_policy_fails_without_python_fallback(self):
        resources = self.root / "resources"
        shutil.copytree(CLI_ROOT / "config/job-components", resources / "config/job-components")
        profile = resources / "config/job-components/profiles/proofreading/gemini-3.6-flash-v1.json"
        profile.unlink()
        catalog = ComponentCatalog(self.project, resources)
        with self.assertRaisesRegex(ConfigurationError, "resource is missing"):
            self.resolve(catalog)
        with self.assertRaisesRegex(ConfigurationError, "resource is missing"):
            resolve_lab_proofreading(catalog)

    def test_project_component_schemas_cannot_override_bundled_validators(self):
        schema = self.project / "config/job-components/schemas/environment.schema.json"
        schema.parent.mkdir(parents=True)
        schema.write_text("{}", encoding="utf-8")
        # Supplying the project root directly still selects its catalog, but
        # component validation remains bound to the bundled schema registry.
        source = CLI_ROOT / "config/job-components/environments/development.json"
        target = self.project / "config/job-components/environments/development.json"
        target.parent.mkdir(parents=True)
        target.write_bytes(source.read_bytes())
        loaded = ComponentCatalog(self.project).load("environment", "development")
        self.assertEqual(loaded.to_payload()["environment_id"], "development")
        target.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ConfigurationError, "component_schema_version"):
            ComponentCatalog(self.project).load("environment", "development")

    def test_manifest_only_roots_work_for_explicit_env_and_upward_selection(self):
        with patch.dict(os.environ, {"GURUBODH_CLI_ROOT": str(self.project)}, clear=True):
            self.assertEqual(resolve_project_context().root, self.project)
        nested = self.project / "work/nested"
        nested.mkdir(parents=True)
        with patch.dict(os.environ, {}, clear=True), patch(
            "pathlib.Path.cwd", return_value=nested
        ):
            self.assertEqual(resolve_project_context().root, self.project)


if __name__ == "__main__":
    unittest.main()
