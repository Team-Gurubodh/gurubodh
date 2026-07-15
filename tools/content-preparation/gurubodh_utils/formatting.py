import hashlib
import json
import os
import time
import urllib.error
import urllib.request

from gurubodh_utils.progress import DEFAULT_PROGRESS_REPORTER


SARVAM_API_KEY_ENV_VAR = "SARVAM_API_KEY"
SARVAM_API_BASE_URL = "https://api.sarvam.ai"
SARVAM_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
FORMATTED_ARTIFACT_SCHEMA_VERSION = "1.0.0"
MAX_SARVAM_FORMATTER_RETRIES = 1
RETRYABLE_HTTP_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}

HINDI_FORMATTING_SYSTEM_PROMPT = """आप एक विशेषज्ञ हिंदी संपादक हैं। दिए गए कच्चे हिंदी देवनागरी पाठ को केवल पढ़ने योग्य बनाएं।

मुख्य नियम:
1. मूल अर्थ, भाषा, क्रम, शब्दावली, नाम, मंत्र, श्लोक, उद्धरण और धार्मिक/दार्शनिक शब्द सुरक्षित रखें।
2. अनुवाद न करें।
3. संक्षेप न करें।
4. नया विचार, व्याख्या, शीर्षक, टिप्पणी या निष्कर्ष न जोड़ें।
5. जहाँ आवश्यक हो केवल विराम चिन्ह जोड़ें।
6. विषय या भाव के स्वाभाविक बदलाव के आधार पर छोटे, पठनीय पैराग्राफ बनाएं।
7. पाठ का क्रम न बदलें।
8. स्पष्ट टाइपिंग/OCR त्रुटि ही सुधारें, वह भी अर्थ बदले बिना।
9. क्रमांक, प्रबोधन संख्या, अध्याय संकेत, वक्ता संकेत, शीर्षक जैसे भाग और अन्य संरचनात्मक संकेत सुरक्षित रखें।"""

SARVAM_FORMATTING_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "sarvam_hindi_formatting_response",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["paragraphs"],
            "properties": {
                "paragraphs": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "string",
                        "minLength": 1,
                    },
                },
            },
        },
    },
}


class FormattingError(Exception):
    """Base class for formatting failures."""


class MissingSarvamApiKeyError(FormattingError):
    """Raised when formatting is requested without SARVAM_API_KEY."""


class SarvamResponseError(FormattingError):
    """Raised when Sarvam returns invalid formatter output."""


class SarvamPermanentError(FormattingError):
    """Raised for failures that should not be retried."""


class SarvamRetryableError(FormattingError):
    """Raised by tests/adapters for retryable Sarvam failures."""


def source_text_sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sarvam_api_key_from_env(environ=None):
    environ = environ if environ is not None else os.environ
    value = environ.get(SARVAM_API_KEY_ENV_VAR, "").strip()
    if not value:
        raise MissingSarvamApiKeyError(
            f"{SARVAM_API_KEY_ENV_VAR} is required when Sarvam formatting is enabled"
        )
    return value


def build_sarvam_client(api_key=None, environ=None):
    api_key = api_key or sarvam_api_key_from_env(environ)
    return SarvamChatCompletionHttpClient(api_key=api_key)


