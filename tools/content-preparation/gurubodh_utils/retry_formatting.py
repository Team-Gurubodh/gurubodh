import json
from pathlib import Path, PurePosixPath

from gurubodh_utils.docx.chapter_split import (
    formatted_artifact_names,
    formatted_json_artifact_payload,
    formatted_markdown,
    formatter_stats,
    formatter_stats_delta,
)
from gurubodh_utils.formatting import SarvamFormatter, source_text_sha256
from gurubodh_utils.metadata import artifact_bytes_integrity
from gurubodh_utils.progress import DEFAULT_PROGRESS_REPORTER
from gurubodh_utils.storage import (
    R2StorageClient,
    destination_artifact_reference,
    destination_object_key,
    is_r2,
    join_key,
)


MAX_RETRY_ATTEMPTS = 3
CHAPTER_ARTIFACT_DIR = PurePosixPath("chapters/text_and_metadata")


def chapter_artifact_prefix(config):
    return (
        join_key(
            config["destination"]["prefix"],
            config["destination"]["subject_dir"],
            CHAPTER_ARTIFACT_DIR.as_posix(),
        )
        + "/"
    )


def is_chapter_metadata_key(key):
    name = PurePosixPath(key).name
    return name.endswith(".json") and not name.endswith(".formatted.json")


def decode_text_artifact(data):
    text = data.decode("utf-8")
    if text.endswith("\n"):
        return text[:-1]
    return text


def parse_chapter_filter(chapter=None, chapters=None):
    selected = set()
    if chapter:
        selected.add(normalize_chapter_number(chapter))
    if chapters:
        for value in chapters.split(","):
            value = value.strip()
            if value:
                selected.add(normalize_chapter_number(value))
    return selected


def normalize_chapter_number(value):
    text = str(value).strip()
    if not text.isdigit():
        raise SystemExit(f"Invalid chapter number: {value}")
    return f"{int(text):03d}"


def metadata_retry_attempts(metadata):
    value = metadata.get("formatting", {}).get("retry_attempts", 0)
    return value if isinstance(value, int) and value >= 0 else 0


def chapter_number(metadata):
    value = metadata.get("document", {}).get("chapter_number")
    return value if isinstance(value, str) else None


def text_filename(metadata):
    value = metadata.get("files", {}).get("text_filename")
    return value if isinstance(value, str) and value else None


def text_object_key(config, metadata):
    storage_ref = metadata.get("storage", {}).get("artifacts", {}).get("text", {})
    key = storage_ref.get("key")
    if isinstance(key, str) and key:
        return key
    filename = text_filename(metadata)
    if not filename:
        return None
    return destination_object_key(config, Path(CHAPTER_ARTIFACT_DIR.as_posix()) / filename)


def read_json_object(client, bucket, key):
    return json.loads(client.get_object_bytes(bucket, key).decode("utf-8"))


def json_bytes(data):
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def formatted_artifact_bytes(formatted_result, output_formats):
    artifacts = {}
    if "json" in output_formats:
        artifacts["json"] = json_bytes(formatted_json_artifact_payload(formatted_result))
    if "markdown" in output_formats:
        artifacts["markdown"] = formatted_markdown(formatted_result["paragraphs"]).encode("utf-8")
    return artifacts


def formatted_artifact_keys(config, text_name, output_formats):
    names = formatted_artifact_names(text_name)
    keys = {}
    if "json" in output_formats:
        keys["json"] = destination_object_key(
            config,
            Path(CHAPTER_ARTIFACT_DIR.as_posix()) / names["json"],
        )
    if "markdown" in output_formats:
        keys["markdown"] = destination_object_key(
            config,
            Path(CHAPTER_ARTIFACT_DIR.as_posix()) / names["markdown"],
        )
    return keys


