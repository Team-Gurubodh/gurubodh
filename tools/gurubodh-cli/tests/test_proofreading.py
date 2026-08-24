import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from gurubodh.config import proofreading_config, validate_pipeline_matches_source
from gurubodh.content_identity import build_content_identity
from gurubodh.paths import destination_paths_for_subject, ensure_job_dirs
from gurubodh.proofreading import (
    EDIT_LIST_SCHEMA,
    GeminiProofreader,
    ProofreadingError,
    ProofreadingSettings,
    proofread_chapter_artifacts,
    word_level_diff,
)
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
    def __init__(self, status_code, status=None, message=None):
        self.status_code = status_code
        self.status = status
        self.message = message


class FakeChapterProofreader:
    def proofread(self, text):
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
        values = {"enabled": True, "min_request_interval_seconds": 0, "max_requests_per_minute": 10}
        values.update(overrides)
        return ProofreadingSettings(**values)

    def test_word_level_diff_preserves_newlines_and_marks_replacement(self):
        rendered, summary = word_level_diff("पहला गलत शब्द।\n\nदूसरा वाक्य।", "पहला सही शब्द।\n\nदूसरा वाक्य।")

        self.assertIn("[-गलत-]{+सही+}", rendered)
        self.assertIn("\n\nदूसरा", rendered)
        self.assertEqual(summary["changed_segments"], 1)

    def test_proofreading_configuration_defaults_and_rejects_unknown_options(self):
        self.assertEqual(proofreading_config({}).model, "gemini-3.7-flash")
        with self.assertRaisesRegex(SystemExit, "unsupported proofreading option"):
            proofreading_config({"proofreading": {"api_key": "not-allowed"}})
        with self.assertRaisesRegex(SystemExit, "unsupported proofreading option"):
            proofreading_config({"proofreading": {"temperature": 0}})

    def test_proofreading_validation_does_not_bypass_pipeline_source_validation(self):
        with self.assertRaisesRegex(SystemExit, "requires source.font_encoding=unicode"):
            validate_pipeline_matches_source({"pipeline": "unicode-docx-ingest", "source": {"font_encoding": "aps"}})

    def test_one_structured_response_produces_corrected_text_and_edit_list(self):
        client = FakeClient([{
            "corrected_text": "यह सही वाक्य है।",
            "edits": [{"original": "गलत", "corrected": "सही", "category": "spelling", "reason": "वर्तनी"}],
        }])
        proofreader = GeminiProofreader(self.settings(), client=client, types_module=FakeTypes)

        result = proofreader.proofread("यह गलत वाक्य है।")

        self.assertEqual(result["corrected_text"], "यह सही वाक्य है।")
        self.assertEqual(len(result["edits"]), 1)
        self.assertEqual(len(client.models.calls), 1)
        self.assertEqual(client.models.calls[0]["model"], "gemini-3.7-flash")
        self.assertNotIn("temperature", client.models.calls[0]["config"].kwargs)

    def test_gemini_schema_omits_unsupported_additional_properties(self):
        self.assertNotIn("additionalProperties", EDIT_LIST_SCHEMA)
        self.assertNotIn("additionalProperties", EDIT_LIST_SCHEMA["properties"]["edits"]["items"])

    def test_api_error_includes_safe_gemini_status(self):
        client = FakeClient([HttpError(400, "INVALID_ARGUMENT", "Unsupported request setting")])
        proofreader = GeminiProofreader(self.settings(), client=client, types_module=FakeTypes)

        with self.assertRaisesRegex(ProofreadingError, r"HTTP 400 INVALID_ARGUMENT: Unsupported request setting"):
            proofreader.proofread("यह गलत है।")

    def test_rate_limit_is_retried_with_backoff(self):
        client = FakeClient([
            HttpError(429),
            {"corrected_text": "यह सही है।", "edits": [{"original": "गलत", "corrected": "सही", "category": "spelling", "reason": "वर्तनी"}]},
        ])
        delays = []
        proofreader = GeminiProofreader(
            self.settings(initial_retry_delay_seconds=1, max_retry_delay_seconds=1),
            client=client,
            types_module=FakeTypes,
            sleep=delays.append,
            random_value=lambda: 0,
        )

        result = proofreader.proofread("यह गलत है।")

        self.assertEqual(result["attempts"], 2)
        self.assertEqual(delays, [1.0])

    def test_sidecars_do_not_change_canonical_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = {
                "destination": {"backend": "local", "root_dir": temp_dir, "subject_dir": "subject"},
                "_proofreading_config": self.settings(),
            }
            paths = destination_paths_for_subject(root / "subject")
            ensure_job_dirs(paths)
            source_text = "यह गलत वाक्य है।\n"
            text_path = paths["text_and_metadata"] / "chapter.txt"
            text_path.write_text(source_text, encoding="utf-8")
            identity = build_content_identity("CAT001", "SUB123", "hi-Deva", source_text)
            metadata = {
                "document": {"chapter_number": "001"},
                "files": {"text_filename": "chapter.txt"},
                "content_identity": identity,
                "storage": {"artifacts": {"text": {"backend": "local", "path": "chapters/text_and_metadata/chapter.txt", "url": None}}},
            }
            metadata_path = paths["text_and_metadata"] / "chapter.json"
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
            canonical_before = {path: path.read_bytes() for path in (text_path, metadata_path)}
            manifest_path = paths["subject"] / "chapters" / "chapter_content_manifest.json"
            manifest_path.write_text("{\"canonical\": true}\n", encoding="utf-8")
            manifest_before = manifest_path.read_bytes()

            result = proofread_chapter_artifacts(config, paths, proofreader=FakeChapterProofreader())

            self.assertEqual(result["counts"], {"succeeded": 1, "failed": 0, "skipped": 0})
            self.assertEqual(text_path.read_bytes(), canonical_before[text_path])
            self.assertEqual(metadata_path.read_bytes(), canonical_before[metadata_path])
            self.assertEqual(manifest_path.read_bytes(), manifest_before)
            sidecar = paths["proofreading"] / "chapter.proofread.json"
            self.assertTrue(sidecar.is_file())
            self.assertEqual(json.loads(sidecar.read_text(encoding="utf-8"))["source"]["text_sha256"], hashlib.sha256(source_text.encode("utf-8")).hexdigest())

    def test_proofreading_directory_is_prep_owned_not_chunk_owned(self):
        self.assertIn(Path("chapters") / "proofreading", owned_relative_paths("prep-subject"))
        self.assertNotIn(Path("chapters") / "proofreading", owned_relative_paths("generate-chunks"))


if __name__ == "__main__":
    unittest.main()