class SarvamChatCompletionHttpClient:
    def __init__(self, api_key, base_url=SARVAM_API_BASE_URL, opener=None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.opener = opener or urllib.request.urlopen

    def create_chat_completion(self, body):
        url = f"{self.base_url}{SARVAM_CHAT_COMPLETIONS_PATH}"
        request = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "api-subscription-key": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.opener(request) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code in RETRYABLE_HTTP_STATUS_CODES:
                raise SarvamRetryableError(
                    f"Sarvam chat completion failed with HTTP {exc.code}"
                ) from exc
            raise SarvamPermanentError(
                f"Sarvam chat completion failed with HTTP {exc.code}"
            ) from exc
        except urllib.error.URLError as exc:
            raise SarvamRetryableError("Sarvam chat completion request failed") from exc

        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise SarvamResponseError("Sarvam API response was not valid JSON") from exc


def parse_sarvam_formatting_response(raw_response):
    if response_finished_due_to_length(raw_response):
        text = extract_response_text(raw_response)
        partial_note = " Partial JSON text was returned." if isinstance(text, str) and text else ""
        raise SarvamResponseError(
            "Sarvam response stopped with finish_reason='length'. The completion "
            "output-token limit was exhausted; increase formatting.max_tokens if "
            "the model tier supports it, or reduce the request size."
            f"{partial_note}"
        )

    text = extract_response_text(raw_response)
    if not isinstance(text, str) or not text.strip():
        raise SarvamResponseError("Sarvam response did not contain chat message content")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SarvamResponseError(f"Sarvam response was not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise SarvamResponseError("Sarvam response JSON must be an object")
    paragraphs = data.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs:
        raise SarvamResponseError("Sarvam response paragraphs must be a non-empty array")
    for index, paragraph in enumerate(paragraphs, start=1):
        if not isinstance(paragraph, str) or not paragraph.strip():
            raise SarvamResponseError(
                f"Sarvam response paragraph {index} must be a non-empty string"
            )
    return [paragraph.strip() for paragraph in paragraphs]


def extract_response_text(raw_response):
    if isinstance(raw_response, dict):
        return extract_response_text_from_mapping(raw_response)

    choices = getattr(raw_response, "choices", None)
    if choices:
        return extract_response_text_from_choice(choices[0])
    return None


def extract_response_text_from_mapping(raw_response):
    choices = raw_response.get("choices")
    if choices:
        return extract_response_text_from_choice(choices[0])
    return None


def extract_response_text_from_choice(choice):
    if isinstance(choice, dict):
        message = choice.get("message")
        if isinstance(message, dict):
            return message.get("content")
        return None

    message = getattr(choice, "message", None)
    if message is not None:
        if isinstance(message, dict):
            return message.get("content")
        return getattr(message, "content", None)
    return None


def response_finished_due_to_length(raw_response):
    choice = first_response_choice(raw_response)
    if choice is None:
        return False
    return choice_value(choice, "finish_reason") == "length"


def first_response_choice(raw_response):
    if isinstance(raw_response, dict):
        choices = raw_response.get("choices")
    else:
        choices = getattr(raw_response, "choices", None)
    if choices:
        return choices[0]
    return None


def choice_value(choice, key):
    if isinstance(choice, dict):
        return choice.get(key)
    return getattr(choice, key, None)


def is_retryable_sarvam_error(exc):
    if isinstance(exc, SarvamRetryableError):
        return True
    if isinstance(exc, (SarvamResponseError, SarvamPermanentError, MissingSarvamApiKeyError)):
        return False

    status_code = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status_code in RETRYABLE_HTTP_STATUS_CODES:
        return True

    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status in RETRYABLE_HTTP_STATUS_CODES


class SarvamFormatter:
    def __init__(
        self,
        formatting_config,
        client=None,
        sleeper=time.sleep,
        environ=None,
        reporter=DEFAULT_PROGRESS_REPORTER,
    ):
        self.config = formatting_config
        self.client = client
        self.sleeper = sleeper
        self.environ = environ
        self.reporter = reporter
        self._has_made_sarvam_request = False

    def format_text(self, text, progress_label=None):
        model = self.config["model"]
        paragraphs = self._format_with_retries(text, model, progress_label=progress_label)
        return {
            "schema_version": FORMATTED_ARTIFACT_SCHEMA_VERSION,
            "provider": "sarvam",
            "model": model,
            "fallback_model_used": None,
            "source_text_sha256": source_text_sha256(text),
            "status": "formatted",
            "paragraphs": paragraphs,
        }

    def _format_with_retries(self, text, model, progress_label=None):
        max_retries = min(self.config["max_retries"], MAX_SARVAM_FORMATTER_RETRIES)
        attempts = max_retries + 1
        last_error = None

        for attempt in range(1, attempts + 1):
            if attempt > 1:
                self._sleep_before_request(
                    progress_label,
                    "retrying after retryable Sarvam error",
                )
            else:
                self._sleep_before_request(progress_label)
            self._report(progress_label, f"Sarvam attempt {attempt}/{attempts}")
            try:
                response = self._call_sarvam(text, model)
                self._has_made_sarvam_request = True
                return parse_sarvam_formatting_response(response)
            except Exception as exc:
                self._has_made_sarvam_request = True
                if not is_retryable_sarvam_error(exc) or attempt == attempts:
                    raise
                last_error = exc

        raise last_error

    def _sleep_before_request(self, progress_label=None, reason=None):
        if not self._has_made_sarvam_request:
            return

        delay_seconds = self.config.get("delay_seconds", 0)
        if not delay_seconds and not reason:
            return

        message = reason or "waiting before next Sarvam request"
        if delay_seconds:
            self._report(
                progress_label,
                f"{message}; sleeping {delay_seconds:g}s",
            )
        else:
            self._report(progress_label, message)
        if delay_seconds:
            self.sleeper(delay_seconds)

    def _report(self, progress_label, message):
        prefix = f"{progress_label} " if progress_label else ""
        self.reporter.report(f"{prefix}{message}")

    def _call_sarvam(self, text, model):
        client = self.client or build_sarvam_client(environ=self.environ)
        messages = [
            {
                "role": "system",
                "content": HINDI_FORMATTING_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": text,
            },
        ]
        return call_sarvam_chat_completion(
            client,
            model,
            messages,
            reasoning_effort=self.config.get("reasoning_effort"),
            max_tokens=self.config.get("max_tokens"),
        )


def call_sarvam_chat_completion(
    client,
    model,
    messages,
    reasoning_effort=None,
    max_tokens=None,
):
    create_chat_completion = getattr(client, "create_chat_completion", None)
    if callable(create_chat_completion):
        return create_chat_completion(
            {
                "model": model,
                "messages": messages,
                "reasoning_effort": reasoning_effort,
                "max_tokens": max_tokens,
                "response_format": SARVAM_FORMATTING_RESPONSE_SCHEMA,
            }
        )

    raise SarvamPermanentError("Unsupported Sarvam HTTP client shape for chat completion")
