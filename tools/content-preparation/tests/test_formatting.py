import copy
import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from gurubodh_utils.constants import DEFAULT_FORMATTING_CONFIG
from gurubodh_utils.formatting import (
    HINDI_FORMATTING_SYSTEM_PROMPT,
    MissingSarvamApiKeyError,
    SARVAM_CHAT_COMPLETIONS_PATH,
    SARVAM_FORMATTING_RESPONSE_SCHEMA,
    SarvamChatCompletionHttpClient,
    SarvamFormatter,
    SarvamPermanentError,
    SarvamResponseError,
    SarvamRetryableError,
    parse_sarvam_formatting_response,
    source_text_sha256,
)


def formatting_config(**overrides):
    config = copy.deepcopy(DEFAULT_FORMATTING_CONFIG)
    config.update(
        {
            "enabled": True,
            "delay_seconds": 0,
            "max_retries": 0,
        }
    )
    config.update(overrides)
    return config


def sarvam_chat_response(content, finish_reason="stop"):
    return {
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {
                    "content": content,
                },
            }
        ]
    }


class FakeSarvamHttpClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create_chat_completion(self, body):
        self.calls.append(body)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeHTTPResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body.encode("utf-8")


class FakeURLOpener:
    def __init__(self, response_body):
        self.response_body = response_body
        self.calls = []

    def __call__(self, request):
        self.calls.append(request)
        return FakeHTTPResponse(self.response_body)


