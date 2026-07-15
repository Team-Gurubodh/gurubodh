import copy
import json
import re
import zipfile
from xml.etree import ElementTree as ET

from gurubodh_utils.docx.namespaces import NS, W
from gurubodh_utils.docx.text import block_text
from gurubodh_utils.docx.validate import validate_docx
from gurubodh_utils.formatting import SarvamFormatter, source_text_sha256
from gurubodh_utils.metadata import build_chapter_metadata
from gurubodh_utils.naming import chapter_output_filename, full_subject_output_filename
from gurubodh_utils.progress import DEFAULT_PROGRESS_REPORTER
from gurubodh_utils.text_utils import normalize_spaces, safe_filename
from gurubodh_utils.time_utils import utc_now


def chapter_starts(text, chapter_split):
    pattern = chapter_split["pattern"]
    if chapter_split.get("pattern_type") == "regex":
        return chapter_split["_compiled_pattern"].search(text) is not None
    return pattern in text


def is_invocation(text):
    return "श्री स्वामी" in text or "जय जय" in text


def detect_subject_blocks(blocks):
    candidates = []
    for block in blocks[:8]:
        text = normalize_spaces(block_text(block))
        if not text:
            continue
        if "विषय" in text:
            return [copy.deepcopy(block)]
        candidates.append((block, text))

    for block, text in candidates:
        if is_invocation(text) or "प्रबोधन क्र" in text:
            continue
        return [copy.deepcopy(block)]
    return []


def chapter_title(text, index):
    text = normalize_spaces(text)
    match = re.search(r"प्रबोधन\s+क्र\.?\s*([^\s]+)", text)
    if match:
        return f"{index:03d}-प्रबोधन-क्र-{safe_filename(match.group(1))}"
    return f"{index:03d}-{safe_filename(text)}"


def chapter_text(blocks):
    parts = []
    for block in blocks:
        text = normalize_spaces(block_text(block))
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def split_body_into_chapters(body, chapter_split):
    children = list(body)
    sect_pr = None
    content_blocks = []
    for child in children:
        if child.tag == W + "sectPr":
            sect_pr = child
        else:
            content_blocks.append(child)

    chapters = []
    preface = []
    current = None
    for block in content_blocks:
        text = block_text(block)
        starts_chapter = block.tag == W + "p" and chapter_starts(text, chapter_split)
        if starts_chapter:
            if current:
                chapters.append(current)
            current = [block]
        elif current is None:
            preface.append(block)
        else:
            current.append(block)

    if current:
        chapters.append(current)

    return preface, chapters, sect_pr


def chapter_document_xml(document_xml, chapter_blocks, subject_blocks, sect_pr):
    root = ET.fromstring(document_xml)
    body = root.find("w:body", NS)
    if body is None:
        raise RuntimeError("word/document.xml has no body")

    for child in list(body):
        body.remove(child)

    for block in subject_blocks:
        body.append(copy.deepcopy(block))
    for block in chapter_blocks:
        body.append(copy.deepcopy(block))
    if sect_pr is not None:
        body.append(copy.deepcopy(sect_pr))

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def write_chapter_docx(source_docx, output_path, document_xml):
    with zipfile.ZipFile(source_docx) as source:
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                data = document_xml if info.filename == "word/document.xml" else source.read(info.filename)
                target.writestr(info, data)


def formatted_artifact_names(text_name):
    base_name = text_name.removesuffix(".txt")
    return {
        "json": f"{base_name}.formatted.json",
        "markdown": f"{base_name}.formatted.md",
    }


def formatted_markdown(paragraphs):
    return "\n\n".join(paragraph.strip() for paragraph in paragraphs if paragraph.strip()) + "\n"