def existing_formatted_artifacts(client, bucket, config, metadata, chapter_text, output_formats):
    filename = text_filename(metadata)
    if not filename:
        return None
    keys = formatted_artifact_keys(config, filename, output_formats)
    if "json" in output_formats and "json" not in keys:
        return None
    if "markdown" in output_formats and "markdown" not in keys:
        return None

    artifacts = {}
    try:
        json_data = client.get_object_bytes(bucket, keys["json"])
    except (FileNotFoundError, KeyError):
        return None
    try:
        payload = json.loads(json_data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    if payload.get("status") != "formatted":
        return None
    if payload.get("source_text_sha256") != source_text_sha256(chapter_text):
        return None
    paragraphs = payload.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs:
        return None
    if any(not isinstance(paragraph, str) or not paragraph.strip() for paragraph in paragraphs):
        return None

    artifacts["json"] = json_data
    if "markdown" in output_formats:
        try:
            artifacts["markdown"] = client.get_object_bytes(bucket, keys["markdown"])
        except (FileNotFoundError, KeyError):
            return None
    return artifacts


def clear_formatted_metadata(metadata):
    files = metadata.setdefault("files", {})
    files.pop("formatted_json_filename", None)
    files.pop("formatted_markdown_filename", None)

    storage_artifacts = metadata.setdefault("storage", {}).setdefault("artifacts", {})
    storage_artifacts.pop("formatted_json", None)
    storage_artifacts.pop("formatted_markdown", None)

    integrity_artifacts = metadata.setdefault("integrity", {}).setdefault("artifacts", {})
    integrity_artifacts.pop("formatted_json", None)
    integrity_artifacts.pop("formatted_markdown", None)


def apply_formatted_metadata(metadata, config, text_name, artifact_data):
    clear_formatted_metadata(metadata)
    names = formatted_artifact_names(text_name)
    files = metadata.setdefault("files", {})
    storage_artifacts = metadata.setdefault("storage", {}).setdefault("artifacts", {})
    integrity_artifacts = metadata.setdefault("integrity", {}).setdefault("artifacts", {})

    if "json" in artifact_data:
        files["formatted_json_filename"] = names["json"]
        relative_path = Path(CHAPTER_ARTIFACT_DIR.as_posix()) / names["json"]
        storage_artifacts["formatted_json"] = destination_artifact_reference(config, relative_path)
        integrity_artifacts["formatted_json"] = artifact_bytes_integrity(artifact_data["json"])

    if "markdown" in artifact_data:
        files["formatted_markdown_filename"] = names["markdown"]
        relative_path = Path(CHAPTER_ARTIFACT_DIR.as_posix()) / names["markdown"]
        storage_artifacts["formatted_markdown"] = destination_artifact_reference(
            config,
            relative_path,
        )
        integrity_artifacts["formatted_markdown"] = artifact_bytes_integrity(
            artifact_data["markdown"],
        )


def update_formatting_metadata(
    metadata,
    config,
    status,
    warning,
    chapter_text,
    retry_attempts,
    attempt_count=0,
    retry_count=0,
    throttle_sleep_seconds=0,
    model_used=None,
    token_usage=None,
):
    formatting_config = config.get("formatting", {})
    formatting = metadata.setdefault("formatting", {})
    formatting.update(
        {
            "enabled": bool(formatting_config.get("enabled")),
            "provider": formatting_config.get("provider"),
            "model": formatting_config.get("model"),
            "fallback_model": formatting_config.get("fallback_model"),
            "model_used": model_used,
            "status": status,
            "warning": warning,
            "attempt_count": attempt_count,
            "retry_count": retry_count,
            "retry_attempts": retry_attempts,
            "throttle_sleep_seconds": throttle_sleep_seconds,
            "source_text_sha256": source_text_sha256(chapter_text),
            "token_usage": {
                "completion_tokens": (token_usage or {}).get("completion_tokens"),
                "prompt_tokens": (token_usage or {}).get("prompt_tokens"),
                "total_tokens": (token_usage or {}).get("total_tokens"),
            },
        }
    )


def candidate_record(key, metadata, selected_chapters):
    number = chapter_number(metadata)
    formatting = metadata.get("formatting", {})
    retry_attempts = metadata_retry_attempts(metadata)
    if selected_chapters and number not in selected_chapters:
        return {"key": key, "metadata": metadata, "status": "skipped", "reason": "not-selected"}
    if not formatting.get("enabled", False):
        return {"key": key, "metadata": metadata, "status": "skipped", "reason": "disabled"}
    if formatting.get("status") != "failed":
        return {"key": key, "metadata": metadata, "status": "skipped", "reason": "not-failed"}
    if retry_attempts >= MAX_RETRY_ATTEMPTS:
        return {
            "key": key,
            "metadata": metadata,
            "status": "retry-exhausted",
            "reason": "retry-attempts-exhausted",
        }
    if not number or not text_filename(metadata):
        return {"key": key, "metadata": metadata, "status": "skipped", "reason": "invalid-metadata"}
    return {"key": key, "metadata": metadata, "status": "selected", "reason": "failed"}


def discover_candidates(config, client, selected_chapters, reporter=DEFAULT_PROGRESS_REPORTER):
    destination = config["destination"]
    bucket = destination["bucket"]
    prefix = chapter_artifact_prefix(config)
    reporter.report(f"listing R2 chapter metadata under r2://{bucket}/{prefix}")
    keys = sorted(client.list_keys(bucket, prefix))
    reporter.report(f"found {len(keys)} object(s) under chapter metadata prefix")
    records = []
    metadata_count = 0
    for key in keys:
        if not is_chapter_metadata_key(key):
            continue
        metadata_count += 1
        try:
            metadata = read_json_object(client, bucket, key)
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            records.append(
                {
                    "key": key,
                    "metadata": {},
                    "status": "skipped",
                    "reason": f"invalid-metadata: {exc}",
                }
            )
            continue
        records.append(candidate_record(key, metadata, selected_chapters))
    reporter.report(f"loaded {metadata_count} chapter metadata file(s)")
    return records


def print_dry_run(records):
    selected = [record for record in records if record["status"] == "selected"]
    retry_exhausted = [record for record in records if record["status"] == "retry-exhausted"]
    skipped = [record for record in records if record["status"] == "skipped"]
    print("retry-formatting dry run:")
    print(
        f"selected={len(selected)} skipped={len(skipped)} "
        f"retry_exhausted={len(retry_exhausted)}"
    )
    if selected:
        print("selected chapters:")
        for record in selected:
            metadata = record["metadata"]
            formatting = metadata.get("formatting", {})
            print(
                f"- {chapter_number(metadata)} formatting.status={formatting.get('status')} "
                f"retry_attempts={metadata_retry_attempts(metadata)}"
            )
    if retry_exhausted:
        print("retry exhausted:")
        for record in retry_exhausted:
            metadata = record["metadata"]
            formatting = metadata.get("formatting", {})
            print(
                f"- {chapter_number(metadata)} formatting.status={formatting.get('status')} "
                f"retry_attempts={metadata_retry_attempts(metadata)}"
            )


def upload_metadata(client, bucket, key, metadata):
    client.put_object_bytes(bucket, key, json_bytes(metadata))


def retry_record(config, client, formatter, record, reporter):
    destination = config["destination"]
    bucket = destination["bucket"]
    metadata = record["metadata"]
    metadata_key = record["key"]
    number = chapter_number(metadata)
    text_name = text_filename(metadata)
    key = text_object_key(config, metadata)
    if not key:
        reporter.report(f"[{number or '?'}] skipped retry formatting: missing text artifact key")
        return {"status": "skipped", "chapter_number": number, "reason": "missing-text-key"}

    try:
        reporter.report(f"[{number}] downloading raw text artifact")
        chapter_text = decode_text_artifact(client.get_object_bytes(bucket, key))
    except FileNotFoundError:
        reporter.report(f"[{number}] skipped retry formatting: raw text artifact missing")
        return {"status": "skipped", "chapter_number": number, "reason": "missing-raw-text"}

    output_formats = set(config.get("formatting", {}).get("output_formats", []))
    retry_attempts = metadata_retry_attempts(metadata)
    reporter.report(
        f"[{number}] checking existing formatted artifacts retry_attempts={retry_attempts}"
    )
    reusable = existing_formatted_artifacts(
        client,
        bucket,
        config,
        metadata,
        chapter_text,
        output_formats,
    )
    if reusable:
        reporter.report(f"[{number}] existing formatted artifacts are valid; updating metadata only")
        apply_formatted_metadata(metadata, config, text_name, reusable)
        update_formatting_metadata(
            metadata,
            config,
            "formatted",
            None,
            chapter_text,
            retry_attempts,
            model_used=config.get("formatting", {}).get("model"),
        )
        reporter.report(f"[{number}] uploading updated metadata")
        upload_metadata(client, bucket, metadata_key, metadata)
        reporter.report(f"[{number}] metadata updated without Sarvam call")
        return {
            "status": "metadata_updated",
            "chapter_number": number,
            "reason": "existing formatted artifacts were valid; no Sarvam call made",
        }

    before = formatter_stats(formatter)
    next_retry_attempts = retry_attempts + 1
    try:
        reporter.report(f"[{number}] retrying formatting attempt {next_retry_attempts}")
        formatted_result = formatter.format_text(chapter_text, progress_label=f"[{number}]")
        delta = formatter_stats_delta(before, formatter_stats(formatter))
        artifact_data = formatted_artifact_bytes(formatted_result, output_formats)
        artifact_keys = formatted_artifact_keys(config, text_name, output_formats)
        for artifact_kind, data in artifact_data.items():
            reporter.report(
                f"[{number}] uploading formatted {artifact_kind} bytes={len(data)}"
            )
            client.put_object_bytes(bucket, artifact_keys[artifact_kind], data)
        apply_formatted_metadata(metadata, config, text_name, artifact_data)
        update_formatting_metadata(
            metadata,
            config,
            "formatted",
            None,
            chapter_text,
            next_retry_attempts,
            attempt_count=delta["request_attempt_count"],
            retry_count=delta["retry_count"],
            throttle_sleep_seconds=delta["throttle_sleep_seconds"],
            model_used=formatted_result.get("model") or config.get("formatting", {}).get("model"),
            token_usage=formatted_result.get("token_usage"),
        )
        reporter.report(f"[{number}] uploading updated metadata")
        upload_metadata(client, bucket, metadata_key, metadata)
        reporter.report(f"[{number}] retry formatting succeeded")
        return {"status": "formatted", "chapter_number": number}
    except Exception as exc:
        delta = formatter_stats_delta(before, formatter_stats(formatter))
        warning = f"retry formatting failed for chapter {number} {text_name}: {exc}"
        reporter.report(f"[{number}] retry formatting failed: {exc}")
        clear_formatted_metadata(metadata)
        update_formatting_metadata(
            metadata,
            config,
            "failed",
            warning,
            chapter_text,
            next_retry_attempts,
            attempt_count=delta["request_attempt_count"],
            retry_count=delta["retry_count"],
            throttle_sleep_seconds=delta["throttle_sleep_seconds"],
            model_used=None,
            token_usage=delta.get("last_token_usage"),
        )
        reporter.report(f"[{number}] uploading failed retry metadata")
        upload_metadata(client, bucket, metadata_key, metadata)
        return {
            "status": "failed",
            "chapter_number": number,
            "warning": warning,
            "retry_attempts": next_retry_attempts,
        }


def print_summary(results, records):
    formatted = [result for result in results if result["status"] == "formatted"]
    metadata_updated = [
        result for result in results if result["status"] == "metadata_updated"
    ]
    failed = [result for result in results if result["status"] == "failed"]
    skipped_results = [result for result in results if result["status"] == "skipped"]
    skipped_records = [record for record in records if record["status"] == "skipped"]
    retry_exhausted = [record for record in records if record["status"] == "retry-exhausted"]
    skipped_count = len(skipped_results) + len(skipped_records)
    print(
        "retry-formatting summary: "
        f"formatted={len(formatted)} metadata_updated={len(metadata_updated)} "
        f"failed={len(failed)} "
        f"skipped={skipped_count} retry_exhausted={len(retry_exhausted)}"
    )
    if metadata_updated:
        print("metadata updated:")
        for result in metadata_updated:
            print(f"- {result.get('chapter_number')} {result.get('reason')}")
    if failed:
        print("failed chapters:")
        for result in failed:
            print(
                f"- {result.get('chapter_number')} "
                f"retry_attempts={result.get('retry_attempts')} "
                f"warning={result.get('warning')}"
            )
    if retry_exhausted:
        print("retry exhausted:")
        for record in retry_exhausted:
            metadata = record["metadata"]
            print(
                f"- {chapter_number(metadata)} "
                f"retry_attempts={metadata_retry_attempts(metadata)} "
                f"warning={metadata.get('formatting', {}).get('warning')}"
            )


def retry_formatting(
    config,
    dry_run=False,
    chapter=None,
    chapters=None,
    r2_client=None,
    formatter=None,
    reporter=DEFAULT_PROGRESS_REPORTER,
):
    if not is_r2(config["destination"]):
        raise SystemExit("retry-formatting requires destination.backend: \"r2\"")
    if not config.get("formatting", {}).get("enabled"):
        raise SystemExit("retry-formatting requires formatting.enabled: true")

    selected_chapters = parse_chapter_filter(chapter=chapter, chapters=chapters)
    client = r2_client or R2StorageClient.from_env()
    records = discover_candidates(config, client, selected_chapters, reporter=reporter)
    if dry_run:
        print_dry_run(records)
        return {"records": records, "results": []}

    selected = [record for record in records if record["status"] == "selected"]
    retry_exhausted = [record for record in records if record["status"] == "retry-exhausted"]
    skipped = [record for record in records if record["status"] == "skipped"]
    reporter.report(
        "retry-formatting selection: "
        f"selected={len(selected)} skipped={len(skipped)} "
        f"retry_exhausted={len(retry_exhausted)}"
    )
    formatter = formatter or SarvamFormatter(config["formatting"], reporter=reporter)
    total = len(selected)
    results = []
    for index, record in enumerate(selected, start=1):
        metadata = record["metadata"]
        reporter.report(
            f"[{index}/{total}] processing chapter {chapter_number(metadata)}"
        )
        results.append(retry_record(config, client, formatter, record, reporter))
    print_summary(results, records)
    return {"records": records, "results": results}
