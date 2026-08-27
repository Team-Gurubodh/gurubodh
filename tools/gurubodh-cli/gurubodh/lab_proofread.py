"""Non-canonical, local-only DOCX proofreading runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import uuid
import zipfile
from xml.etree import ElementTree as ET
from typing import Any, Callable

from gurubodh import __version__
from gurubodh.audit import resolved_build_provenance
from gurubodh.constants import ENTRY_POINT_LAB_PROOFREAD
from gurubodh.docx.export import formatting_defaults, write_chapter_docx
from gurubodh.docx.namespaces import NS
from gurubodh.docx.text import extract_docx_text, iter_docx_text_parts
from gurubodh.docx.validate import validate_docx
from gurubodh.legacy.docx_converter import convert_docx, target_devanagari_font
from gurubodh.legacy.font_detection import run_converter
from gurubodh.locales import locale_spec
from gurubodh.proofreading import GeminiProofreader, ProofreadingError, ProofreadingSettings, word_level_diff
from gurubodh.time_utils import utc_now


COMMAND_NAME = "lab proofread"
MANIFEST_SCHEMA_VERSION = 1


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if value.endswith("\n") else value + "\n", encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def _safe_lab_root(lab_root: str | Path) -> Path:
    root = Path(lab_root).expanduser().resolve()
    if "cms_library" in root.parts:
        raise ValueError("--lab-root must not be cms_library or a path within cms_library.")
    return root


def _run_directory(lab_root: Path) -> tuple[str, Path]:
    run_id = f"{utc_now().replace(':', '').replace('-', '').replace('+00:00', 'Z')}-{uuid.uuid4().hex}"
    run_dir = lab_root / "proofread" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


def _relative_path(run_dir: Path, path: Path) -> str:
    return str(path.relative_to(run_dir))


def _artifact_checksums(run_dir: Path) -> dict[str, str]:
    return {
        _relative_path(run_dir, path): _sha256(path)
        for path in sorted(run_dir.rglob("*"))
        if path.is_file() and path.name != "run_manifest.json"
    }


def _detect_font_encodings(source: Path) -> list[str]:
    detected: set[str] = set()
    with zipfile.ZipFile(source) as package:
        for name in iter_docx_text_parts(package):
            root = ET.fromstring(package.read(name))
            for run in root.findall(".//w:r", NS):
                converter = run_converter(run)
                if converter:
                    detected.add(converter)
    return sorted(detected)


def _canonical_text(text: str) -> str:
    return text.rstrip("\n") + "\n" if text.strip() else "\n"


def _report_markdown(manifest: dict[str, Any]) -> str:
    source = manifest["source"]
    lines = [
        "# Gurubodh lab proofread run",
        "",
        f"- Run ID: `{manifest['run_id']}`",
        f"- Outcome: `{manifest['outcome']}`",
        f"- Locale: `{manifest['locale']['language']}`",
        f"- Source: `{source['path']}`",
        f"- Source SHA-256: `{source.get('sha256', 'unavailable')}`",
        f"- Source font encoding: `{source.get('font_encoding', 'unavailable')}`",
        f"- Command: `{manifest['command']['entry_point']}`",
    ]
    if manifest.get("error"):
        lines.extend(("", f"- Error: {manifest['error']}"))
    return "\n".join(lines) + "\n"


def _base_manifest(run_id: str, run_dir: Path, source: Path, locale: Any, context: Any) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": utc_now(),
        "outcome": "running",
        "non_canonical": True,
        "run_directory": str(run_dir),
        "source": {"path": str(source)},
        "locale": locale.proofreading_provenance(),
        "command": {
            "name": COMMAND_NAME,
            "entry_point": ENTRY_POINT_LAB_PROOFREAD,
            "package_version": __version__,
            "build_provenance": resolved_build_provenance(context.root),
        },
    }


def _write_final_reports(run_dir: Path, manifest: dict[str, Any]) -> Path:
    report_path = run_dir / "report" / "run_report.md"
    _write_text(report_path, _report_markdown(manifest))
    manifest["artifact_sha256"] = _artifact_checksums(run_dir)
    manifest_path = run_dir / "run_manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def run_lab_proofread(
    context: Any,
    source: str | Path,
    locale_name: str,
    lab_root: str | Path,
    proofreader: Any | None = None,
    settings: ProofreadingSettings | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Proofread one DOCX into a distinct non-canonical lab run.

    The source is opened read-only.  All transient conversion and every durable
    artifact are contained beneath the explicit lab root.
    """
    locale = locale_spec(locale_name)
    root = _safe_lab_root(lab_root)
    source_path = Path(source).expanduser().resolve()
    run_id, run_dir = _run_directory(root)
    manifest = _base_manifest(run_id, run_dir, source_path, locale, context)

    try:
        if source_path.suffix.lower() != ".docx":
            raise ValueError("--source must name a .docx file.")
        if not source_path.is_file():
            raise FileNotFoundError(f"Source DOCX does not exist: {source_path}")
        validate_docx(source_path)
        manifest["source"]["sha256"] = _sha256(source_path)
        encodings = _detect_font_encodings(source_path)
        manifest["source"]["font_encoding"] = "+".join(encodings) if encodings else "unicode"

        if encodings:
            if progress:
                progress("Converting detected legacy-font text to a transient Unicode DOCX.")
            with tempfile.TemporaryDirectory(prefix="legacy-conversion-", dir=run_dir) as working_dir:
                converted = Path(working_dir) / "converted.docx"
                conversion = convert_docx(
                    source_path,
                    target_devanagari_font(),
                    context.legacy_converter,
                    converted,
                    progress=lambda *_: None,
                )
                source_text = _canonical_text(extract_docx_text(converted))
                manifest["source"]["legacy_conversion"] = {
                    "converter_counts": conversion["converter_counts"],
                    "total_nodes": conversion["total_nodes"],
                    "total_chars": conversion["total_chars"],
                }
        else:
            source_text = _canonical_text(extract_docx_text(source_path))

        source_text_path = run_dir / "report" / "extracted_source.txt"
        _write_text(source_text_path, source_text)
        manifest["source"]["extracted_text"] = _relative_path(run_dir, source_text_path)
        manifest["source"]["extracted_text_sha256"] = _sha256(source_text_path)

        selected_settings = settings or ProofreadingSettings()
        if len(source_text) > selected_settings.max_input_characters:
            raise ProofreadingError(
                "input_too_large",
                f"Extracted source has {len(source_text)} characters; configured proofreading limit is {selected_settings.max_input_characters}.",
            )
        if progress:
            progress("Sending one structured Gemini proofreading request.")
        response = (proofreader or GeminiProofreader(selected_settings, locale=locale)).proofread(
            source_text, progress=progress
        )
        corrected_text = _canonical_text(response["corrected_text"])
        corrected_text_path = run_dir / "output" / "corrected_proofread.txt"
        _write_text(corrected_text_path, corrected_text)
        diff_text, diff_summary = word_level_diff(source_text, corrected_text)
        diff_path = run_dir / "report" / "proofreading.diff.txt"
        _write_text(diff_path, "Word-level proof-reading diff. [-removed-] {+added+}\n\n" + diff_text)
        details_path = run_dir / "report" / "proofreading_details.json"
        _write_json(
            details_path,
            {
                "schema_version": 1,
                "status": "succeeded",
                "provider": {"name": selected_settings.provider, "model": selected_settings.model},
                "proofreading_locale": locale.proofreading_provenance(),
                "source_text": {
                    "path": _relative_path(run_dir, source_text_path),
                    "sha256": _sha256(source_text_path),
                },
                "corrected_text": {
                    "path": _relative_path(run_dir, corrected_text_path),
                    "sha256": _sha256(corrected_text_path),
                },
                "diff": {
                    "path": _relative_path(run_dir, diff_path),
                    "sha256": _sha256(diff_path),
                    "summary": diff_summary,
                },
                "gemini_edits": response["edits"],
                "request": {
                    key: response[key]
                    for key in ("estimated_input_tokens", "attempts", "throttle_seconds", "usage")
                },
            },
        )
        title = f"{source_path.stem}: proofread"
        corrected_docx_path = run_dir / "output" / "corrected_proofread.docx"
        write_chapter_docx(corrected_docx_path, corrected_text, title, locale.language)
        manifest.update(
            {
                "outcome": "succeeded",
                "proofreading": {"correction_count": len(response["edits"]), "diff_summary": diff_summary},
                "output": {
                    "corrected_text": _relative_path(run_dir, corrected_text_path),
                    "corrected_docx": _relative_path(run_dir, corrected_docx_path),
                    "docx_title": title,
                    "formatting": formatting_defaults(),
                    "structured_details": _relative_path(run_dir, details_path),
                    "readable_diff": _relative_path(run_dir, diff_path),
                },
            }
        )
    except Exception as exc:
        manifest["outcome"] = "failed"
        manifest["error"] = str(exc)
        _write_final_reports(run_dir, manifest)
        raise

    manifest_path = _write_final_reports(run_dir, manifest)
    return {"run_id": run_id, "run_directory": run_dir, "manifest_path": manifest_path}
