"""Detect supported and unsupported source fonts in DOCX text runs."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from gurubodh.docx.namespaces import NS, W
from gurubodh.docx.text import iter_docx_text_parts


APS_FONT_PATTERNS = (
    "aps-dv",
    "aps dv",
    "aps_dv",
    "priyanka",
    "prakash",
)

UNSUPPORTED_SHREELIPI_FONT_PATTERNS = (
    "shreelipi",
    "shree-lipi",
    "shree lipi",
    "srilipi",
    "sri-lipi",
    "sri lipi",
    "shree-dev",
    "shreedev",
)

# This is deliberately a centrally reviewed allowlist. Job configuration must
# never grant an unreviewed source font permission.
APPROVED_UNICODE_FONT_FAMILIES = frozenset(
    {
        "aparajita",
        "aptos",
        "arial",
        "arial unicode ms",
        "calibri",
        "cambria",
        "hind",
        "kohinoor devanagari",
        "kokila",
        "lohit devanagari",
        "mangal",
        "mukta",
        "nirmala ui",
        "noto sans devanagari",
        "noto serif devanagari",
        "sanskrit 2003",
        "shobhika",
        "times new roman",
        "tiro devanagari hindi",
        "utsaah",
    }
)

_FONT_VALUE_NAMES = ("ascii", "hAnsi", "cs", "eastAsia")
_THEME_VALUE_NAMES = ("asciiTheme", "hAnsiTheme", "csTheme", "eastAsiaTheme")
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


class UnsupportedSourceFontError(ValueError):
    """Raised before processing an unsupported source font."""


@dataclass(frozen=True)
class SourceFont:
    family: str
    part_name: str


def _normalized(font_name: str) -> str:
    return " ".join(font_name.casefold().split())


def _font_kind(font_name: str) -> str | None:
    normalized = _normalized(font_name)
    if any(pattern in normalized for pattern in UNSUPPORTED_SHREELIPI_FONT_PATTERNS):
        return "shreelipi"
    if any(pattern in normalized for pattern in APS_FONT_PATTERNS):
        return "aps"
    if normalized in APPROVED_UNICODE_FONT_FAMILIES:
        return "unicode"
    return None


def detect_converter_for_font(font_name):
    """Return the only supported legacy converter for a font family."""
    return "aps" if _font_kind(font_name or "") == "aps" else None


def is_legacy_font(font_name):
    return detect_converter_for_font(font_name) is not None


def rfonts_values(rfonts):
    if rfonts is None:
        return []
    return [
        value
        for key, value in rfonts.attrib.items()
        if key.rsplit("}", 1)[-1] in _FONT_VALUE_NAMES
    ]


def run_converter(run):
    rfonts = run.find("w:rPr/w:rFonts", NS)
    for value in rfonts_values(rfonts):
        converter = detect_converter_for_font(value)
        if converter:
            return converter
    return None


def _font_attributes(rfonts) -> dict[str, str]:
    if rfonts is None:
        return {}
    return {
        key.rsplit("}", 1)[-1]: value
        for key, value in rfonts.attrib.items()
        if key.rsplit("}", 1)[-1] in (*_FONT_VALUE_NAMES, *_THEME_VALUE_NAMES)
    }


def _rpr_font_attributes(element) -> dict[str, str]:
    if element is None:
        return {}
    return _font_attributes(element.find("w:rFonts", NS))


def _theme_fonts(package: zipfile.ZipFile) -> dict[str, str]:
    try:
        root = ET.fromstring(package.read("word/theme/theme1.xml"))
    except KeyError:
        return {}
    scheme = root.find(f".//{{{_A_NS}}}fontScheme")
    if scheme is None:
        return {}
    values = {}
    for group_name, prefix in (("majorFont", "major"), ("minorFont", "minor")):
        group = scheme.find(f"{{{_A_NS}}}{group_name}")
        if group is None:
            continue
        for element_name, suffix in (("latin", "HAnsi"), ("ea", "EastAsia"), ("cs", "Bidi")):
            element = group.find(f"{{{_A_NS}}}{element_name}")
            if element is not None and element.get("typeface"):
                values[f"{prefix}{suffix}"] = element.get("typeface")
                if suffix == "HAnsi":
                    values[f"{prefix}Ascii"] = element.get("typeface")
    return values


def _styles(package: zipfile.ZipFile) -> tuple[dict[str, tuple[str | None, dict[str, str]]], dict[str, str]]:
    try:
        root = ET.fromstring(package.read("word/styles.xml"))
    except KeyError:
        return {}, {}
    defaults = _rpr_font_attributes(root.find("w:docDefaults/w:rPrDefault/w:rPr", NS))
    styles = {}
    for style in root.findall("w:style", NS):
        style_id = style.get(W + "styleId")
        if not style_id:
            continue
        attributes = _rpr_font_attributes(style.find("w:rPr", NS))
        attributes.update(_rpr_font_attributes(style.find("w:pPr/w:rPr", NS)))
        based_on = style.find("w:basedOn", NS)
        styles[style_id] = (based_on.get(W + "val") if based_on is not None else None, attributes)
    return styles, defaults


def _style_font_attributes(style_id, styles, seen=None) -> dict[str, str]:
    if not style_id or style_id not in styles:
        return {}
    seen = seen or set()
    if style_id in seen:
        return {}
    based_on, attributes = styles[style_id]
    resolved = _style_font_attributes(based_on, styles, seen | {style_id})
    resolved.update(attributes)
    return resolved


def _effective_font_attributes(run, paragraph, styles, defaults) -> dict[str, str]:
    attributes = dict(defaults)
    paragraph_style = paragraph.find("w:pPr/w:pStyle", NS)
    if paragraph_style is not None:
        attributes.update(_style_font_attributes(paragraph_style.get(W + "val"), styles))
    attributes.update(_rpr_font_attributes(paragraph.find("w:pPr/w:rPr", NS)))
    run_style = run.find("w:rPr/w:rStyle", NS)
    if run_style is not None:
        attributes.update(_style_font_attributes(run_style.get(W + "val"), styles))
    attributes.update(_rpr_font_attributes(run.find("w:rPr", NS)))
    return attributes


def _families(attributes, theme_fonts) -> list[str]:
    values = []
    for name in _FONT_VALUE_NAMES:
        if attributes.get(name):
            values.append(attributes[name])
    for name in _THEME_VALUE_NAMES:
        if attributes.get(name) and theme_fonts.get(attributes[name]):
            values.append(theme_fonts[attributes[name]])
    return list(dict.fromkeys(value for value in values if value))


def effective_run_converter(run, paragraph, styles, defaults, theme_fonts):
    """Return the APS converter selected by the run's effective font."""
    attributes = _effective_font_attributes(run, paragraph, styles, defaults)
    for family in _families(attributes, theme_fonts):
        converter = detect_converter_for_font(family)
        if converter:
            return converter
    return None


