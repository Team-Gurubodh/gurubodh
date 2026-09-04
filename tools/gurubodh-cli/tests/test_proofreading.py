import json
import os
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gurubodh.config import proofreading_config, validate_pipeline_matches_source
from gurubodh.errors import GurubodhError
from gurubodh.locales import locale_spec
from gurubodh.proofreading import (
    EDIT_LIST_SCHEMA,
    GeminiProofreader,
    ProofreadingError,
    ProofreadingSettings,
    word_level_diff,
)
from gurubodh.schema_validation import validate_job


class FakeTypes:
    class GenerateContentConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs


class FakeResponse:
    def __init__(self, payload):
        self.text = json.dumps(payload, ensure_ascii=False)
        self.usage_metadata = None


class FakeModels:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return FakeResponse(response)


class FakeClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)


class HttpError(Exception):
    def __init__(self, status_code, status=None, message=None, headers=None):
        self.status_code = status_code
        self.status = status
        self.message = message
        self.response = SimpleNamespace(status_code=status_code, headers=headers or {})


class SdkReadTimeout(Exception):
    pass


SdkReadTimeout.__module__ = "httpx"


class ProofreadingTests(unittest.TestCase):
    def settings(self, **overrides):
        values = {"min_request_interval_seconds": 0, "max_requests_per_minute": 10}
        values.update(overrides)
        return ProofreadingSettings(**values)

    def test_word_level_diff_preserves_newlines_and_marks_replacement(self):
        rendered, summary = word_level_diff("पहला गलत शब्द।\n\nदूसरा वाक्य।", "पहला सही शब्द।\n\nदूसरा वाक्य।")

        self.assertIn("[-गलत-]{+सही+}", rendered)
        self.assertIn("\n\nदूसरा", rendered)
        self.assertEqual(summary["changed_segments"], 1)

    def test_proofreading_runtime_configuration_uses_explicit_job_values_and_cross_field_rule(self):
        job_path = Path(__file__).parents[1] / "jobs" / "subjects" / "sub123_spand_rahasya" / "hi-IN" / "prep-subject.local.json"
        job = json.loads(job_path.read_text(encoding="utf-8"))
        settings = proofreading_config(job)

        self.assertEqual(settings.model, "gemini-3.6-flash")
        self.assertEqual(settings.max_output_tokens, 16384)
        self.assertEqual(settings.request_timeout_seconds, 120)
        self.assertEqual(settings.request_progress_interval_seconds, 15)
        self.assertEqual(settings.unavailable_max_retries, 2)
        self.assertEqual(settings.unavailable_cooldown_seconds, 120)
        self.assertEqual(settings.public_dict()["request_timeout_seconds"], 120)
        with self.assertRaisesRegex(GurubodhError, "proofreading is required"):
            proofreading_config({})

        invalid = json.loads(json.dumps(job))
        invalid["proofreading"]["initial_retry_delay_seconds"] = 10
        invalid["proofreading"]["max_retry_delay_seconds"] = 5
        with self.assertRaisesRegex(GurubodhError, "max_retry_delay_seconds must be at least"):
            proofreading_config(invalid)

        invalid = json.loads(json.dumps(job))
        invalid["proofreading"]["request_timeout_seconds"] = 0
        with self.assertRaisesRegex(GurubodhError, "request_timeout_seconds must be greater than zero"):
            proofreading_config(invalid)

        invalid = json.loads(json.dumps(job))
        invalid["proofreading"]["request_timeout_seconds"] = 10
        invalid["proofreading"]["request_progress_interval_seconds"] = 11
        with self.assertRaisesRegex(GurubodhError, "must not exceed request_timeout_seconds"):
            proofreading_config(invalid)
        with self.assertRaisesRegex(ValueError, "unavailable_cooldown_seconds must be greater than zero"):
            ProofreadingSettings(unavailable_cooldown_seconds=0)

    def test_prep_subject_schema_rejects_invalid_new_operational_settings(self):
        job_path = Path(__file__).parents[1] / "jobs" / "subjects" / "sub123_spand_rahasya" / "hi-IN" / "prep-subject.local.json"
        valid_job = json.loads(job_path.read_text(encoding="utf-8"))
        validate_job(valid_job, "prep-subject", job_path)

        valid_job["proofreading"].pop("request_timeout_seconds")
        with self.assertRaisesRegex(GurubodhError, r"proofreading\.request_timeout_seconds.*is required"):
            validate_job(valid_job, "prep-subject", job_path)

        valid_job = json.loads(job_path.read_text(encoding="utf-8"))
        valid_job["proofreading"]["unavailable_cooldown_seconds"] = 0
        with self.assertRaisesRegex(GurubodhError, r"proofreading\.unavailable_cooldown_seconds"):
            validate_job(valid_job, "prep-subject", job_path)

    def test_pipeline_runtime_validation_rejects_the_wrong_entry_point(self):
        with self.assertRaisesRegex(GurubodhError, "cannot be processed"):
            validate_pipeline_matches_source(
                {"pipeline": "unicode-docx-ingest"},
                "legacy-docx-to-unicode",
            )

    def test_one_structured_response_produces_corrected_text_and_edit_list(self):
        client = FakeClient([{
            "corrected_text": "यह सही वाक्य है।",
            "edits": [{"original": "गलत", "corrected": "सही", "category": "spelling", "reason": "वर्तनी"}],
        }])
        proofreader = GeminiProofreader(self.settings(), locale=locale_spec("hi-IN"), client=client, types_module=FakeTypes)

        result = proofreader.proofread("यह गलत वाक्य है।")

        self.assertEqual(result["corrected_text"], "यह सही वाक्य है।")
        self.assertEqual(len(result["edits"]), 1)
        self.assertEqual(len(client.models.calls), 1)
        self.assertEqual(client.models.calls[0]["model"], "gemini-3.7-flash")
        self.assertNotIn("temperature", client.models.calls[0]["config"].kwargs)
        self.assertEqual(client.models.calls[0]["config"].kwargs["http_options"], {"timeout": 120000})

    def test_locale_selects_independently_authored_hindi_and_marathi_instructions(self):
        response = {
            "corrected_text": "योग्य मजकूर आहे.",
            "edits": [{"original": "चुकीचा", "corrected": "योग्य", "category": "spelling", "reason": "शब्दलेखन"}],
        }
        hindi_client = FakeClient([response])
        marathi_client = FakeClient([response])

        GeminiProofreader(
            self.settings(), locale=locale_spec("hi-IN"), client=hindi_client, types_module=FakeTypes
        ).proofread("चुकीचा मजकूर आहे.")
        GeminiProofreader(
            self.settings(), locale=locale_spec("mr-IN"), client=marathi_client, types_module=FakeTypes
        ).proofread("चुकीचा मजकूर आहे.")

        hindi_instruction = hindi_client.models.calls[0]["config"].kwargs["system_instruction"]
        marathi_instruction = marathi_client.models.calls[0]["config"].kwargs["system_instruction"]
        self.assertIn("हिंदी भाषा संपादक", hindi_instruction)
        self.assertIn("मराठी भाषा संपादक", marathi_instruction)
        self.assertNotEqual(hindi_instruction, marathi_instruction)

    def test_missing_gemini_credential_fails_before_a_request(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            with self.assertRaisesRegex(ProofreadingError, "Set GEMINI_API_KEY"):
                GeminiProofreader(self.settings(), locale=locale_spec("hi-IN")).proofread("यह गलत वाक्य है।")

    def test_gemini_schema_omits_unsupported_additional_properties(self):
        self.assertNotIn("additionalProperties", EDIT_LIST_SCHEMA)
        self.assertNotIn("additionalProperties", EDIT_LIST_SCHEMA["properties"]["edits"]["items"])

    def test_full_chapter_edit_is_rejected_to_keep_provenance_text_free(self):
        client = FakeClient([{
            "corrected_text": "यह सही वाक्य है।",
            "edits": [{"original": "यह गलत वाक्य है।", "corrected": "यह सही वाक्य है।", "category": "spelling", "reason": "वर्तनी"}],
        }])
        proofreader = GeminiProofreader(self.settings(), locale=locale_spec("hi-IN"), client=client, types_module=FakeTypes)

        with self.assertRaisesRegex(ProofreadingError, "full chapter text"):
            proofreader.proofread("यह गलत वाक्य है।")

    def test_api_error_includes_safe_gemini_status_without_response_body(self):
        client = FakeClient([HttpError(400, "INVALID_ARGUMENT", "Unsupported request setting")])
        proofreader = GeminiProofreader(self.settings(), locale=locale_spec("hi-IN"), client=client, types_module=FakeTypes)

        with self.assertRaisesRegex(ProofreadingError, r"HTTP 400 INVALID_ARGUMENT"):
            proofreader.proofread("यह गलत है।")

    def test_in_flight_progress_reports_elapsed_and_remaining_time_only_until_response(self):
        response = {
            "corrected_text": "यह सही है।",
            "edits": [{"original": "गलत", "corrected": "सही", "category": "spelling", "reason": "वर्तनी"}],
        }
        client = FakeClient([response])
        original_generate = client.models.generate_content

        def delayed_generate(**kwargs):
            time.sleep(0.03)
            return original_generate(**kwargs)

        client.models.generate_content = delayed_generate
        messages = []
        proofreader = GeminiProofreader(
            self.settings(request_timeout_seconds=1, request_progress_interval_seconds=0.005),
            locale=locale_spec("hi-IN"),
            client=client,
            types_module=FakeTypes,
        )

        proofreader.proofread("यह गलत है।", progress=messages.append)

        start = next(message for message in messages if message.startswith("Sending Gemini request"))
        self.assertIn("timeout 1.0 seconds", start)
        heartbeat_positions = [
            index for index, message in enumerate(messages) if message.startswith("Gemini request is still in progress")
        ]
        self.assertTrue(heartbeat_positions)
        self.assertTrue(all("elapsed" in messages[index] and "remaining" in messages[index] for index in heartbeat_positions))
        response_position = messages.index("Gemini response received; validating and writing canonical artifacts.")
        self.assertTrue(all(index < response_position for index in heartbeat_positions))

    def test_sdk_http_timeout_is_retried_with_accurate_attempt_counts(self):
        client = FakeClient([
            SdkReadTimeout("request timed out"),
            {"corrected_text": "यह सही है।", "edits": [{"original": "गलत", "corrected": "सही", "category": "spelling", "reason": "वर्तनी"}]},
        ])
        delays = []
        proofreader = GeminiProofreader(
            self.settings(max_retries=1, initial_retry_delay_seconds=1, max_retry_delay_seconds=1),
            locale=locale_spec("hi-IN"),
            client=client,
            types_module=FakeTypes,
            sleep=delays.append,
            random_value=lambda: 0,
        )

        result = proofreader.proofread("यह गलत है।")

        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["failed_request_attempts"], 1)
        self.assertEqual(delays, [1.0])

    def test_rate_limit_is_retried_with_backoff(self):
        client = FakeClient([
            HttpError(429),
            {"corrected_text": "यह सही है।", "edits": [{"original": "गलत", "corrected": "सही", "category": "spelling", "reason": "वर्तनी"}]},
        ])
        delays = []
        proofreader = GeminiProofreader(
            self.settings(initial_retry_delay_seconds=1, max_retry_delay_seconds=1),
            locale=locale_spec("hi-IN"),
            client=client,
            types_module=FakeTypes,
            sleep=delays.append,
            random_value=lambda: 0,
        )

        result = proofreader.proofread("यह गलत है।")

        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["successful_request_attempts"], 1)
        self.assertEqual(result["failed_request_attempts"], 1)
        self.assertEqual(delays, [1.0])

    def test_terminal_api_failure_records_every_request_attempt(self):
        client = FakeClient([HttpError(503), HttpError(503), HttpError(503)])
        proofreader = GeminiProofreader(
            self.settings(max_retries=1),
            locale=locale_spec("hi-IN"),
            client=client,
            types_module=FakeTypes,
            sleep=lambda _: None,
            random_value=lambda: 0,
        )

        with self.assertRaises(ProofreadingError) as raised:
            proofreader.proofread("यह गलत है।")

        self.assertEqual(raised.exception.code, "service_unavailable")
        self.assertEqual(raised.exception.request_attempts, 3)
        self.assertEqual(raised.exception.successful_request_attempts, 0)
        self.assertEqual(
            raised.exception.request_diagnostics["terminal_retry_exhaustion_reason"],
            "service_unavailable_retry_exhausted",
        )

    def test_503_uses_dedicated_30_then_90_second_recovery_schedule(self):
        client = FakeClient([
            HttpError(503, "UNAVAILABLE"),
            HttpError(503, "UNAVAILABLE"),
            {"corrected_text": "यह सही है।", "edits": [{"original": "गलत", "corrected": "सही", "category": "spelling", "reason": "वर्तनी"}]},
        ])
        delays = []
        proofreader = GeminiProofreader(
            self.settings(max_retries=9),
            locale=locale_spec("hi-IN"),
            client=client,
            types_module=FakeTypes,
            sleep=delays.append,
            random_value=lambda: 0,
        )

        result = proofreader.proofread("यह गलत है।")

        self.assertEqual(delays, [30.0, 90.0])
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(result["request_diagnostics"]["attempts"][0]["http_status"], 503)
        self.assertEqual(result["request_diagnostics"]["attempts"][1]["retry_delay_seconds"], 90.0)

    def test_503_uses_a_longer_retry_after_hint(self):
        client = FakeClient([
            HttpError(503, "UNAVAILABLE", headers={"retry-after": "45"}),
            {"corrected_text": "यह सही है।", "edits": [{"original": "गलत", "corrected": "सही", "category": "spelling", "reason": "वर्तनी"}]},
        ])
        delays = []
        proofreader = GeminiProofreader(
            self.settings(),
            locale=locale_spec("hi-IN"),
            client=client,
            types_module=FakeTypes,
            sleep=delays.append,
            random_value=lambda: 0,
        )

        result = proofreader.proofread("यह गलत है।")

        self.assertEqual(delays, [45.0])
        self.assertTrue(result["request_diagnostics"]["attempts"][0]["server_retry_hint_used"])

    def test_proofreader_reports_provider_retry_delay_to_operator(self):
        client = FakeClient([
            HttpError(429, "RESOURCE_EXHAUSTED", "Quota exceeded. Please retry in 35.089783349s."),
            {"corrected_text": "यह सही है।", "edits": [{"original": "गलत", "corrected": "सही", "category": "spelling", "reason": "वर्तनी"}]},
        ])
        delays, messages = [], []
        proofreader = GeminiProofreader(
            self.settings(),
            locale=locale_spec("hi-IN"),
            client=client,
            types_module=FakeTypes,
            sleep=delays.append,
            random_value=lambda: 0,
        )

        proofreader.proofread("यह गलत है।", progress=messages.append)

        self.assertEqual(delays, [35.089783349])
        self.assertEqual(messages[0], "Checking local Gemini request pacing before sending.")
        self.assertIn("Sending Gemini request (attempt 1; estimated input", messages[1])
        self.assertIn("retrying in 35.1 seconds (Gemini's requested retry delay)", messages[2])
        self.assertIn("Gemini response received; validating", messages[-1])


if __name__ == "__main__":
    unittest.main()
