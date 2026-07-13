import hashlib
import inspect
import json
import os
import time


SARVAM_API_KEY_ENV_VAR = "SARVAM_API_KEY"
SARVAM_API_BASE_URL = "https://api.sarvam.ai"
FORMATTED_ARTIFACT_SCHEMA_VERSION = "1.0.0"

HINDI_FORMATTING_SYSTEM_PROMPT = """आप एक विशेषज्ञ हिंदी संपादक हैं। आपका कार्य दिए गए कच्चे हिंदी देवनागरी पाठ को केवल पढ़ने योग्य बनाना है।

मुख्य नियम:
1. मूल पाठ का अर्थ, भाषा, क्रम और शब्दावली सुरक्षित रखें।
2. अनुवाद न करें।
3. संक्षेप न करें।
4. नया विचार, व्याख्या, शीर्षक, टिप्पणी या निष्कर्ष न जोड़ें।
5. किसी भी वाक्य, पंक्ति, नाम, मंत्र, श्लोक, उद्धरण या धार्मिक/दार्शनिक शब्द को हटाएँ नहीं।
6. जहाँ आवश्यक हो वहाँ केवल विराम चिन्ह जोड़ें: पूर्ण विराम (।), अल्पविराम (,), प्रश्नवाचक चिन्ह (?), द्विबिंदु (:), अर्धविराम (;), उद्धरण चिह्न।
7. विषय या भाव में स्वाभाविक बदलाव के आधार पर पाठ को छोटे, पठनीय पैराग्राफों में बाँटें।
8. पैराग्राफ बनाने के लिए पाठ का क्रम न बदलें।
9. वर्तनी या व्याकरण सुधार केवल तभी करें जब वह स्पष्ट टाइपिंग/OCR त्रुटि हो और अर्थ न बदले।
10. संस्कृत, हिंदी, मराठी, पारिभाषिक, धार्मिक और नाम-संबंधी शब्दों को यथावत रखें।
11. यदि पाठ में क्रमांक, प्रबोधन संख्या, अध्याय संकेत, वक्ता संकेत या शीर्षक जैसा भाग हो, तो उसे सुरक्षित रखें।

आपको केवल एक वैध JSON ऑब्जेक्ट लौटाना है। JSON में बिल्कुल ये कुंजियाँ हों:

{
  "paragraphs": [
    "पहला पैराग्राफ",
    "दूसरा पैराग्राफ"
  ]
}

आउटपुट में JSON के अलावा कोई अतिरिक्त टेक्स्ट, Markdown, टिप्पणी या ```json बैकटिक्स न दें।"""

SARVAM_FORMATTING_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "sarvam_hindi_formatting_response",
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


class SarvamDependencyError(FormattingError):
    """Raised when the Sarvam SDK is required but not installed."""


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
    try:
        from sarvamai import SarvamAI
    except ImportError as exc:
        raise SarvamDependencyError(
            "Sarvam formatting requires the optional sarvamai Python package"
        ) from exc
    return SarvamAI(api_subscription_key=api_key)


