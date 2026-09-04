import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from gurubodh.contracts import PrepSubjectJob
from gurubodh.locales import locale_spec
from gurubodh.naming import chapter_unmodified_source_filename
from gurubodh.paths import destination_paths_for_subject, ensure_job_dirs
from gurubodh.proofreading.artifacts import write_canonical_chapter_artifacts
from gurubodh.proofreading.errors import ProofreadingError
from gurubodh.proofreading.policy import (
    RequestPolicy,
    RequestRateLimiter,
    safe_request_diagnostics,
)
from gurubodh.proofreading.service import (
    ProofreadingService,
    RawProofreadingResponse,
)
from gurubodh.proofreading.settings import ProofreadingSettings
from gurubodh.proofreading.validation import parse_structured_response


class HttpError(Exception):
    def __init__(self, status_code, status=None, headers=None):
        self.status_code = status_code
        self.status = status
        self.response = SimpleNamespace(
            status_code=status_code, headers=headers or {}
        )


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class FakeTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
        self.last_request_elapsed_seconds = 0.0

    def send(self, text, progress=None):
        self.calls.append(text)
        return RawProofreadingResponse(
            text=json.dumps(self.payload, ensure_ascii=False),
            elapsed_seconds=0.25,
            usage={"input_tokens": 4},
        )


class FakeProofreader:
    def __init__(self):
        self.calls = []

    def proofread(self, text, progress=None):
        self.calls.append(text)
        return {
            "corrected_text": text.replace("गलत", "सही"),
            "edits": [
                {
                    "original": "गलत",
                    "corrected": "सही",
                    "category": "spelling",
                    "reason": "वर्तनी",
                }
            ],
            "estimated_input_tokens": 10,
            "attempts": 1,
            "successful_request_attempts": 1,
            "throttle_seconds": 0.0,
            "usage": {"input_tokens": 10},
            "request_diagnostics": None,
        }


def prep_job(root):
    payload = {
        "schema_version": "1.4.0",
        "pipeline": "unicode-docx-ingest",
        "source": {
            "backend": "local",
            "root_dir": str(root),
            "relative_path": "source.docx",
            "font_encoding": "unicode",
            "file_format": "docx",
        },
        "destination": {
            "backend": "local",
            "root_dir": str(root),
            "subject_dir": "subject/hi-IN",
        },
        "naming": {
            "category_code": "CAT001",
            "subject_code": "SUB123",
            "title_slug": "component-test",
            "version": "01",
            "subversion": "01",
        },
        "chapter_split": {
            "enabled": True,
            "pattern_type": "literal",
            "pattern": "CHAPTER",
        },
        "metadata_defaults": {
            "language": "hi-IN",
            "source_script": "Devanagari",
            "output_text_encoding": "UTF-8",
        },
    }
    return PrepSubjectJob(
        payload,
        locale_spec("hi-IN"),
        ProofreadingSettings(min_request_interval_seconds=0),
    )


class ProofreadingComponentTests(unittest.TestCase):
    def test_structured_validation_uses_plain_strings_and_returns_typed_values(self):
        result = parse_structured_response(
            json.dumps(
                {
                    "corrected_text": "यह सही है।",
                    "edits": [
                        {
                            "original": "गलत",
                            "corrected": "सही",
                            "category": "spelling",
                            "reason": "वर्तनी",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            "यह गलत है।",
            provider_name="Gemini",
        )

        self.assertEqual(result.corrected_text, "यह सही है।")
        self.assertEqual(result.edits[0].category, "spelling")
        self.assertEqual(result.edits[0].to_payload()["corrected"], "सही")

        with self.assertRaisesRegex(ProofreadingError, "valid structured JSON"):
            parse_structured_response(
                "not-json", "यह गलत है।", provider_name="Gemini"
            )

    def test_request_policy_classifies_and_schedules_without_a_gemini_client(self):
        settings = ProofreadingSettings(
            min_request_interval_seconds=3,
            unavailable_first_retry_delay_seconds=30,
            unavailable_second_retry_delay_seconds=90,
        )
        policy = RequestPolicy(
            settings, provider_name="Gemini", random_value=lambda: 0
        )
        failure = policy.classify(
            HttpError(503, "UNAVAILABLE", {"retry-after": "45"})
        )

        self.assertTrue(failure.retryable)
        self.assertEqual(failure.retry_limit, 2)
        first_retry = policy.retry_plan(failure, 1)
        second_retry = policy.retry_plan(failure, 2)
        self.assertEqual(first_retry.delay_seconds, 45)
        self.assertTrue(first_retry.server_retry_hint_used)
        self.assertEqual(second_retry.delay_seconds, 90)
        self.assertFalse(second_retry.server_retry_hint_used)

        terminal = policy.terminal_error(failure, 3, None)
        self.assertEqual(terminal.code, "service_unavailable")
        self.assertNotIn("retry-after", str(terminal))

        diagnostics = safe_request_diagnostics(
            {
                "attempts": [
                    {
                        "attempt": 1,
                        "http_status": 503,
                        "elapsed_seconds": 1.25,
                        "response_body": "यह गलत है।",
                    }
                ],
                "source_text": "यह गलत है।",
                "terminal_retry_exhaustion_reason": "service_unavailable_retry_exhausted",
            }
        )
        self.assertNotIn("यह गलत है।", json.dumps(diagnostics, ensure_ascii=False))

        clock = FakeClock()
        limiter = RequestRateLimiter(settings, clock=clock, sleep=clock.sleep)
        self.assertEqual(limiter.acquire(1), 0)
        self.assertEqual(limiter.acquire(1), 3)

    def test_provider_service_returns_the_shared_validated_contract(self):
        transport = FakeTransport(
            {
                "corrected_text": "यह सही है।",
                "edits": [
                    {
                        "original": "गलत",
                        "corrected": "सही",
                        "category": "spelling",
                        "reason": "वर्तनी",
                    }
                ],
            }
        )
        service = ProofreadingService(
            ProofreadingSettings(min_request_interval_seconds=0),
            transport,
            provider_name="Fake",
            locale=locale_spec("hi-IN"),
            sleep=lambda _: None,
            random_value=lambda: 0,
        )

        result = service.proofread("यह गलत है।")

        self.assertEqual(result["corrected_text"], "यह सही है।")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["usage"], {"input_tokens": 4})
        self.assertEqual(transport.calls, ["यह गलत है।"])

    def test_canonical_artifacts_use_a_fake_provider_without_an_sdk(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = prep_job(root)
            paths = destination_paths_for_subject(root / "subject" / "hi-IN")
            ensure_job_dirs(paths)
            source_path = paths["unmodified_source_text"] / (
                chapter_unmodified_source_filename(config, 1)
            )
            source_path.write_text("यह गलत है।\n", encoding="utf-8")
            proofreader = FakeProofreader()

            outcome = write_canonical_chapter_artifacts(
                config,
                paths,
                1,
                source_path,
                proofreader=proofreader,
            )

            self.assertEqual(proofreader.calls, ["यह गलत है।\n"])
            self.assertEqual(outcome.correction_count, 1)
            self.assertEqual(outcome.request_attempts, 1)
            self.assertTrue(
                (paths["subject"] / outcome.checkpoint_artifacts[-1].path).is_file()
            )
            serialized = json.dumps(
                outcome.proofreading_payload(), ensure_ascii=False
            )
            self.assertNotIn("यह गलत है।", serialized)
            self.assertNotIn("यह सही है।", serialized)


if __name__ == "__main__":
    unittest.main()
