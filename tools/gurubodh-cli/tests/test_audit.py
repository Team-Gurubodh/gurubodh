import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gurubodh.audit import (
    AUDIT_ENVELOPE_KEYS,
    AUDIT_REPORT_SCHEMA_NAME,
    AUDIT_REPORT_SCHEMA_VERSION,
    REDACTED,
    AuditContext,
    AuditWriter,
    bounded_failure,
    deterministic_json,
    report_paths,
    safe_configuration_snapshot,
)
from gurubodh.errors import GurubodhError
from gurubodh.proofreading.errors import ProofreadingError
from gurubodh.schema_validation import validate_artifact


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def context(self):
        config = {
            "schema_version": "1.0.0",
            "pipeline": "test-pipeline",
            "source": {"backend": "local", "root_dir": str(self.root)},
            "destination": {"backend": "local", "root_dir": str(self.root)},
        }
        with patch("gurubodh.audit.resolved_build_provenance") as provenance:
            provenance.return_value = {
                "source": "unavailable",
                "source_revision": None,
                "image_revision": None,
                "image_version": None,
                "image_created": None,
            }
            return AuditContext.create(
                "test-command",
                "gurubodh test-command",
                self.root,
                config=config,
                run_id="test-run",
                started_at="2026-09-04T00:00:00Z",
            )

    def test_writer_emits_the_v2_envelope_and_common_write_result(self):
        context = self.context()
        writer = AuditWriter(
            context,
            report_paths(self.root, "audit", "test-command"),
        )

        result = writer.write(
            status="succeeded",
            job_identity={"job_id": "job"},
            processing_summary={"processed": 1},
            lifecycle={"current_state": "succeeded", "transitions": []},
            publication={"backend": "local", "status": "succeeded"},
            failure=None,
            command_details={"items": []},
            renderer=lambda report: f"status: {report['run_identity']['status']}",
        )

        self.assertEqual(set(result.report), AUDIT_ENVELOPE_KEYS)
        self.assertEqual(result.report["schema_name"], AUDIT_REPORT_SCHEMA_NAME)
        self.assertEqual(result.report["schema_version"], AUDIT_REPORT_SCHEMA_VERSION)
        self.assertEqual(
            result.paths["json"].read_text(encoding="utf-8"),
            deterministic_json(result.report),
        )
        self.assertEqual(
            result.paths["markdown"].read_text(encoding="utf-8"),
            "status: succeeded\n",
        )
        self.assertEqual(
            result.local_writes["json"].bytes_written,
            result.paths["json"].stat().st_size,
        )
        self.assertEqual(result.references, result.report["report_artifacts"])

    def test_configuration_snapshot_redacts_secrets_and_omits_runtime_objects(self):
        runtime_client = object()
        snapshot = safe_configuration_snapshot(
            {
                "schema_version": "1.0.0",
                "source": {
                    "api_key": "secret-value",
                    "access-token": "secret-token",
                    "max_estimated_input_tokens_per_minute": 20000,
                    "runtime_client": runtime_client,
                    "_compiled_pattern": "private-runtime-value",
                },
                "unlisted_runtime": runtime_client,
            }
        )

        self.assertEqual(snapshot["source"]["api_key"], REDACTED)
        self.assertEqual(snapshot["source"]["access-token"], REDACTED)
        self.assertEqual(
            snapshot["source"]["max_estimated_input_tokens_per_minute"], 20000
        )
        self.assertNotIn("runtime_client", snapshot["source"])
        self.assertNotIn("_compiled_pattern", snapshot["source"])
        self.assertNotIn("unlisted_runtime", snapshot)

    def test_v1_reports_are_an_explicit_incompatible_major_version(self):
        writer = AuditWriter(
            self.context(), report_paths(self.root, "audit", "test-command")
        )
        report = writer.build_envelope(
            status="succeeded",
            job_identity=None,
            processing_summary={},
            lifecycle=None,
            publication={"backend": "local", "status": "not_applicable"},
            failure=None,
            command_details={},
        )
        validate_artifact(report, "audit report")

        old_report = copy.deepcopy(report)
        old_report["schema_version"] = "1.0.0"
        with self.assertRaisesRegex(
            GurubodhError, r'\$\.schema_version must equal "2\.0\.0"'
        ):
            validate_artifact(old_report, "audit report")

    def test_failure_shape_is_bounded_and_provider_neutral(self):
        error = ProofreadingError(
            "service_unavailable",
            "failure " * 200,
            request_diagnostics={
                "attempts": [{"attempt": 1, "http_status": 503}],
                "terminal_retry_exhaustion_reason": "service_unavailable_retry_exhausted",
            },
        )

        failure = bounded_failure(error, "proofreading")

        self.assertEqual(
            set(failure),
            {"stage", "code", "error_type", "message", "request_diagnostics"},
        )
        self.assertEqual(failure["stage"], "proofreading")
        self.assertEqual(failure["code"], "service_unavailable")
        self.assertLessEqual(len(failure["message"]), 500)
        self.assertEqual(
            failure["request_diagnostics"]["attempts"][0]["http_status"], 503
        )


if __name__ == "__main__":
    unittest.main()
