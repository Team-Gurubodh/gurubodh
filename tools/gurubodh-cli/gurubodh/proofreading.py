"""Gemini-backed canonical locale-aware chapter proofreading artifacts."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import time
from typing import Any, Callable

from gurubodh.content_identity import build_content_identity
from gurubodh.locales import LocaleSpec, locale_spec
from gurubodh.metadata import build_chapter_metadata
from gurubodh.naming import chapter_output_filename
from gurubodh.storage import destination_artifact_reference
from gurubodh.time_utils import utc_now


GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY"
PROOFREADING_OUTPUT_DIR = "proofreading"
PROOFREADING_MANIFEST_FILENAME = "proofreading_manifest.json"
PROOFREADING_SCHEMA_VERSION = 2

EDIT_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "corrected_text": {"type": "string", "description": "Corrected source text only."},
        "edits": {
            "type": "array",
            "description": "Every spelling, grammar, or punctuation correction.",
            "items": {
                "type": "object",
                "properties": {
                    "original": {"type": "string"},
                    "corrected": {"type": "string"},
                    "category": {"type": "string", "enum": ["spelling", "grammar", "punctuation"]},
                    "reason": {"type": "string"},
                },
                "required": ["original", "corrected", "category", "reason"],
            },
        },
    },
    "required": ["corrected_text", "edits"],
}


class ProofreadingError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        retryable: bool = False,
        retry_after_seconds: float | None = None,
        request_attempts: int = 0,
        successful_request_attempts: int = 0,
    ):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        # These are deliberately request-level counters, not chapter counters.
        # They let resumable callers audit retries and terminal API failures.
        self.request_attempts = request_attempts
        self.successful_request_attempts = successful_request_attempts


@dataclass(frozen=True)
class ProofreadingSettings:
    provider: str = "google-ai-studio"
    model: str = "gemini-3.7-flash"
    max_output_tokens: int = 8192
    max_input_characters: int = 30000
    max_retries: int = 3
    initial_retry_delay_seconds: float = 2.0
    max_retry_delay_seconds: float = 30.0
    min_request_interval_seconds: float = 6.0
    max_requests_per_minute: int = 8
    max_estimated_input_tokens_per_minute: int = 20000

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ProofreadingSettings":
        values = {field: config.get(field, getattr(cls, field)) for field in cls.__dataclass_fields__}
        return cls(**values)

    def public_dict(self) -> dict[str, Any]:
        return {
            "mandatory": True,
            "provider": self.provider,
            "model": self.model,
            "max_output_tokens": self.max_output_tokens,
            "max_input_characters": self.max_input_characters,
            "max_retries": self.max_retries,
            "initial_retry_delay_seconds": self.initial_retry_delay_seconds,
            "max_retry_delay_seconds": self.max_retry_delay_seconds,
            "min_request_interval_seconds": self.min_request_interval_seconds,
            "max_requests_per_minute": self.max_requests_per_minute,
            "max_estimated_input_tokens_per_minute": self.max_estimated_input_tokens_per_minute,
        }


def estimate_input_tokens(text: str) -> int:
    """A deliberately conservative local estimate for quota pacing, not billing."""
    return max(1, math.ceil(len(text) * 1.25)) if text else 0


def _tokens(text: str) -> list[str]:
    return re.findall(r"\s+|\S+", text, flags=re.UNICODE)


def word_level_diff(original: str, corrected: str) -> tuple[str, dict[str, Any]]:
    """Render a whitespace-preserving word diff without another model request."""
    original_tokens, corrected_tokens = _tokens(original), _tokens(corrected)
    matcher = difflib.SequenceMatcher(None, original_tokens, corrected_tokens, autojunk=False)
    rendered: list[str] = []
    changed_segments = 0
    removed_words = added_words = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            rendered.extend(original_tokens[i1:i2])
            continue
        changed_segments += 1
        removed, added = "".join(original_tokens[i1:i2]), "".join(corrected_tokens[j1:j2])
        removed_words += len(re.findall(r"\S+", removed))
        added_words += len(re.findall(r"\S+", added))
        if removed:
            rendered.append(f"[-{removed}-]")
        if added:
            rendered.append(f"{{+{added}+}}")
    return "".join(rendered), {
        "total_words_original": len(re.findall(r"\S+", original)),
        "total_words_corrected": len(re.findall(r"\S+", corrected)),
        "changed_segments": changed_segments,
        "removed_word_count": removed_words,
        "added_word_count": added_words,
        "similarity_ratio": round(matcher.ratio(), 3),
    }


def _validated_response(response_text: str, original_text: str) -> tuple[str, list[dict[str, str]]]:
    try:
        payload = json.loads(response_text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ProofreadingError("malformed_response", f"Gemini did not return valid structured JSON: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != {"corrected_text", "edits"}:
        raise ProofreadingError("malformed_response", "Gemini response must contain only corrected_text and edits.")
    corrected = payload["corrected_text"]
    edits = payload["edits"]
    if not isinstance(corrected, str) or (original_text.strip() and not corrected.strip()):
        raise ProofreadingError("malformed_response", "Gemini returned an empty corrected_text for non-empty source text.")
    if not isinstance(edits, list):
        raise ProofreadingError("malformed_response", "Gemini response edits must be an array.")
    validated: list[dict[str, str]] = []
    source_without_outer_whitespace = original_text.strip()
    corrected_without_outer_whitespace = corrected.strip()
    for index, edit in enumerate(edits, start=1):
        if not isinstance(edit, dict) or set(edit) != {"original", "corrected", "category", "reason"}:
            raise ProofreadingError("malformed_response", f"Gemini edit {index} has an invalid shape.")
        if edit["category"] not in {"spelling", "grammar", "punctuation"}:
            raise ProofreadingError("malformed_response", f"Gemini edit {index} has an invalid category.")
        if not all(isinstance(edit[key], str) and edit[key].strip() for key in ("original", "corrected", "reason")):
            raise ProofreadingError("malformed_response", f"Gemini edit {index} has an empty required value.")
        if (
            edit["original"].strip() == source_without_outer_whitespace
            or edit["corrected"].strip() == corrected_without_outer_whitespace
        ):
            raise ProofreadingError(
                "malformed_response",
                f"Gemini edit {index} would embed a full chapter text in proofreading provenance.",
            )
        validated.append({key: edit[key] for key in ("original", "corrected", "category", "reason")})
    text_changed = original_text.rstrip("\n") != corrected.rstrip("\n")
    if text_changed and not validated:
        raise ProofreadingError("malformed_response", "Gemini changed the text without an explanatory edit list.")
    if not text_changed and validated:
        raise ProofreadingError("malformed_response", "Gemini supplied edits without changing the text.")
    return corrected, validated


def _status_code(exc: Exception) -> int | None:
    for value in (getattr(exc, "status_code", None), getattr(getattr(exc, "response", None), "status_code", None), getattr(exc, "code", None)):
        if isinstance(value, int):
            return value
    return None


def _retry_after_seconds(exc: Exception) -> float | None:
    value = getattr(exc, "retry_after_seconds", None)
    if isinstance(value, (int, float)) and value >= 0:
        return float(value)
    for message in (getattr(exc, "message", None), str(exc)):
        if not isinstance(message, str):
            continue
        match = re.search(
            r"\b(?:retry|try again)\s+(?:in|after)\s+(\d+(?:\.\d+)?)\s*(?:s|sec(?:onds?)?)\b",
            message,
            flags=re.IGNORECASE,
        )
        if match:
            return float(match.group(1))
    return None


def _api_error_detail(exc: Exception, status_code: int | None) -> str:
    """Return bounded API diagnostics without serializing an exception payload."""
    api_status = getattr(exc, "status", None)
    if isinstance(api_status, str) and re.fullmatch(r"[A-Z_]{1,64}", api_status):
        detail = f"HTTP {status_code} {api_status}" if status_code else api_status
    else:
        detail = f"HTTP {status_code}" if status_code else exc.__class__.__name__
    message = getattr(exc, "message", None)
    if isinstance(message, str) and message.strip():
        normalized_message = re.sub(r"\s+", " ", message).strip()
        return f"{detail}: {normalized_message[:500]}"
    return detail


class RequestRateLimiter:
    def __init__(self, settings: ProofreadingSettings, clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        self.settings = settings
        self.clock = clock
        self.sleep = sleep
        self.requests: deque[tuple[float, int]] = deque()
        self.last_request_at: float | None = None

    def acquire(self, estimated_tokens: int, on_wait: Callable[[float], None] | None = None) -> float:
        now = self.clock()
        while self.requests and now - self.requests[0][0] >= 60:
            self.requests.popleft()
        waits = []
        if self.last_request_at is not None:
            waits.append(self.settings.min_request_interval_seconds - (now - self.last_request_at))
        if len(self.requests) >= self.settings.max_requests_per_minute:
            waits.append(60 - (now - self.requests[0][0]))
        used_tokens = sum(tokens for _, tokens in self.requests)
        if self.requests and used_tokens + estimated_tokens > self.settings.max_estimated_input_tokens_per_minute:
            waits.append(60 - (now - self.requests[0][0]))
        wait_seconds = max([0.0, *waits])
        if wait_seconds:
            if on_wait:
                on_wait(wait_seconds)
            self.sleep(wait_seconds)
            now = self.clock()
            while self.requests and now - self.requests[0][0] >= 60:
                self.requests.popleft()
        self.requests.append((now, estimated_tokens))
        self.last_request_at = now
        return wait_seconds


class GeminiProofreader:
    def __init__(
        self,
        settings: ProofreadingSettings,
        locale: LocaleSpec | None = None,
        client: Any | None = None,
        types_module: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
        random_value: Callable[[], float] = random.random,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.settings = settings
        self.locale = locale
        self._client = client
        self._types_module = types_module
        self._sleep = sleep
        self._random_value = random_value
        self._limiter = RequestRateLimiter(settings, clock=clock, sleep=sleep)

    @property
    def client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = os.environ.get(GEMINI_API_KEY_ENV_VAR)
        if not api_key:
            raise ProofreadingError("missing_credentials", f"Set {GEMINI_API_KEY_ENV_VAR} before enabling proofreading.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ProofreadingError("missing_dependency", "Proofreading requires the google-genai package. Reinstall Gurubodh CLI dependencies.") from exc
        self._types_module = types
        self._client = genai.Client(api_key=api_key)
        return self._client

    def _config(self) -> Any:
        if self._types_module is None:
            _ = self.client
        if self.locale is None:
            raise ProofreadingError(
                "missing_locale",
                "Gemini proofreading requires an explicitly selected supported language.",
            )
        return self._types_module.GenerateContentConfig(
            system_instruction=self.locale.proofreading_instruction,
            max_output_tokens=self.settings.max_output_tokens,
            response_mime_type="application/json",
            response_schema=EDIT_LIST_SCHEMA,
        )

    def proofread(self, text: str, progress: Callable[[str], None] | None = None) -> dict[str, Any]:
        estimated_tokens = estimate_input_tokens(text)
        if len(text) > self.settings.max_input_characters:
            raise ProofreadingError(
                "input_too_large",
                f"Chapter has {len(text)} characters; configured proofreading limit is {self.settings.max_input_characters}.",
            )
        if estimated_tokens > self.settings.max_estimated_input_tokens_per_minute:
            raise ProofreadingError(
                "input_too_large",
                "Chapter estimated input tokens exceed the configured per-minute proofreading budget.",
            )
        attempts = 0
        total_throttle_seconds = 0.0

        def announce_local_wait(wait_seconds: float) -> None:
            if progress:
                progress(f"Waiting {wait_seconds:.1f} seconds for local Gemini request pacing.")

        while True:
            attempts += 1
            if progress:
                progress("Checking local Gemini request pacing before sending.")
            total_throttle_seconds += self._limiter.acquire(
                estimated_tokens,
                on_wait=announce_local_wait if progress else None,
            )
            if progress:
                progress(
                    f"Sending Gemini request (attempt {attempts}; estimated input {estimated_tokens} tokens)."
                )
            try:
                response = self.client.models.generate_content(
                    model=self.settings.model,
                    contents=f"<source-text>\n{text}\n</source-text>",
                    config=self._config(),
                )
                try:
                    corrected, edits = _validated_response(response.text, text)
                except ProofreadingError as exc:
                    # The request itself completed even if its response violated
                    # the proofreading contract.
                    exc.request_attempts = attempts
                    exc.successful_request_attempts = 1
                    raise
                if progress:
                    progress("Gemini response received; validating and writing canonical artifacts.")
                return {
                    "corrected_text": corrected,
                    "edits": edits,
                    "estimated_input_tokens": estimated_tokens,
                    "attempts": attempts,
                    "successful_request_attempts": 1,
                    "failed_request_attempts": attempts - 1,
                    "throttle_seconds": round(total_throttle_seconds, 3),
                    "usage": usage_summary(getattr(response, "usage_metadata", None)),
                }
            except ProofreadingError:
                raise
            except Exception as exc:
                status_code = _status_code(exc)
                retryable = status_code in {408, 429, 500, 502, 503, 504} or isinstance(exc, (TimeoutError, ConnectionError))
                if not retryable or attempts > self.settings.max_retries:
                    code = "rate_limited" if status_code == 429 else "api_error"
                    detail = _api_error_detail(exc, status_code)
                    raise ProofreadingError(
                        code,
                        f"Gemini proofreading request failed ({detail}).",
                        retryable=retryable,
                        request_attempts=attempts,
                    ) from exc
                retry_after = _retry_after_seconds(exc)
                delay = retry_after if retry_after is not None else min(
                    self.settings.max_retry_delay_seconds,
                    self.settings.initial_retry_delay_seconds * (2 ** (attempts - 1)),
                )
                delay += delay * 0.25 * self._random_value()
                if progress:
                    source = "Gemini's requested retry delay" if retry_after is not None else "exponential backoff"
                    progress(
                        f"Gemini returned a transient {status_code or 'network'} error; "
                        f"retrying in {delay:.1f} seconds ({source})."
                    )
                self._sleep(delay)
                total_throttle_seconds += delay


def usage_summary(usage: Any) -> dict[str, int] | None:
    if usage is None:
        return None
    values = {}
    for source, target in (("prompt_token_count", "input_tokens"), ("candidates_token_count", "output_tokens"), ("total_token_count", "total_tokens")):
        value = getattr(usage, source, None)
        if isinstance(value, int):
            values[target] = value
    return values or None


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((text if text.endswith("\n") else text + "\n").encode("utf-8"))


def _proofread_artifact_paths(proofreading_dir: Path, text_filename: str) -> dict[str, Path]:
    stem = Path(text_filename).stem
    return {
        "diff": proofreading_dir / f"{stem}.proofread.diff.txt",
        "json": proofreading_dir / f"{stem}.proofread.json",
    }


def _artifact_integrity(path: Path) -> dict[str, Any]:
    return {"algorithm": "sha256", "encoding": "UTF-8", "line_endings": "LF", "scope": "artifact-bytes", "value": hashlib.sha256(path.read_bytes()).hexdigest()}


def _canonical_text_filename(unmodified_source_filename: str) -> str:
    suffix = "_unmodified_source.txt"
    if not unmodified_source_filename.endswith(suffix):
        raise ProofreadingError(
            "invalid_unmodified_source_artifact",
            f"Unmodified source artifact has an unexpected filename: {unmodified_source_filename}",
        )
    return f"{unmodified_source_filename.removesuffix(suffix)}.txt"


def _chapter_file_names(config: dict[str, Any], chapter_number: int) -> dict[str, Any]:
    text_name = chapter_output_filename(config, chapter_number, ".txt")
    metadata_name = chapter_output_filename(config, chapter_number, ".json")
    return {
        "metadata": metadata_name,
        "text": text_name,
        "metadata_relative_path": Path("chapters") / "text_and_metadata" / metadata_name,
        "text_relative_path": Path("chapters") / "text_and_metadata" / text_name,
    }


def _canonical_text_value(corrected_text: str) -> str:
    """Normalize canonical artifact line endings without applying identity normalization."""
    return corrected_text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def _validate_proofreader_locale(proofreader: Any, locale: LocaleSpec) -> None:
    """Reject a caller-supplied Gemini client whose prompt locale disagrees.

    This guard runs before the request. It protects the canonical metadata
    language from being paired with a Gemini instruction selected for another
    locale while preserving lightweight fake proofreaders used by tests.
    """
    if isinstance(proofreader, GeminiProofreader):
        selected = proofreader.locale
        if selected is None or selected.language != locale.language:
            selected_language = selected.language if selected else "none"
            raise ProofreadingError(
                "locale_mismatch",
                f"Selected proofreading language {selected_language!r} does not match chapter metadata language {locale.language!r}.",
            )


def proofread_single_chapter_artifacts(
    config: dict[str, Any],
    paths: dict[str, Path],
    chapter_number: int,
    unmodified_source_path: Path,
    converter_counts: dict[str, int] | None = None,
    entry_point: str = "",
    proofreader: GeminiProofreader | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Proofread one staged chapter and write its complete artifact set.

    The caller owns checkpointing.  This deliberately returns only bounded
    provenance and artifact checksums; neither the source nor corrected text is
    returned for inclusion in a job checkpoint or audit record.
    """
    settings = config["_proofreading_config"]
    source_bytes = unmodified_source_path.read_bytes()
    source_text = source_bytes.decode("utf-8")
    locale = config.get("_locale") or locale_spec(config["metadata_defaults"]["language"])
    source_identity = build_content_identity(
        config["naming"]["category_code"],
        config["naming"]["subject_code"],
        locale.language,
        source_text,
    )
    text_filename = _canonical_text_filename(unmodified_source_path.name)
    file_names = _chapter_file_names(config, chapter_number)
    if text_filename != file_names["text"]:
        raise ProofreadingError(
            "invalid_unmodified_source_artifact",
            f"Unmodified source filename does not match chapter {chapter_number:03d}: {unmodified_source_path.name}",
        )

    proofreader = proofreader or GeminiProofreader(settings, locale=locale)
    _validate_proofreader_locale(proofreader, locale)
    response = proofreader.proofread(source_text, progress=progress)
    canonical_text = _canonical_text_value(response["corrected_text"])
    canonical_text_path = paths["text_and_metadata"] / text_filename
    metadata_path = paths["text_and_metadata"] / file_names["metadata"]
    _write_text(canonical_text_path, canonical_text)
    metadata = build_chapter_metadata(
        config,
        chapter_number,
        file_names,
        canonical_text,
        converter_counts or {},
        utc_now(),
        entry_point,
    )
    _write_text(metadata_path, json.dumps(metadata, ensure_ascii=False, indent=2))

    canonical_artifact_text = canonical_text_path.read_text(encoding="utf-8")
    rendered_diff, diff_summary = word_level_diff(source_text, canonical_artifact_text)
    proof_dir = paths["proofreading"]
    proof_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths = _proofread_artifact_paths(proof_dir, text_filename)
    _write_text(artifact_paths["diff"], "Word-level proof-reading diff. [-removed-] {+added+}\n\n" + rendered_diff)
    relative_dir = Path("chapters") / PROOFREADING_OUTPUT_DIR
    canonical_integrity = _artifact_integrity(canonical_text_path)
    payload = {
        "schema_version": PROOFREADING_SCHEMA_VERSION,
        "status": "succeeded",
        "created_at": utc_now(),
        "provider": {"name": settings.provider, "model": settings.model},
        "proofreading_locale": locale.proofreading_provenance(),
        "unmodified_source": {
            "text_artifact": destination_artifact_reference(
                config,
                Path("chapters") / "unmodified_source_text" / unmodified_source_path.name,
            ),
            "text_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "content_identity": source_identity,
        },
        "canonical_corrected": {
            "text_artifact": metadata["storage"]["artifacts"]["text"],
            "text_sha256": canonical_integrity["value"],
            "content_identity": metadata["content_identity"],
        },
        "diff_artifact": destination_artifact_reference(config, relative_dir / artifact_paths["diff"].name),
        "integrity": {
            "unmodified_source": _artifact_integrity(unmodified_source_path),
            "canonical_corrected": canonical_integrity,
            "diff": _artifact_integrity(artifact_paths["diff"]),
        },
        "local_diff_summary": diff_summary,
        "gemini_edits": response["edits"],
        "request": {key: response[key] for key in ("estimated_input_tokens", "attempts", "throttle_seconds", "usage")},
    }
    _write_text(artifact_paths["json"], json.dumps(payload, ensure_ascii=False, indent=2))
    artifact_files = [
        unmodified_source_path,
        canonical_text_path,
        metadata_path,
        artifact_paths["diff"],
        artifact_paths["json"],
    ]
    chapter = {
        "chapter_number": f"{chapter_number:03d}",
        "status": "succeeded",
        "correction_count": len(response["edits"]),
        # Internal checkpoint bookkeeping. The caller removes this before
        # recording canonical chapter provenance.
        "gemini_request_attempts": response["attempts"],
        "gemini_successful_request_attempts": response.get("successful_request_attempts", response["attempts"]),
        "local_diff_summary": diff_summary,
        "unmodified_source_content_key": source_identity["content_key"],
        "canonical_content_key": metadata["content_identity"]["content_key"],
        "artifacts": {
            "unmodified_source": destination_artifact_reference(
                config,
                Path("chapters") / "unmodified_source_text" / unmodified_source_path.name,
            ),
            "canonical_text": metadata["storage"]["artifacts"]["text"],
            "canonical_metadata": metadata["storage"]["artifacts"]["metadata"],
            **{key: destination_artifact_reference(config, relative_dir / path.name) for key, path in artifact_paths.items()},
        },
        "checkpoint_artifacts": [
            {
                "path": str(path.relative_to(paths["subject"])),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in artifact_files
            if path.is_file()
        ],
    }
    return chapter


def write_proofreading_manifest(
    paths: dict[str, Path],
    settings: ProofreadingSettings,
    chapters: list[dict[str, Any]],
    locale: LocaleSpec,
) -> Path:
    """Write the final canonical proofreading provenance manifest."""
    manifest = {
        "schema_version": PROOFREADING_SCHEMA_VERSION,
        "provider": {"name": settings.provider, "model": settings.model},
        "proofreading_locale": locale.proofreading_provenance(),
        "counts": {"succeeded": len(chapters), "failed": 0, "skipped": 0},
        "chapters": [{key: value for key, value in chapter.items() if key != "checkpoint_artifacts"} for chapter in chapters],
    }
    manifest_path = paths["proofreading"] / PROOFREADING_MANIFEST_FILENAME
    _write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest_path


def proofread_chapter_artifacts(
    config: dict[str, Any],
    paths: dict[str, Path],
    converter_counts: dict[str, int] | None = None,
    entry_point: str = "",
    progress: Callable[..., None] | None = None,
    proofreader: GeminiProofreader | None = None,
) -> dict[str, Any]:
    """Create canonical proofread chapter artifacts from retained source text.

    Any proofreading failure is deliberately raised immediately.  The caller
    builds the candidate manifest and promotes/uploads the staged tree only
    after this function returns successfully.
    """
    settings = config["_proofreading_config"]
    source_paths = sorted(paths["unmodified_source_text"].glob("*_unmodified_source.txt"))
    result = {"enabled": True, "chapters": [], "counts": {"succeeded": 0, "failed": 0, "skipped": 0}}
    locale = config.get("_locale") or locale_spec(config["metadata_defaults"]["language"])
    proofreader = proofreader or GeminiProofreader(settings, locale=locale)
    proof_dir = paths["proofreading"]
    proof_dir.mkdir(parents=True, exist_ok=True)
    if progress:
        print(
            f"[proofread] Preparing {len(source_paths)} chapter(s) for sequential Gemini proofreading "
            f"with {settings.provider}/{settings.model}."
        )

    for chapter_index, unmodified_source_path in enumerate(source_paths, start=1):
        try:
            if progress:
                print(
                    f"[proofread {chapter_index:02d}/{len(source_paths):02d}] "
                    f"Unmodified source is ready ({len(unmodified_source_path.read_text(encoding='utf-8'))} characters); starting Gemini request."
                )
            chapter = proofread_single_chapter_artifacts(
                config,
                paths,
                chapter_index,
                unmodified_source_path,
                converter_counts=converter_counts,
                entry_point=entry_point,
                proofreader=proofreader,
                progress=(
                    lambda message: print(
                        f"[proofread {chapter_index:02d}/{len(source_paths):02d}] {message}"
                    )
                )
                if progress
                else None,
            )
        except ProofreadingError as exc:
            if progress:
                print(f"[proofread] chapter {chapter_index:03d}: failed ({exc.code}: {exc})")
            raise

        # The old all-or-nothing helper is a public compatibility surface. Its
        # caller has no checkpoint state to persist, so keep that internal
        # bookkeeping field out of its returned manifest/result.
        chapter.pop("checkpoint_artifacts", None)
        chapter.pop("gemini_request_attempts", None)
        chapter.pop("gemini_successful_request_attempts", None)
        result["chapters"].append(chapter)
        result["counts"]["succeeded"] += 1
        if progress:
            file_names = _chapter_file_names(config, chapter_index)
            text_filename = file_names["text"]
            artifact_paths = _proofread_artifact_paths(proof_dir, text_filename)
            progress(
                "proofread",
                paths["text_and_metadata"] / text_filename,
                paths["text_and_metadata"] / file_names["metadata"],
                unmodified_source_path,
                artifact_paths["diff"],
                artifact_paths["json"],
            )

    manifest_path = write_proofreading_manifest(paths, settings, result["chapters"], locale)
    result["manifest_path"] = manifest_path
    return result
