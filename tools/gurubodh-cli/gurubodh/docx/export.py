"""Deterministic, validated DOCX rendering for canonical chapter text."""

import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


FONT_NAME = "Noto Sans Devanagari"
BODY_FONT_SIZE_PT = 11
TITLE_FONT_SIZE_PT = 18
MARGIN_INCHES = 1.0
BODY_SPACE_AFTER_PT = 8
TITLE_SPACE_AFTER_PT = 12
LINE_SPACING = 1.15
PACKAGE_TIMESTAMP = (2000, 1, 1, 0, 0, 0)


def formatting_defaults():
    return {
        "font_name": FONT_NAME,
        "body_font_size_pt": BODY_FONT_SIZE_PT,
        "title_font_size_pt": TITLE_FONT_SIZE_PT,
        "margin_inches": MARGIN_INCHES,
        "body_space_after_pt": BODY_SPACE_AFTER_PT,
        "title_space_after_pt": TITLE_SPACE_AFTER_PT,
        "line_spacing": LINE_SPACING,
        "paragraph_direction": "left-to-right",
        "paragraph_mapping": "blank-line-v1",
        "artifact_final_newline": "exactly-one-LF-excluded-from-body",
    }


def generated_title(title_slug, chapter_number):
    return f"{title_slug}: prabodhan {chapter_number}"


def canonical_body(text):
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise ValueError("Canonical chapter text must use exactly one artifact-final LF.")
    return text[:-1]


def paragraph_values(text):
    """Map exact blank-line delimiters to Word paragraphs without reflow."""
    return canonical_body(text).split("\n\n")


def _set_font(style, size, language):
    style.font.name = FONT_NAME
    style.font.size = Pt(size)
    rpr = style.element.get_or_add_rPr()
    fonts = rpr.get_or_add_rFonts()
    for attribute in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{attribute}"), FONT_NAME)
    lang = rpr.find(qn("w:lang"))
    if lang is None:
        lang = OxmlElement("w:lang")
        rpr.append(lang)
    lang.set(qn("w:val"), language)
    lang.set(qn("w:eastAsia"), language)
    lang.set(qn("w:bidi"), language)


def _set_ltr(paragraph):
    ppr = paragraph._p.get_or_add_pPr()
    bidi = ppr.find(qn("w:bidi"))
    if bidi is None:
        bidi = OxmlElement("w:bidi")
        ppr.append(bidi)
    bidi.set(qn("w:val"), "0")


def _add_preserved_text(paragraph, value):
    lines = value.split("\n")
    run = paragraph.add_run()
    for index, line in enumerate(lines):
        if index:
            run.add_break(WD_BREAK.LINE)
        run.add_text(line)


def _normalize_package(path):
    """Fix ZIP metadata so identical content produces identical DOCX bytes."""
    source_path = Path(path)
    with tempfile.NamedTemporaryFile(suffix=".docx", dir=source_path.parent, delete=False) as handle:
        normalized_path = Path(handle.name)
    try:
        with zipfile.ZipFile(source_path, "r") as source, zipfile.ZipFile(
            normalized_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as destination:
            for original in sorted(source.infolist(), key=lambda item: item.filename):
                info = zipfile.ZipInfo(original.filename, date_time=PACKAGE_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.comment = original.comment
                info.extra = b""
                info.internal_attr = original.internal_attr
                info.external_attr = original.external_attr
                info.create_system = original.create_system
                destination.writestr(info, source.read(original.filename), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        shutil.move(normalized_path, source_path)
    finally:
        normalized_path.unlink(missing_ok=True)


def write_chapter_docx(path, text, title, language):
    path = Path(path)
    values = paragraph_values(text)
    document = Document()
    fixed_time = datetime(2000, 1, 1)
    document.core_properties.created = fixed_time
    document.core_properties.modified = fixed_time
    document.core_properties.last_modified_by = "Gurubodh CLI"
    document.core_properties.revision = 1
    for section in document.sections:
        section.top_margin = Inches(MARGIN_INCHES)
        section.bottom_margin = Inches(MARGIN_INCHES)
        section.left_margin = Inches(MARGIN_INCHES)
        section.right_margin = Inches(MARGIN_INCHES)
    normal = document.styles["Normal"]
    title_style = document.styles["Title"]
    _set_font(normal, BODY_FONT_SIZE_PT, language)
    _set_font(title_style, TITLE_FONT_SIZE_PT, language)
    normal.paragraph_format.space_after = Pt(BODY_SPACE_AFTER_PT)
    normal.paragraph_format.line_spacing = LINE_SPACING
    title_style.paragraph_format.space_after = Pt(TITLE_SPACE_AFTER_PT)

    heading = document.add_paragraph(style="Title")
    _set_ltr(heading)
    _add_preserved_text(heading, title)
    for value in values:
        paragraph = document.add_paragraph(style="Normal")
        _set_ltr(paragraph)
        _add_preserved_text(paragraph, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path)
    _normalize_package(path)
    validate_chapter_docx(path, text, title)


def validate_chapter_docx(path, canonical_text, title):
    path = Path(path)
    if not zipfile.is_zipfile(path):
        raise ValueError(f"Generated DOCX is not a ZIP/OOXML package: {path}")
    with zipfile.ZipFile(path, "r") as package:
        bad_member = package.testzip()
        if bad_member:
            raise ValueError(f"Generated DOCX has a corrupt ZIP member: {bad_member}")
        required = {"[Content_Types].xml", "word/document.xml"}
        missing = required - set(package.namelist())
        if missing:
            raise ValueError(f"Generated DOCX is missing required OOXML member(s): {', '.join(sorted(missing))}")
    document = Document(path)
    if not document.paragraphs or document.paragraphs[0].text != title:
        raise ValueError("Generated DOCX title paragraph does not match the configured title.")
    expected_values = paragraph_values(canonical_text)
    actual_values = [paragraph.text for paragraph in document.paragraphs[1:]]
    if actual_values != expected_values:
        raise ValueError("Generated DOCX paragraph/line-break mapping does not reproduce canonical text.")
    reconstructed = "\n\n".join(actual_values) + "\n"
    if reconstructed != canonical_text:
        raise ValueError("Generated DOCX body fails the canonical artifact-final-newline round trip.")
    return True