class FormattingTests(unittest.TestCase):
    def test_formatter_import_does_not_require_sarvam_sdk(self):
        formatter = SarvamFormatter(formatting_config(), client=FakeSarvamHttpClient([
            sarvam_chat_response('{"paragraphs": ["पहला पैराग्राफ।"]}')
        ]))

        result = formatter.format_text("पहला पैराग्राफ")

        self.assertEqual(result["provider"], "sarvam")
        self.assertEqual(result["model"], "sarvam-30b")
        self.assertIsNone(result["fallback_model_used"])
        self.assertEqual(result["status"], "formatted")
        self.assertEqual(result["paragraphs"], ["पहला पैराग्राफ।"])
        self.assertEqual(result["source_text_sha256"], source_text_sha256("पहला पैराग्राफ"))

    def test_missing_sarvam_api_key_has_clear_error(self):
        formatter = SarvamFormatter(formatting_config(), environ={})

        with self.assertRaises(MissingSarvamApiKeyError) as exc:
            formatter.format_text("प्रबोधन")

        self.assertIn("SARVAM_API_KEY", str(exc.exception))

    def test_sarvam_chat_request_uses_prompt_and_response_schema(self):
        client = FakeSarvamHttpClient([sarvam_chat_response('{"paragraphs": ["ॐ।"]}')])
        formatter = SarvamFormatter(formatting_config(), client=client)

        formatter.format_text("ॐ")

        call = client.calls[0]
        self.assertEqual(call["model"], "sarvam-30b")
        self.assertEqual(call["response_format"], SARVAM_FORMATTING_RESPONSE_SCHEMA)
        self.assertEqual(call["response_format"]["type"], "json_schema")
        self.assertTrue(call["response_format"]["json_schema"]["strict"])
        self.assertEqual(
            call["response_format"]["json_schema"]["schema"]["properties"]["paragraphs"][
                "minItems"
            ],
            1,
        )
        self.assertIsNone(call["reasoning_effort"])
        self.assertEqual(call["max_tokens"], 4096)
        self.assertEqual(call["messages"][0]["role"], "system")
        self.assertEqual(call["messages"][0]["content"], HINDI_FORMATTING_SYSTEM_PROMPT)
        self.assertEqual(call["messages"][1], {"role": "user", "content": "ॐ"})

    def test_hindi_prompt_keeps_output_contract_out_of_prompt_text(self):
        forbidden_terms = [
            "JSON",
            "json",
            "Markdown",
            "बैकटिक्स",
            "वैध JSON",
            "```",
        ]

        for term in forbidden_terms:
            self.assertNotIn(term, HINDI_FORMATTING_SYSTEM_PROMPT)

    def test_hindi_prompt_keeps_editorial_safeguards(self):
        expected_terms = [
            "expert Hindi editor",
            "clean, readable",
            "shared theme, idea, or logical flow",
            "Do not start a new paragraph for every sentence",
            "3 to 6 sentences",
            "Do not translate",
            "Do not summarize or omit",
            "Fix missing punctuation",
            "पूर्ण विराम",
        ]

        for term in expected_terms:
            self.assertIn(term, HINDI_FORMATTING_SYSTEM_PROMPT)

    def test_sarvam_chat_request_uses_configured_completion_controls(self):
        client = FakeSarvamHttpClient([sarvam_chat_response('{"paragraphs": ["ॐ।"]}')])
        formatter = SarvamFormatter(
            formatting_config(reasoning_effort="low", max_tokens=2048),
            client=client,
        )

        formatter.format_text("ॐ")

        call = client.calls[0]
        self.assertEqual(call["reasoning_effort"], "low")
        self.assertEqual(call["max_tokens"], 2048)

    def test_sarvam_chat_request_rejects_non_http_client_shape(self):
        formatter = SarvamFormatter(formatting_config(), client=object())

        with self.assertRaises(SarvamPermanentError) as exc:
            formatter.format_text("ॐ")

        self.assertIn("Unsupported Sarvam HTTP client shape", str(exc.exception))

    def test_direct_http_client_sends_expected_request(self):
        response = {"choices": [{"message": {"content": '{"paragraphs": ["ॐ।"]}'}}]}
        opener = FakeURLOpener(json.dumps(response))
        client = SarvamChatCompletionHttpClient(api_key="test-key", opener=opener)
        body = {
            "model": "sarvam-30b",
            "messages": [{"role": "user", "content": "ॐ"}],
            "reasoning_effort": None,
            "max_tokens": 4096,
            "response_format": SARVAM_FORMATTING_RESPONSE_SCHEMA,
        }

        result = client.create_chat_completion(body)

        request = opener.calls[0]
        self.assertEqual(request.full_url, f"https://api.sarvam.ai{SARVAM_CHAT_COMPLETIONS_PATH}")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers["Api-subscription-key"], "test-key")
        self.assertEqual(request.headers["Content-type"], "application/json")
        self.assertEqual(json.loads(request.data.decode("utf-8")), body)
        self.assertEqual(result, response)

    def test_parser_accepts_openai_style_choice_response(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": '{"paragraphs": ["एक।", "दो।"]}',
                    }
                }
            ]
        }

        self.assertEqual(parse_sarvam_formatting_response(response), ["एक।", "दो।"])

    def test_parser_rejects_json_with_markdown_fence_markers(self):
        response = sarvam_chat_response('```json\n{"paragraphs": ["एक।"]}\n```')

        with self.assertRaises(SarvamResponseError) as exc:
            parse_sarvam_formatting_response(response)

        self.assertIn("valid JSON", str(exc.exception))

    def test_parser_rejects_invalid_json(self):
        with self.assertRaises(SarvamResponseError) as exc:
            parse_sarvam_formatting_response(sarvam_chat_response("not-json"))

        self.assertIn("valid JSON", str(exc.exception))

    def test_parser_explains_length_finish_with_no_content(self):
        response = sarvam_chat_response("", finish_reason="length")

        with self.assertRaises(SarvamResponseError) as exc:
            parse_sarvam_formatting_response(response)

        message = str(exc.exception)
        self.assertIn("finish_reason='length'", message)
        self.assertIn("output-token limit", message)

    def test_parser_explains_length_finish_with_partial_content(self):
        response = sarvam_chat_response('{"paragraphs": ["अधूरा।"', finish_reason="length")

        with self.assertRaises(SarvamResponseError) as exc:
            parse_sarvam_formatting_response(response)

        message = str(exc.exception)
        self.assertIn("finish_reason='length'", message)
        self.assertIn("Partial JSON text", message)

    def test_parser_allows_schema_level_extra_fields_to_be_enforced_by_sarvam(self):
        response = sarvam_chat_response('{"paragraphs": ["एक।"], "title": "नया"}')

        self.assertEqual(parse_sarvam_formatting_response(response), ["एक।"])

    def test_parser_rejects_invalid_paragraph_shape(self):
        with self.assertRaises(SarvamResponseError) as exc:
            parse_sarvam_formatting_response(sarvam_chat_response('{"paragraphs": ["एक।", ""]}'))

        self.assertIn("paragraph 2", str(exc.exception))

    def test_retryable_failure_retries_after_configured_delay(self):
        sleeps = []
        client = FakeSarvamHttpClient([
            SarvamRetryableError("rate limited"),
            sarvam_chat_response('{"paragraphs": ["दूसरा प्रयास।"]}'),
        ])
        formatter = SarvamFormatter(
            formatting_config(delay_seconds=1.5, max_retries=1),
            client=client,
            sleeper=sleeps.append,
        )

        result = formatter.format_text("दूसरा प्रयास")

        self.assertEqual(result["paragraphs"], ["दूसरा प्रयास।"])
        self.assertEqual(sleeps, [1.5])
        self.assertEqual(len(client.calls), 2)

    def test_successive_formatting_calls_wait_after_first_request(self):
        sleeps = []
        client = FakeSarvamHttpClient([
            sarvam_chat_response('{"paragraphs": ["पहला।"]}'),
            sarvam_chat_response('{"paragraphs": ["दूसरा।"]}'),
        ])
        formatter = SarvamFormatter(
            formatting_config(delay_seconds=4, max_retries=0),
            client=client,
            sleeper=sleeps.append,
        )

        first = formatter.format_text("पहला")
        second = formatter.format_text("दूसरा")

        self.assertEqual(first["paragraphs"], ["पहला।"])
        self.assertEqual(second["paragraphs"], ["दूसरा।"])
        self.assertEqual(sleeps, [4])
        self.assertEqual(len(client.calls), 2)

    def test_retry_progress_reports_attempts_and_sleep(self):
        sleeps = []
        output = StringIO()
        client = FakeSarvamHttpClient([
            SarvamRetryableError("rate limited"),
            sarvam_chat_response('{"paragraphs": ["दूसरा प्रयास।"]}'),
        ])
        formatter = SarvamFormatter(
            formatting_config(delay_seconds=5, max_retries=1),
            client=client,
            sleeper=sleeps.append,
        )

        with redirect_stdout(output):
            formatter.format_text("दूसरा प्रयास", progress_label="[2/3]")

        progress = output.getvalue()
        self.assertIn("[2/3] Sarvam attempt 1/2", progress)
        self.assertIn("[2/3] retrying after retryable Sarvam error; sleeping 5s", progress)
        self.assertIn("[2/3] Sarvam attempt 2/2", progress)
        self.assertEqual(sleeps, [5])

    def test_non_retryable_failure_does_not_sleep_or_retry(self):
        sleeps = []
        client = FakeSarvamHttpClient([SarvamPermanentError("bad credentials")])
        formatter = SarvamFormatter(
            formatting_config(delay_seconds=1, max_retries=3),
            client=client,
            sleeper=sleeps.append,
        )

        with self.assertRaises(SarvamPermanentError):
            formatter.format_text("प्रबोधन")

        self.assertEqual(sleeps, [])
        self.assertEqual(len(client.calls), 1)

    def test_retryable_failure_raises_after_retries_exhausted(self):
        sleeps = []
        client = FakeSarvamHttpClient([
            SarvamRetryableError("rate limited"),
            SarvamRetryableError("still rate limited"),
        ])
        formatter = SarvamFormatter(
            formatting_config(delay_seconds=2, max_retries=1),
            client=client,
            sleeper=sleeps.append,
        )

        with self.assertRaises(SarvamRetryableError):
            formatter.format_text("प्रबोधन")

        self.assertEqual(sleeps, [2])
        self.assertEqual(len(client.calls), 2)

    def test_retryable_failure_is_hard_capped_at_one_retry(self):
        sleeps = []
        client = FakeSarvamHttpClient([
            SarvamRetryableError("rate limited"),
            SarvamRetryableError("still rate limited"),
            sarvam_chat_response('{"paragraphs": ["तीसरा प्रयास।"]}'),
        ])
        formatter = SarvamFormatter(
            formatting_config(delay_seconds=2, max_retries=5),
            client=client,
            sleeper=sleeps.append,
        )

        with self.assertRaises(SarvamRetryableError):
            formatter.format_text("प्रबोधन")

        self.assertEqual(sleeps, [2])
        self.assertEqual(len(client.calls), 2)


if __name__ == "__main__":
    unittest.main()
