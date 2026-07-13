import copy
import unittest

from gurubodh_utils.constants import DEFAULT_FORMATTING_CONFIG
from gurubodh_utils.formatting import (
    HINDI_FORMATTING_SYSTEM_PROMPT,
    MissingSarvamApiKeyError,
    SARVAM_FORMATTING_RESPONSE_SCHEMA,
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


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeChat:
    def __init__(self, responses):
        self.completions = FakeCompletions(responses)


class FakeSarvamClient:
    def __init__(self, responses):
        self.chat = FakeChat(responses)


class FormattingTests(unittest.TestCase):
    def test_formatter_import_does_not_require_sarvam_sdk(self):
        formatter = SarvamFormatter(formatting_config(), client=FakeSarvamClient([
            '{"paragraphs": ["पहला पैराग्राफ।"]}'
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
        client = FakeSarvamClient(['{"paragraphs": ["ॐ।"]}'])
        formatter = SarvamFormatter(formatting_config(), client=client)

        formatter.format_text("ॐ")

        call = client.chat.completions.calls[0]
        self.assertEqual(call["model"], "sarvam-30b")
        self.assertEqual(call["response_format"], SARVAM_FORMATTING_RESPONSE_SCHEMA)
        self.assertEqual(call["messages"][0]["role"], "system")
        self.assertEqual(call["messages"][0]["content"], HINDI_FORMATTING_SYSTEM_PROMPT)
        self.assertEqual(call["messages"][1], {"role": "user", "content": "ॐ"})

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

    def test_parser_rejects_invalid_json(self):
        with self.assertRaises(SarvamResponseError) as exc:
            parse_sarvam_formatting_response("not-json")

        self.assertIn("valid JSON", str(exc.exception))

    def test_parser_rejects_unknown_fields(self):
        with self.assertRaises(SarvamResponseError) as exc:
            parse_sarvam_formatting_response('{"paragraphs": ["एक।"], "title": "नया"}')

        self.assertIn("unsupported fields", str(exc.exception))

    def test_parser_rejects_invalid_paragraph_shape(self):
        with self.assertRaises(SarvamResponseError) as exc:
            parse_sarvam_formatting_response('{"paragraphs": ["एक।", ""]}')

        self.assertIn("paragraph 2", str(exc.exception))

    def test_retryable_failure_retries_after_configured_delay(self):
        sleeps = []
        client = FakeSarvamClient([
            SarvamRetryableError("rate limited"),
            '{"paragraphs": ["दूसरा प्रयास।"]}',
        ])
        formatter = SarvamFormatter(
            formatting_config(delay_seconds=1.5, max_retries=1),
            client=client,
            sleeper=sleeps.append,
        )

        result = formatter.format_text("दूसरा प्रयास")

        self.assertEqual(result["paragraphs"], ["दूसरा प्रयास।"])
        self.assertEqual(sleeps, [1.5])
        self.assertEqual(len(client.chat.completions.calls), 2)

    def test_non_retryable_failure_does_not_sleep_or_retry(self):
        sleeps = []
        client = FakeSarvamClient([SarvamPermanentError("bad credentials")])
        formatter = SarvamFormatter(
            formatting_config(delay_seconds=1, max_retries=3),
            client=client,
            sleeper=sleeps.append,
        )

        with self.assertRaises(SarvamPermanentError):
            formatter.format_text("प्रबोधन")

        self.assertEqual(sleeps, [])
        self.assertEqual(len(client.chat.completions.calls), 1)

    def test_retryable_failure_raises_after_retries_exhausted(self):
        sleeps = []
        client = FakeSarvamClient([
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
        self.assertEqual(len(client.chat.completions.calls), 2)


if __name__ == "__main__":
    unittest.main()
