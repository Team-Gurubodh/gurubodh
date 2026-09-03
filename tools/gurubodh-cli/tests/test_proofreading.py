import hashlib
import json
import os
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gurubodh.config import proofreading_config, validate_pipeline_matches_source
from gurubodh.content_identity import build_content_identity
from gurubodh.content_manifest import write_chapter_content_manifest
from gurubodh.locales import locale_spec
from gurubodh.naming import chapter_output_filename, chapter_unmodified_source_filename
from gurubodh.paths import destination_paths_for_subject, ensure_job_dirs
from gurubodh.proofreading import (
    EDIT_LIST_SCHEMA,
    GeminiProofreader,
    ProofreadingError,
    ProofreadingSettings,
    proofread_chapter_artifacts,
    word_level_diff,
)
from gurubodh.schema_validation import validate_job
from gurubodh.storage import owned_relative_paths


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


class FakeChapterProofreader:
    def __init__(self):
        self.inputs = []

    def proofread(self, text, progress=None):
        self.inputs.append(text)
        return {
            "corrected_text": "यह सही वाक्य है।\n",
            "edits": [{"original": "गलत", "corrected": "सही", "category": "spelling", "reason": "वर्तनी"}],
            "estimated_input_tokens": 20,
            "attempts": 1,
            "throttle_seconds": 0,
            "usage": {"input_tokens": 10},
        }


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
        with self.assertRaisesRegex(SystemExit, "proofreading is required"):
            proofreading_config({})

        invalid = json.loads(json.dumps(job))
        invalid["proofreading"]["initial_retry_delay_seconds"] = 10
        invalid["proofreading"]["max_retry_delay_seconds"] = 5
        with self.assertRaisesRegex(SystemExit, "max_retry_delay_seconds must be at least"):
            proofreading_config(invalid)

        invalid = json.loads(json.dumps(job))
        invalid["proofreading"]["request_timeout_seconds"] = 0
        with self.assertRaisesRegex(SystemExit, "request_timeout_seconds must be greater than zero"):
            proofreading_config(invalid)

        invalid = json.loads(json.dumps(job))
        invalid["proofreading"]["request_timeout_seconds"] = 10
        invalid["proofreading"]["request_progress_interval_seconds"] = 11
        with self.assertRaisesRegex(SystemExit, "must not exceed request_timeout_seconds"):
            proofreading_config(invalid)
        with self.assertRaisesRegex(ValueError, "unavailable_cooldown_seconds must be greater than zero"):
            ProofreadingSettings(unavailable_cooldown_seconds=0)

    def test_prep_subject_schema_rejects_invalid_new_operational_settings(self):
        job_path = Path(__file__).parents[1] / "jobs" / "subjects" / "sub123_spand_rahasya" / "hi-IN" / "prep-subject.local.json"
        valid_job = json.loads(job_path.read_text(encoding="utf-8"))
        validate_job(valid_job, "prep-subject", job_path)

        valid_job["proofreading"].pop("request_timeout_seconds")
        with self.assertRaisesRegex(SystemExit, r"proofreading\.request_timeout_seconds.*is required"):
            validate_job(valid_job, "prep-subject", job_path)

        valid_job = json.loads(job_path.read_text(encoding="utf-8"))
        valid_job["proofreading"]["unavailable_cooldown_seconds"] = 0
        with self.assertRaisesRegex(SystemExit, r"proofreading\.unavailable_cooldown_seconds"):
            validate_job(valid_job, "prep-subject", job_path)

    def test_pipeline_runtime_validation_rejects_the_wrong_entry_point(self):
        with self.assertRaisesRegex(SystemExit, "cannot be processed"):
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

    def test_mismatched_gemini_prompt_locale_is_rejected_before_request(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = {
                "pipeline": "unicode-docx-ingest",
                "source": {"backend": "local", "root_dir": temp_dir, "relative_path": "source.docx", "font_encoding": "unicode", "file_format": "docx"},
                "destination": {"backend": "local", "root_dir": temp_dir, "subject_dir": "subject/mr-IN"},
                "naming": {"category_code": "CAT001", "subject_code": "SUB123", "title_slug": "spand-rahasya", "version": "01", "subversion": "01"},
                "metadata_defaults": {"language": "mr-IN", "source_script": "Devanagari", "output_text_encoding": "UTF-8"},
                "_proofreading_config": self.settings(),
            }
            paths = destination_paths_for_subject(root / "subject" / "mr-IN")
            ensure_job_dirs(paths)
            source_path = paths["unmodified_source_text"] / chapter_unmodified_source_filename(config, 1)
            source_path.write_text("चुकीचा मजकूर आहे.\n", encoding="utf-8")
            client = FakeClient([{
                "corrected_text": "योग्य मजकूर आहे.",
                "edits": [{"original": "चुकीचा", "corrected": "योग्य", "category": "spelling", "reason": "शब्दलेखन"}],
            }])
            proofreader = GeminiProofreader(
                self.settings(), locale=locale_spec("hi-IN"), client=client, types_module=FakeTypes
            )

            with self.assertRaisesRegex(ProofreadingError, "does not match chapter metadata language"):
                proofread_chapter_artifacts(config, paths, proofreader=proofreader)

            self.assertEqual(client.models.calls, [])

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

    def test_proofreading_writes_exact_canonical_five_artifacts_without_full_text_in_details(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = {
                "pipeline": "unicode-docx-ingest",
                "source": {"backend": "local", "root_dir": temp_dir, "relative_path": "source.docx", "font_encoding": "unicode", "file_format": "docx"},
                "destination": {"backend": "local", "root_dir": temp_dir, "subject_dir": "subject/hi-IN"},
                "naming": {"category_code": "CAT001", "subject_code": "SUB123", "title_slug": "spand-rahasya", "version": "01", "subversion": "01"},
                "metadata_defaults": {"language": "hi-IN", "source_script": "Devanagari", "output_text_encoding": "UTF-8", "summary_chapter_markers": ["सही"]},
                "_proofreading_config": self.settings(),
            }
            paths = destination_paths_for_subject(root / "subject")
            ensure_job_dirs(paths)
            source_text = "यह गलत वाक्य है।\n"
            source_name = chapter_unmodified_source_filename(config, 1)
            source_path = paths["unmodified_source_text"] / source_name
            source_path.write_text(source_text, encoding="utf-8")
            fake = FakeChapterProofreader()

            output = StringIO()
            with redirect_stdout(output):
                result = proofread_chapter_artifacts(
                    config,
                    paths,
                    entry_point="python3 -m gurubodh prep-subject",
                    proofreader=fake,
                    progress=lambda *_: None,
                )

            self.assertEqual(result["counts"], {"succeeded": 1, "failed": 0, "skipped": 0})
            self.assertIn("Preparing 1 chapter(s) for sequential Gemini proofreading", output.getvalue())
            self.assertIn("Unmodified source is ready", output.getvalue())
            self.assertEqual(fake.inputs, [source_text])
            text_name = chapter_output_filename(config, 1, ".txt")
            metadata_name = chapter_output_filename(config, 1, ".json")
            text_path = paths["text_and_metadata"] / text_name
            metadata_path = paths["text_and_metadata"] / metadata_name
            details_path = paths["proofreading"] / f"{Path(text_name).stem}.proofread.json"
            diff_path = paths["proofreading"] / f"{Path(text_name).stem}.proofread.diff.txt"
            self.assertEqual(
                {path.name for path in paths["text_and_metadata"].iterdir()},
                {text_name, metadata_name},
            )
            self.assertEqual({path.name for path in paths["unmodified_source_text"].iterdir()}, {source_name})
            self.assertTrue(diff_path.is_file())
            self.assertTrue(details_path.is_file())
            self.assertFalse((paths["proofreading"] / f"{Path(text_name).stem}.proofread.txt").exists())
            self.assertEqual(text_path.read_text(encoding="utf-8"), "यह सही वाक्य है।\n")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["content_identity"], build_content_identity("CAT001", "SUB123", "hi-IN", "यह सही वाक्य है।"))
            self.assertEqual(metadata["content_stats"]["character_count"], len("यह सही वाक्य है।"))
            self.assertEqual(metadata["content"]["automated_tags"], ["summary_chapter", "उपसंहार"])
            self.assertEqual(metadata["integrity"]["artifacts"]["text"]["value"], hashlib.sha256(text_path.read_bytes()).hexdigest())
            details = json.loads(details_path.read_text(encoding="utf-8"))
            details_text = details_path.read_text(encoding="utf-8")
            self.assertEqual(details["unmodified_source"]["text_sha256"], hashlib.sha256(source_text.encode("utf-8")).hexdigest())
            self.assertEqual(details["canonical_corrected"]["text_sha256"], hashlib.sha256(text_path.read_bytes()).hexdigest())
            self.assertEqual(details["unmodified_source"]["text_artifact"]["path"], f"chapters/unmodified_source_text/{source_name}")
            self.assertEqual(details["canonical_corrected"]["text_artifact"], metadata["storage"]["artifacts"]["text"])
            self.assertEqual(details["proofreading_locale"]["language"], "hi-IN")
            self.assertEqual(details["proofreading_locale"]["instruction_template"]["id"], "hi-IN-proofreading")
            self.assertRegex(details["proofreading_locale"]["instruction_template"]["sha256"], "^[a-f0-9]{64}$")
            self.assertNotIn(source_text, details_text)
            self.assertNotIn("यह सही वाक्य है।", details_text)
            content_manifest_path = write_chapter_content_manifest(config, paths)
            content_manifest = json.loads(content_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(content_manifest["chapters"][0]["text_artifact"], metadata["storage"]["artifacts"]["text"])
            self.assertNotIn("unmodified_source_text", json.dumps(content_manifest))
            proof_manifest = json.loads((paths["proofreading"] / "proofreading_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(proof_manifest["proofreading_locale"]["language"], "hi-IN")

    def test_proofreading_normalizes_canonical_text_to_lf_only_bytes(self):
        class MixedLineEndingProofreader:
            def proofread(self, text, progress=None):
                return {
                    "corrected_text": "पहला\r\nदूसरा\rतीसरा\r\n",
                    "edits": [],
                    "estimated_input_tokens": 20,
                    "attempts": 1,
                    "throttle_seconds": 0,
                    "usage": {"input_tokens": 10},
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = {
                "pipeline": "unicode-docx-ingest",
                "source": {"backend": "local", "root_dir": temp_dir, "relative_path": "source.docx", "font_encoding": "unicode", "file_format": "docx"},
                "destination": {"backend": "local", "root_dir": temp_dir, "subject_dir": "subject/hi-IN"},
                "naming": {"category_code": "CAT001", "subject_code": "SUB123", "title_slug": "spand-rahasya", "version": "01", "subversion": "01"},
                "metadata_defaults": {"language": "hi-IN", "source_script": "Devanagari", "output_text_encoding": "UTF-8"},
                "_proofreading_config": self.settings(),
            }
            paths = destination_paths_for_subject(root / "subject")
            ensure_job_dirs(paths)
            source_path = paths["unmodified_source_text"] / chapter_unmodified_source_filename(config, 1)
            source_path.write_bytes("पहला स्रोत।\n".encode("utf-8"))

            proofread_chapter_artifacts(config, paths, proofreader=MixedLineEndingProofreader())

            text_path = paths["text_and_metadata"] / chapter_output_filename(config, 1, ".txt")
            text_bytes = text_path.read_bytes()
            expected_bytes = "पहला\nदूसरा\nतीसरा\n".encode("utf-8")
            self.assertEqual(text_bytes, expected_bytes)
            self.assertNotIn(b"\r", text_bytes)
            self.assertTrue(text_bytes.endswith(b"\n"))
            self.assertFalse(text_bytes.endswith(b"\n\n"))

            metadata_path = text_path.with_suffix(".json")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            expected_text = expected_bytes.decode("utf-8").removesuffix("\n")
            self.assertEqual(metadata["integrity"]["artifacts"]["text"]["value"], hashlib.sha256(text_bytes).hexdigest())
            self.assertEqual(metadata["content_identity"], build_content_identity("CAT001", "SUB123", "hi-IN", expected_text))
            details_path = paths["proofreading"] / f"{text_path.stem}.proofread.json"
            details = json.loads(details_path.read_text(encoding="utf-8"))
            self.assertEqual(details["canonical_corrected"]["text_sha256"], hashlib.sha256(text_bytes).hexdigest())

            manifest = json.loads(write_chapter_content_manifest(config, paths).read_text(encoding="utf-8"))
            self.assertEqual(manifest["chapters"][0]["content_key"], metadata["content_identity"]["content_key"])

    def test_proofreading_failure_does_not_write_canonical_artifacts_or_a_manifest(self):
        class FailingProofreader:
            def proofread(self, text, progress=None):
                raise ProofreadingError("missing_credentials", "Set GEMINI_API_KEY before enabling proofreading.")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = {
                "pipeline": "unicode-docx-ingest",
                "source": {"backend": "local", "root_dir": temp_dir, "relative_path": "source.docx", "font_encoding": "unicode", "file_format": "docx"},
                "destination": {"backend": "local", "root_dir": temp_dir, "subject_dir": "subject/hi-IN"},
                "metadata_defaults": {"language": "hi-IN", "source_script": "Devanagari", "output_text_encoding": "UTF-8"},
                "naming": {"category_code": "CAT001", "subject_code": "SUB123", "title_slug": "spand-rahasya", "version": "01", "subversion": "01"},
                "_proofreading_config": self.settings(),
            }
            paths = destination_paths_for_subject(root / "subject")
            ensure_job_dirs(paths)
            (paths["unmodified_source_text"] / chapter_unmodified_source_filename(config, 1)).write_text("यह गलत है।\n", encoding="utf-8")

            with self.assertRaisesRegex(ProofreadingError, "GEMINI_API_KEY"):
                proofread_chapter_artifacts(config, paths, proofreader=FailingProofreader())

            self.assertEqual(list(paths["text_and_metadata"].iterdir()), [])
            self.assertFalse((paths["proofreading"] / "proofreading_manifest.json").exists())

    def test_proofreading_directory_is_prep_owned_not_chunk_owned(self):
        self.assertIn(Path("chapters") / "proofreading", owned_relative_paths("prep-subject"))
        self.assertIn(Path("chapters") / "unmodified_source_text", owned_relative_paths("prep-subject"))
        self.assertNotIn(Path("chapters") / "proofreading", owned_relative_paths("generate-chunks"))

    def test_generate_docx_owns_only_msword_and_its_audit_history(self):
        self.assertEqual(
            owned_relative_paths("generate-docx"),
            (Path("chapters") / "msword", Path("run_reports") / "generate-docx"),
        )


if __name__ == "__main__":
    unittest.main()