def parse_sarvam_formatting_response(raw_response):
    text = extract_response_text(raw_response)
    if not isinstance(text, str) or not text.strip():
        raise SarvamResponseError("Sarvam response did not contain JSON text")

    text = normalize_json_response_text(text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SarvamResponseError(f"Sarvam response was not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise SarvamResponseError("Sarvam response JSON must be an object")
    unknown_keys = sorted(set(data) - {"paragraphs"})
    if unknown_keys:
        keys = ", ".join(unknown_keys)
        raise SarvamResponseError(f"Sarvam response contains unsupported fields: {keys}")
    paragraphs = data.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs:
        raise SarvamResponseError("Sarvam response paragraphs must be a non-empty array")
    for index, paragraph in enumerate(paragraphs, start=1):
        if not isinstance(paragraph, str) or not paragraph.strip():
            raise SarvamResponseError(
                f"Sarvam response paragraph {index} must be a non-empty string"
            )
    return [paragraph.strip() for paragraph in paragraphs]


def normalize_json_response_text(text):
    stripped = text.strip()
    if stripped.startswith("```json"):
        stripped = stripped.removeprefix("```json").strip()
    elif stripped.startswith("```"):
        stripped = stripped.removeprefix("```").strip()

    if stripped.endswith("```"):
        stripped = stripped.removesuffix("```").strip()
    return stripped


def extract_response_text(raw_response):
    if isinstance(raw_response, str):
        return raw_response
    if isinstance(raw_response, dict):
        return extract_response_text_from_mapping(raw_response)

    choices = getattr(raw_response, "choices", None)
    if choices:
        return extract_response_text_from_choice(choices[0])
    text = getattr(raw_response, "text", None)
    if text is not None:
        return text
    content = getattr(raw_response, "content", None)
    if content is not None:
        return content
    return None


def extract_response_text_from_mapping(raw_response):
    if "text" in raw_response:
        return raw_response["text"]
    if "content" in raw_response:
        return raw_response["content"]
    choices = raw_response.get("choices")
    if choices:
        return extract_response_text_from_choice(choices[0])
    return None


def extract_response_text_from_choice(choice):
    if isinstance(choice, dict):
        message = choice.get("message")
        if isinstance(message, dict):
            return message.get("content")
        return choice.get("text") or choice.get("content")

    message = getattr(choice, "message", None)
    if message is not None:
        if isinstance(message, dict):
            return message.get("content")
        return getattr(message, "content", None)
    return getattr(choice, "text", None) or getattr(choice, "content", None)


def is_retryable_sarvam_error(exc):
    if isinstance(exc, SarvamRetryableError):
        return True
    if isinstance(exc, (SarvamResponseError, SarvamPermanentError, MissingSarvamApiKeyError)):
        return False

    status_code = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status_code in {408, 409, 425, 429, 500, 502, 503, 504}:
        return True

    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status in {408, 409, 425, 429, 500, 502, 503, 504}


class SarvamFormatter:
    def __init__(self, formatting_config, client=None, sleeper=time.sleep, environ=None):
        self.config = formatting_config
        self.client = client
        self.sleeper = sleeper
        self.environ = environ

    def format_text(self, text):
        model = self.config["model"]
        paragraphs = self._format_with_retries(text, model)
        return {
            "schema_version": FORMATTED_ARTIFACT_SCHEMA_VERSION,
            "provider": "sarvam",
            "model": model,
            "fallback_model_used": None,
            "source_text_sha256": source_text_sha256(text),
            "status": "formatted",
            "paragraphs": paragraphs,
        }

    def _format_with_retries(self, text, model):
        max_retries = self.config["max_retries"]
        attempts = max_retries + 1
        last_error = None

        for attempt in range(1, attempts + 1):
            if attempt > 1:
                self._sleep_before_retry()
            try:
                response = self._call_sarvam(text, model)
                return parse_sarvam_formatting_response(response)
            except Exception as exc:
                if not is_retryable_sarvam_error(exc) or attempt == attempts:
                    raise
                last_error = exc

        raise last_error

    def _sleep_before_retry(self):
        delay_seconds = self.config.get("delay_seconds", 0)
        if delay_seconds:
            self.sleeper(delay_seconds)

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
        return call_sarvam_chat_completion(client, model, messages)


def call_sarvam_chat_completion(client, model, messages):
    chat = getattr(client, "chat", None)
    completions = getattr(chat, "completions", None) if chat is not None else None

    if completions is not None:
        create = getattr(completions, "create", None)
        if callable(create):
            return call_with_optional_response_format(create, model, messages)
        if callable(completions):
            return call_with_optional_response_format(completions, model, messages)

    create_chat_completion = getattr(client, "create_chat_completion", None)
    if callable(create_chat_completion):
        return call_with_optional_response_format(create_chat_completion, model, messages)

    raise SarvamPermanentError("Unsupported Sarvam client shape for chat completion")


def call_with_optional_response_format(callable_obj, model, messages):
    kwargs = {
        "model": model,
        "messages": messages,
    }
    if accepts_keyword(callable_obj, "response_format"):
        kwargs["response_format"] = SARVAM_FORMATTING_RESPONSE_SCHEMA
    return callable_obj(**kwargs)


def accepts_keyword(callable_obj, keyword):
    try:
        parameters = inspect.signature(callable_obj).parameters
    except (TypeError, ValueError):
        return True

    if keyword in parameters:
        return True
    return any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
