import json
import tempfile
import unittest
from pathlib import Path

from gurubodh.contracts import CandidateManifestBinding, MaterializedSource
from gurubodh.derived_artifact_lifecycle import (
    AuditResult,
    DerivedArtifactDefinition,
    destination_subject_dir,
    run_derived_artifact_lifecycle,
)
from gurubodh.errors import GurubodhError


OUTPUT = Path("chapters") / "derived-test"
REPORTS = Path("run_reports") / "generate-docx"
DEFINITION = DerivedArtifactDefinition(
    command_name="generate-docx",
    output_relative_dir=OUTPUT,
    readiness_manifest_filename="ready.json",
    report_relative_dir=REPORTS,
)


def local_config(root):
    section = {
        "backend": "local",
        "root_dir": str(root),
        "subject_dir": "123_subject/hi-IN",
    }
    return {"source": dict(section), "destination": dict(section)}


def r2_config(root):
    config = local_config(root)
    config["destination"] = {
        "backend": "r2",
        "bucket": "test-bucket",
        "prefix": "cms_library",
        "subject_dir": "123_subject/hi-IN",
        "url_base": None,
    }
    return config


class FakeR2Client:
    def __init__(self, objects=None, fail_artifact_upload=False):
        self.objects = dict(objects or {})
        self.fail_artifact_upload = fail_artifact_upload
        self.events = []

    def prefix_has_objects(self, bucket, prefix):
        return any(key.startswith(prefix) for key in self.objects)

    def exists(self, bucket, key):
        return key in self.objects

    def list_keys(self, bucket, prefix):
        return sorted(key for key in self.objects if key.startswith(prefix))

    def upload_file(self, path, bucket, key):
        self.events.append(("upload", key))
        if self.fail_artifact_upload and key.endswith("artifact.txt"):
            raise RuntimeError("simulated artifact upload failure")
        self.objects[key] = Path(path).read_bytes()

    def delete_keys(self, bucket, keys):
        self.events.append(("delete_keys", tuple(keys)))
        for key in keys:
            self.objects.pop(key, None)
        return list(keys)

    def delete_prefix(self, bucket, prefix):
        self.events.append(("delete_prefix", prefix))
        keys = self.list_keys(bucket, prefix)
        for key in keys:
            self.objects.pop(key, None)
        return keys

    def download_file(self, bucket, key, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(self.objects[key])


class DummyWorkflow:
    def __init__(
        self,
        destination_subject,
        final_output,
        generation_error=None,
        validation_error=None,
        appear_after_preflight=False,
        r2_client=None,
        r2_appear_key=None,
    ):
        self.destination_subject = Path(destination_subject)
        self.final_output = Path(final_output)
        self.generation_error = generation_error
        self.validation_error = validation_error
        self.appear_after_preflight = appear_after_preflight
        self.r2_client = r2_client
        self.r2_appear_key = r2_appear_key
        self.audit_index = 0

    def materialize_and_validate_source(self, r2_client, progress):
        return MaterializedSource(
            subject_dir=self.destination_subject,
            candidate_manifest=CandidateManifestBinding(
                path=self.destination_subject / "candidate.json",
                sha256="candidate",
                reference={},
                chapters=(),
                selected_chapters=(),
            ),
            sources=[],
        )

    def generate_staged_artifacts(self, source, staged_output, progress):
        if self.final_output.exists() and not self.appear_after_preflight:
            self.asserted_prior_output_present = True
        if self.appear_after_preflight:
            self.final_output.mkdir(parents=True, exist_ok=True)
            (self.final_output / "appeared.txt").write_text("appeared", encoding="utf-8")
        if self.r2_client and self.r2_appear_key:
            self.r2_client.objects[self.r2_appear_key] = b"appeared"
        if self.generation_error:
            raise self.generation_error
        artifact = staged_output / "artifact.txt"
        artifact.write_text("replacement", encoding="utf-8")
        return {"artifact": artifact.name}

    def build_readiness_manifest(self, source, generation):
        return {"ready": True, "artifact": generation["artifact"]}

    def validate_staged_package(self, source, generation, staged_output, readiness_manifest):
        if self.validation_error:
            raise self.validation_error
        json.loads(readiness_manifest.read_text(encoding="utf-8"))
        if not (staged_output / generation["artifact"]).is_file():
            raise ValueError("missing staged artifact")

    def write_audit(
        self,
        status,
        lifecycle,
        source,
        generation,
        publication,
        failure,
        announce,
    ):
        self.audit_index += 1
        report = {
            "status": status,
            "lifecycle": lifecycle.as_dict(),
            "publication": publication,
            "failure": failure,
        }
        directory = self.destination_subject / REPORTS
        directory.mkdir(parents=True, exist_ok=True)
        paths = {
            "json": directory / f"audit-{self.audit_index}.json",
            "markdown": directory / f"audit-{self.audit_index}.md",
        }
        paths["json"].write_text(json.dumps(report) + "\n", encoding="utf-8")
        paths["markdown"].write_text(f"status: {status}\n", encoding="utf-8")
        return AuditResult(report, paths)


class DerivedArtifactLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def run_local(self, workflow, overwrite=False, revalidator=lambda *args: None):
        return run_derived_artifact_lifecycle(
            local_config(self.root),
            DEFINITION,
            workflow,
            overwrite=overwrite,
            progress=lambda _: None,
            destination_subject=workflow.destination_subject,
            source_revalidator=revalidator,
        )

    def test_success_exposes_the_ordered_seven_state_contract(self):
        subject = self.root / "123_subject/hi-IN"
        workflow = DummyWorkflow(subject, subject / OUTPUT)

        result = self.run_local(workflow)

        self.assertEqual(
            [entry["state"] for entry in result.lifecycle["transitions"]],
            [
                "preflight",
                "source_validation",
                "generation",
                "staged_validation",
                "source_revalidation",
                "publication",
                "success_audit",
            ],
        )
        self.assertEqual((subject / OUTPUT / "artifact.txt").read_text(), "replacement")
        self.assertTrue((subject / OUTPUT / "ready.json").is_file())

    def test_prepublication_failures_preserve_an_existing_local_set(self):
        for failing_state in ("generation", "staged_validation", "source_revalidation"):
            with self.subTest(failing_state=failing_state):
                subject = self.root / failing_state / "123_subject/hi-IN"
                output = subject / OUTPUT
                output.mkdir(parents=True)
                previous = output / "previous.txt"
                previous.write_text("previous", encoding="utf-8")
                workflow = DummyWorkflow(
                    subject,
                    output,
                    generation_error=RuntimeError("generation failed")
                    if failing_state == "generation"
                    else None,
                    validation_error=RuntimeError("validation failed")
                    if failing_state == "staged_validation"
                    else None,
                )
                revalidator = (
                    (lambda *args: (_ for _ in ()).throw(RuntimeError("source changed")))
                    if failing_state == "source_revalidation"
                    else (lambda *args: None)
                )

                with self.assertRaises(GurubodhError):
                    self.run_local(workflow, overwrite=True, revalidator=revalidator)

                self.assertEqual(previous.read_text(encoding="utf-8"), "previous")
                report = json.loads(
                    next((subject / REPORTS).glob("*.json")).read_text(encoding="utf-8")
                )
                self.assertEqual(report["failure"]["state"], failing_state)

    def test_destination_appearing_after_preflight_is_not_modified(self):
        subject = self.root / "appeared/123_subject/hi-IN"
        output = subject / OUTPUT
        workflow = DummyWorkflow(subject, output, appear_after_preflight=True)

        with self.assertRaisesRegex(GurubodhError, "appeared after preflight"):
            self.run_local(workflow)

        self.assertEqual((output / "appeared.txt").read_text(), "appeared")

    def test_r2_manifest_is_last_and_failure_audit_is_uploaded(self):
        config = r2_config(self.root)
        root = "cms_library/123_subject/hi-IN"
        manifest_key = f"{root}/chapters/derived-test/ready.json"
        old_key = f"{root}/chapters/derived-test/old.txt"

        for should_fail in (False, True):
            with self.subTest(should_fail=should_fail):
                client = FakeR2Client(
                    {manifest_key: b"old", old_key: b"old"},
                    fail_artifact_upload=should_fail,
                )
                destination_subject, destination_temporary = destination_subject_dir(
                    config, DEFINITION.command_name
                )
                workflow = DummyWorkflow(
                    destination_subject, destination_subject / OUTPUT
                )
                arguments = dict(
                    config=config,
                    definition=DEFINITION,
                    workflow=workflow,
                    overwrite=True,
                    r2_client=client,
                    progress=lambda _: None,
                    destination_subject=destination_subject,
                    destination_temporary=destination_temporary,
                    source_revalidator=lambda *args: None,
                )
                if should_fail:
                    with self.assertRaisesRegex(GurubodhError, "simulated artifact"):
                        run_derived_artifact_lifecycle(**arguments)
                    self.assertNotIn(manifest_key, client.objects)
                    self.assertTrue(
                        any("/run_reports/generate-docx/" in key for key in client.objects)
                    )
                else:
                    result = run_derived_artifact_lifecycle(**arguments)
                    output_uploads = [
                        key
                        for event, key in client.events
                        if event == "upload" and "/chapters/derived-test/" in key
                    ]
                    self.assertEqual(output_uploads[-1], manifest_key)
                    self.assertTrue(result.publication["manifest_published_last"])

    def test_r2_destination_appearing_after_preflight_is_not_modified(self):
        config = r2_config(self.root)
        root = "cms_library/123_subject/hi-IN"
        appeared_key = f"{root}/chapters/derived-test/ready.json"
        client = FakeR2Client()
        destination_subject, destination_temporary = destination_subject_dir(
            config, DEFINITION.command_name
        )
        workflow = DummyWorkflow(
            destination_subject,
            destination_subject / OUTPUT,
            r2_client=client,
            r2_appear_key=appeared_key,
        )

        with self.assertRaisesRegex(GurubodhError, "appeared after preflight"):
            run_derived_artifact_lifecycle(
                config,
                DEFINITION,
                workflow,
                r2_client=client,
                progress=lambda _: None,
                destination_subject=destination_subject,
                destination_temporary=destination_temporary,
                source_revalidator=lambda *args: None,
            )

        self.assertEqual(client.objects[appeared_key], b"appeared")
        self.assertFalse(any(event[0].startswith("delete") for event in client.events))


if __name__ == "__main__":
    unittest.main()