def write_formatted_artifacts(chapter_text_dir, text_name, formatted_result, output_formats):
    names = formatted_artifact_names(text_name)
    written = {}

    if "json" in output_formats:
        json_path = chapter_text_dir / names["json"]
        json_path.write_text(
            json.dumps(formatted_result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written["json"] = json_path

    if "markdown" in output_formats:
        markdown_path = chapter_text_dir / names["markdown"]
        markdown_path.write_text(
            formatted_markdown(formatted_result["paragraphs"]),
            encoding="utf-8",
        )
        written["markdown"] = markdown_path

    return written


def reusable_formatted_artifacts(chapter_text_dir, text_name, chapter_text_value, output_formats):
    names = formatted_artifact_names(text_name)
    json_path = chapter_text_dir / names["json"]
    markdown_path = chapter_text_dir / names["markdown"]

    if "json" in output_formats and not json_path.exists():
        return None
    if "markdown" in output_formats and not markdown_path.exists():
        return None

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if data.get("status") != "formatted":
        return None
    if data.get("source_text_sha256") != source_text_sha256(chapter_text_value):
        return None

    paragraphs = data.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs:
        return None
    if any(not isinstance(paragraph, str) or not paragraph.strip() for paragraph in paragraphs):
        return None

    artifacts = {}
    if "json" in output_formats:
        artifacts["json"] = json_path
    if "markdown" in output_formats:
        artifacts["markdown"] = markdown_path
    return artifacts


def format_chapter_artifacts(
    chapter_text_dir,
    text_name,
    chapter_number,
    chapter_text_value,
    formatting_config,
    formatter,
    chapter_total=None,
    reporter=DEFAULT_PROGRESS_REPORTER,
):
    label = f"[{chapter_number}/{chapter_total}]" if chapter_total else f"[{chapter_number}]"
    base_name = text_name.removesuffix(".txt")
    if not formatting_config or not formatting_config.get("enabled"):
        return {
            "status": "disabled",
            "warning": None,
            "artifacts": {},
            "attempt_count": 0,
            "retry_count": 0,
            "throttle_sleep_seconds": 0,
            "model_used": None,
        }

    stats_before = formatter_stats(formatter)
    try:
        output_formats = set(formatting_config["output_formats"])
        if formatting_config.get("regenerate") == "when-source-checksum-changes":
            artifacts = reusable_formatted_artifacts(
                chapter_text_dir,
                text_name,
                chapter_text_value,
                output_formats,
            )
            if artifacts:
                reporter.report(f"{label} skipped formatting: unchanged source checksum")
                return {
                    "status": "skipped-unchanged",
                    "warning": None,
                    "artifacts": artifacts,
                    "attempt_count": 0,
                    "retry_count": 0,
                    "throttle_sleep_seconds": 0,
                    "model_used": formatting_config.get("model"),
                }

        reporter.report(
            f"{label} formatting with {formatting_config['model']} "
            f"chars={len(chapter_text_value)} max_tokens={formatting_config.get('max_tokens')}"
        )
        formatted_result = formatter.format_text(chapter_text_value, progress_label=label)
        stats_delta = formatter_stats_delta(stats_before, formatter_stats(formatter))
        artifacts = write_formatted_artifacts(
            chapter_text_dir,
            text_name,
            formatted_result,
            output_formats,
        )
        reporter.report(f"{label} formatted paragraphs={len(formatted_result['paragraphs'])}")
        return {
            "status": "formatted",
            "warning": None,
            "artifacts": artifacts,
            "attempt_count": stats_delta["request_attempt_count"],
            "retry_count": stats_delta["retry_count"],
            "throttle_sleep_seconds": stats_delta["throttle_sleep_seconds"],
            "model_used": formatted_result.get("model") or formatting_config.get("model"),
        }
    except Exception as exc:
        stats_delta = formatter_stats_delta(stats_before, formatter_stats(formatter))
        warning = f"formatting failed for chapter {chapter_number:03d} {base_name}: {exc}"
        reporter.report(f"{label} formatting failed: {exc}")
        if not formatting_config.get("continue_on_error", True):
            raise SystemExit(warning) from exc
        print(f"warning: {warning}")
        return {
            "status": "failed",
            "warning": warning,
            "artifacts": {},
            "attempt_count": stats_delta["request_attempt_count"],
            "retry_count": stats_delta["retry_count"],
            "throttle_sleep_seconds": stats_delta["throttle_sleep_seconds"],
            "model_used": None,
        }


def formatter_stats(formatter):
    if formatter is None:
        return {
            "request_attempt_count": 0,
            "retry_count": 0,
            "throttle_sleep_seconds": 0,
        }
    return {
        "request_attempt_count": getattr(formatter, "request_attempt_count", 0),
        "retry_count": getattr(formatter, "retry_count", 0),
        "throttle_sleep_seconds": getattr(formatter, "throttle_sleep_seconds", 0),
    }


def formatter_stats_delta(before, after):
    return {
        key: after.get(key, 0) - before.get(key, 0)
        for key in ("request_attempt_count", "retry_count", "throttle_sleep_seconds")
    }


def print_formatting_summary(summary):
    total = (
        summary["formatted"]
        + summary["skipped-unchanged"]
        + summary["failed"]
        + summary["disabled"]
    )
    if total == 0:
        return
    print(
        "formatting summary: "
        f"formatted={summary['formatted']} "
        f"skipped_unchanged={summary['skipped-unchanged']} "
        f"failed={summary['failed']} "
        f"disabled={summary['disabled']}"
    )


def formatted_metadata_file_names(formatting_result, subject_dir):
    file_names = {}
    artifacts = formatting_result.get("artifacts", {}) if formatting_result else {}

    json_path = artifacts.get("json")
    if json_path:
        file_names["formatted_json"] = json_path.name
        file_names["formatted_json_path"] = json_path
        file_names["formatted_json_relative_path"] = json_path.relative_to(subject_dir)

    markdown_path = artifacts.get("markdown")
    if markdown_path:
        file_names["formatted_markdown"] = markdown_path.name
        file_names["formatted_markdown_path"] = markdown_path
        file_names["formatted_markdown_relative_path"] = markdown_path.relative_to(subject_dir)

    return file_names


def split_docx_into_chapters(
    docx_path,
    chapter_split,
    chapter_docx_dir,
    chapter_text_dir,
    config=None,
    converter_counts=None,
    entry_point=None,
    reporter=DEFAULT_PROGRESS_REPORTER,
):
    with zipfile.ZipFile(docx_path) as docx:
        document_xml = docx.read("word/document.xml")

    root = ET.fromstring(document_xml)
    body = root.find("w:body", NS)
    if body is None:
        raise RuntimeError("word/document.xml has no body")

    preface, chapters, sect_pr = split_body_into_chapters(body, chapter_split)
    if not chapters:
        print(f"no chapters found using pattern: {chapter_split['pattern']}")
        return []

    subject_blocks = detect_subject_blocks(preface)
    chapter_docx_dir.mkdir(parents=True, exist_ok=True)
    chapter_text_dir.mkdir(parents=True, exist_ok=True)

    outputs = []
    created_at = utc_now()
    formatting_config = config.get("formatting") if config else None
    formatter = (
        SarvamFormatter(formatting_config, reporter=reporter)
        if formatting_config and formatting_config.get("enabled")
        else None
    )
    formatting_summary = {"formatted": 0, "skipped-unchanged": 0, "failed": 0, "disabled": 0}
    chapter_total = len(chapters)
    for index, blocks in enumerate(chapters, start=1):
        if config:
            docx_name = chapter_output_filename(config, index, ".docx")
            text_name = chapter_output_filename(config, index, ".txt")
            metadata_name = chapter_output_filename(config, index, ".json")
        else:
            title = chapter_title(block_text(blocks[0]), index)
            docx_name = f"{title}.docx"
            text_name = f"{title}.txt"
            metadata_name = None

        base_name = text_name.removesuffix(".txt")
        reporter.report(f"[{index}/{chapter_total}] writing chapter {base_name}")
        output_path = chapter_docx_dir / docx_name
        text_path = chapter_text_dir / text_name
        xml = chapter_document_xml(document_xml, blocks, subject_blocks, sect_pr)
        write_chapter_docx(docx_path, output_path, xml)
        text_value = chapter_text(subject_blocks + blocks)
        text_path.write_text(text_value + "\n", encoding="utf-8")
        if config:
            formatting_result = format_chapter_artifacts(
                chapter_text_dir,
                text_name,
                index,
                text_value,
                formatting_config,
                formatter,
                chapter_total=chapter_total,
                reporter=reporter,
            )
            formatting_summary[formatting_result["status"]] += 1
        if config:
            metadata = build_chapter_metadata(
                config,
                index,
                {
                    "metadata": metadata_name,
                    "text": text_name,
                    "msword": docx_name,
                    "metadata_relative_path": (chapter_text_dir / metadata_name).relative_to(
                        chapter_text_dir.parents[1]
                    ),
                    "text_relative_path": (chapter_text_dir / text_name).relative_to(
                        chapter_text_dir.parents[1]
                    ),
                    "msword_relative_path": (chapter_docx_dir / docx_name).relative_to(
                        chapter_docx_dir.parents[1]
                    ),
                    "full_msword_relative_path": (
                        chapter_docx_dir.parents[1]
                        / "full_subject"
                        / full_subject_output_filename(config, ".docx")
                    ).relative_to(chapter_docx_dir.parents[1]),
                    "full_text_relative_path": (
                        chapter_docx_dir.parents[1]
                        / "full_subject"
                        / full_subject_output_filename(config, ".txt")
                    ).relative_to(chapter_docx_dir.parents[1]),
                    **formatted_metadata_file_names(
                        formatting_result,
                        chapter_text_dir.parents[1],
                    ),
                },
                text_value,
                converter_counts or {},
                created_at,
                entry_point or "",
                formatting_result,
            )
            (chapter_text_dir / metadata_name).write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        validate_docx(output_path)
        outputs.append(output_path)

    print(f"wrote {len(outputs)} chapter files under {chapter_docx_dir}")
    print(f"wrote {len(outputs)} chapter text files under {chapter_text_dir}")
    print_formatting_summary(formatting_summary)
    return outputs