def source_fonts(path) -> list[SourceFont]:
    """Return effective font families for every text-bearing DOCX run."""
    found = []
    with zipfile.ZipFile(path) as package:
        styles, defaults = _styles(package)
        theme_fonts = _theme_fonts(package)
        for part_name in iter_docx_text_parts(package):
            root = ET.fromstring(package.read(part_name))
            for paragraph in root.findall(".//w:p", NS):
                for run in paragraph.findall(".//w:r", NS):
                    if not run.findall(".//w:t", NS):
                        continue
                    attributes = _effective_font_attributes(run, paragraph, styles, defaults)
                    found.extend(SourceFont(family, part_name) for family in _families(attributes, theme_fonts))
    return found


def validate_supported_source_fonts(path) -> list[SourceFont]:
    """Reject a DOCX before any conversion, proofreading, or publication."""
    fonts = source_fonts(path)
    for source_font in fonts:
        kind = _font_kind(source_font.family)
        if kind == "shreelipi":
            raise UnsupportedSourceFontError(
                f'Unsupported source font family detected: "{source_font.family}". '
                "ShreeLipi/Sri-Lipi conversion is disabled because verified font-specific mappings are unavailable. "
                "This document was not processed; no canonical artifacts were created or published."
            )
        if kind is None:
            raise UnsupportedSourceFontError(
                f'Unsupported source font family detected: "{source_font.family}". '
                "Gurubodh accepts only approved Unicode and APS font families. "
                "This document was not processed; no canonical artifacts were created or published."
            )
    return fonts
