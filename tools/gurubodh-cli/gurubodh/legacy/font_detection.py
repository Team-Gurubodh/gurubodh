"""Detect supported and unsupported source fonts in DOCX text runs."""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from gurubodh.docx.namespaces import NS, W
from gurubodh.docx.text import iter_docx_text_parts
from gurubodh.errors import ConfigurationError, SourceValidationError
from gurubodh.resource_discovery import BundledResourceError, bundled_resource_path
from gurubodh.schema_validation import validate_policy


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

_SOURCE_FONT_POLICY = "config/policies/source-fonts.json"

_FONT_VALUE_NAMES = ("ascii", "hAnsi", "cs", "eastAsia")
_THEME_VALUE_NAMES = ("asciiTheme", "hAnsiTheme", "cstheme", "eastAsiaTheme")
_FONT_ATTRIBUTE_PAIRS = tuple(zip(_FONT_VALUE_NAMES, _THEME_VALUE_NAMES))
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


class UnsupportedSourceFontError(SourceValidationError, ValueError):
    """Raised before processing an unsupported source font."""


@dataclass(frozen=True)
class SourceFont:
    family: str
    part_name: str


@dataclass(frozen=True)
class _StyleDefinition:
    style_type: str | None
    based_on: str | None
    font_attributes: dict[str, str]


@dataclass(frozen=True)
class _StyleCatalog:
    definitions: dict[str, _StyleDefinition]
    defaults: dict[str, str]


@dataclass(frozen=True)
class _TextRunFonts:
    families: tuple[str, ...]
    part_name: str
    paragraph_number: int
    run_number: int
    unresolved_theme_references: tuple[str, ...]
    unresolved_style_references: tuple[str, ...]

    @property
    def location(self) -> str:
        return (
            f'DOCX part "{self.part_name}", paragraph '
            f"{self.paragraph_number}, run {self.run_number}"
        )


def _normalized(font_name: str) -> str:
    return " ".join(font_name.casefold().split())


def _legacy_font_kind(font_name: str) -> str | None:
    normalized = _normalized(font_name)
    if any(pattern in normalized for pattern in UNSUPPORTED_SHREELIPI_FONT_PATTERNS):
        return "shreelipi"
    if any(pattern in normalized for pattern in APS_FONT_PATTERNS):
        return "aps"
    return None


def _unique_policy_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON property: {key}")
        result[key] = value
    return result


def load_approved_unicode_font_families() -> frozenset[str]:
    """Load shared approvals from this CLI distribution, never a job catalog.

    Read once per source preflight, so a previous successful load cannot mask
    subsequently missing or invalid policy data in a long-lived process.
    """
    try:
        path = bundled_resource_path(_SOURCE_FONT_POLICY)
        policy = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_unique_policy_keys,
        )
    except (BundledResourceError, OSError, ValueError) as exc:
        raise ConfigurationError(
            f"Source-font policy {_SOURCE_FONT_POLICY} is missing, unreadable, or malformed: {exc}"
        ) from exc
    validate_policy(policy, "source-fonts", path)
    approved = set()
    for index, family in enumerate(policy["approved_unicode_font_families"]):
        normalized = _normalized(family)
        location = f"$.approved_unicode_font_families[{index}]"
        legacy_kind = _legacy_font_kind(normalized)
        if legacy_kind:
            raise ConfigurationError(
                f"Source-font policy {path}: {location} ({family!r}) conflicts with "
                f"the known {legacy_kind} legacy-font classification."
            )
        if normalized in approved:
            raise ConfigurationError(
                f"Source-font policy {path}: {location} duplicates a family after "
                "case and whitespace normalization."
            )
        approved.add(normalized)
    return frozenset(approved)


def detect_converter_for_font(font_name):
    """Return the only supported legacy converter for a font family."""
    return "aps" if _legacy_font_kind(font_name or "") == "aps" else None


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


def _font_attributes(rfonts) -> dict[str, str]:
    if rfonts is None:
        return {}
    return {
        (
            "cstheme"
            if key.rsplit("}", 1)[-1] == "csTheme"
            else key.rsplit("}", 1)[-1]
        ): value
        for key, value in rfonts.attrib.items()
        if key.rsplit("}", 1)[-1]
        in (*_FONT_VALUE_NAMES, *_THEME_VALUE_NAMES, "csTheme")
    }


def _rpr_font_attributes(element) -> dict[str, str]:
    if element is None:
        return {}
    return _font_attributes(element.find("w:rFonts", NS))


def _merge_font_attributes(
    inherited: dict[str, str], overriding: dict[str, str]
) -> dict[str, str]:
    """Apply rFonts hierarchy rules to one more-specific formatting level."""
    merged = dict(inherited)
    for family_name, theme_name in _FONT_ATTRIBUTE_PAIRS:
        if family_name in overriding or theme_name in overriding:
            merged.pop(family_name, None)
            merged.pop(theme_name, None)
            if family_name in overriding:
                merged[family_name] = overriding[family_name]
            if theme_name in overriding:
                merged[theme_name] = overriding[theme_name]
    return merged


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
        devanagari = next(
            (
                element.get("typeface")
                for element in group.findall(f"{{{_A_NS}}}font")
                if element.get("script") == "Deva" and element.get("typeface")
            ),
            None,
        )
        for element_name, suffix in (
            ("latin", "HAnsi"),
            ("ea", "EastAsia"),
            ("cs", "Bidi"),
        ):
            element = group.find(f"{{{_A_NS}}}{element_name}")
            typeface = element.get("typeface") if element is not None else None
            if not typeface and suffix in {"EastAsia", "Bidi"}:
                typeface = devanagari
            if typeface:
                values[f"{prefix}{suffix}"] = typeface
                if suffix == "HAnsi":
                    values[f"{prefix}Ascii"] = typeface
    return values


def _styles(package: zipfile.ZipFile) -> tuple[_StyleCatalog, dict[str, str]]:
    try:
        root = ET.fromstring(package.read("word/styles.xml"))
    except KeyError:
        return _StyleCatalog({}, {}), {}
    defaults = _rpr_font_attributes(root.find("w:docDefaults/w:rPrDefault/w:rPr", NS))
    definitions = {}
    default_styles = {}
    for style in root.findall("w:style", NS):
        style_id = style.get(W + "styleId")
        if not style_id:
            continue
        style_type = style.get(W + "type")
        attributes = _rpr_font_attributes(style.find("w:rPr", NS))
        attributes = _merge_font_attributes(
            attributes, _rpr_font_attributes(style.find("w:pPr/w:rPr", NS))
        )
        based_on = style.find("w:basedOn", NS)
        definitions[style_id] = _StyleDefinition(
            style_type,
            based_on.get(W + "val") if based_on is not None else None,
            attributes,
        )
        if style.get(W + "default") in {"1", "true", "on"} and style_type:
            default_styles.setdefault(style_type, style_id)
    return _StyleCatalog(definitions, default_styles), defaults


def _style_font_resolution(
    style_id: str | None,
    styles: _StyleCatalog,
    expected_type: str,
    seen: tuple[str, ...] = (),
) -> tuple[dict[str, str], list[str]]:
    if not style_id:
        return {}, []
    definition = styles.definitions.get(style_id)
    if definition is None:
        return {}, [
            f'{expected_type} style "{style_id}" is not defined in word/styles.xml'
        ]
    if definition.style_type != expected_type:
        return {}, [
            f'{expected_type} style reference "{style_id}" names a '
            f'{definition.style_type or "typeless"} style'
        ]
    if style_id in seen:
        chain = " -> ".join((*seen, style_id))
        return {}, [f"{expected_type} style inheritance cycle: {chain}"]

    inherited = {}
    unresolved = []
    if definition.based_on:
        parent = styles.definitions.get(definition.based_on)
        # OOXML ignores a basedOn reference to a different style type.
        if parent is not None and parent.style_type != expected_type:
            parent = None
        if parent is None:
            if definition.based_on not in styles.definitions:
                unresolved.append(
                    f'{expected_type} style "{style_id}" is based on undefined '
                    f'style "{definition.based_on}"'
                )
        else:
            inherited, parent_unresolved = _style_font_resolution(
                definition.based_on, styles, expected_type, (*seen, style_id)
            )
            unresolved.extend(parent_unresolved)
    return (
        _merge_font_attributes(inherited, definition.font_attributes),
        unresolved,
    )


def _effective_font_resolution(
    run, paragraph, styles: _StyleCatalog, defaults
) -> tuple[dict[str, str], list[str]]:
    attributes = dict(defaults)
    paragraph_style = paragraph.find("w:pPr/w:pStyle", NS)
    paragraph_style_id = (
        paragraph_style.get(W + "val")
        if paragraph_style is not None
        else styles.defaults.get("paragraph")
    )
    paragraph_attributes, unresolved = _style_font_resolution(
        paragraph_style_id, styles, "paragraph"
    )
    attributes = _merge_font_attributes(attributes, paragraph_attributes)
    attributes = _merge_font_attributes(
        attributes, _rpr_font_attributes(paragraph.find("w:pPr/w:rPr", NS))
    )
    run_style = run.find("w:rPr/w:rStyle", NS)
    run_style_id = (
        run_style.get(W + "val")
        if run_style is not None
        else styles.defaults.get("character")
    )
    run_attributes, run_unresolved = _style_font_resolution(
        run_style_id, styles, "character"
    )
    unresolved.extend(run_unresolved)
    attributes = _merge_font_attributes(attributes, run_attributes)
    attributes = _merge_font_attributes(
        attributes, _rpr_font_attributes(run.find("w:rPr", NS))
    )
    return attributes, unresolved


def _effective_font_attributes(run, paragraph, styles, defaults) -> dict[str, str]:
    attributes, _unresolved = _effective_font_resolution(
        run, paragraph, styles, defaults
    )
    return attributes


def _families(attributes, theme_fonts) -> list[str]:
    values = []
    for family_name, theme_name in _FONT_ATTRIBUTE_PAIRS:
        if theme_name in attributes:
            reference = attributes[theme_name]
            if reference and theme_fonts.get(reference):
                values.append(theme_fonts[reference])
        elif attributes.get(family_name):
            values.append(attributes[family_name])
    return list(dict.fromkeys(value for value in values if value))


def _unresolved_theme_references(attributes, theme_fonts) -> list[str]:
    return list(
        dict.fromkeys(
            attributes[theme_name]
            for _family_name, theme_name in _FONT_ATTRIBUTE_PAIRS
            if theme_name in attributes
            and (
                not attributes[theme_name]
                or not theme_fonts.get(attributes[theme_name])
            )
        )
    )


def effective_run_converter(run, paragraph, styles, defaults, theme_fonts):
    """Return the APS converter selected by the run's effective font."""
    attributes = _effective_font_attributes(run, paragraph, styles, defaults)
    for family in _families(attributes, theme_fonts):
        converter = detect_converter_for_font(family)
        if converter:
            return converter
    return None


def _text_run_fonts(path) -> list[_TextRunFonts]:
    runs = []
    with zipfile.ZipFile(path) as package:
        styles, defaults = _styles(package)
        theme_fonts = _theme_fonts(package)
        for part_name in iter_docx_text_parts(package):
            root = ET.fromstring(package.read(part_name))
            for paragraph_number, paragraph in enumerate(
                root.findall(".//w:p", NS), start=1
            ):
                for run_number, run in enumerate(
                    paragraph.findall(".//w:r", NS), start=1
                ):
                    if not any(
                        node.text for node in run.findall(".//w:t", NS)
                    ):
                        continue
                    attributes, unresolved_styles = _effective_font_resolution(
                        run, paragraph, styles, defaults
                    )
                    runs.append(
                        _TextRunFonts(
                            tuple(_families(attributes, theme_fonts)),
                            part_name,
                            paragraph_number,
                            run_number,
                            tuple(
                                _unresolved_theme_references(
                                    attributes, theme_fonts
                                )
                            ),
                            tuple(unresolved_styles),
                        )
                    )
    return runs


def source_fonts(path) -> list[SourceFont]:
    """Return effective font families for every text-bearing DOCX run."""
    return [
        SourceFont(family, run.part_name)
        for run in _text_run_fonts(path)
        for family in run.families
    ]


def validate_supported_source_fonts(path) -> list[SourceFont]:
    """Reject a DOCX before any conversion, proofreading, or publication."""
    approved_unicode = load_approved_unicode_font_families()
    fonts = source_fonts(path)
    for source_font in fonts:
        kind = _legacy_font_kind(source_font.family)
        if kind == "shreelipi":
            raise UnsupportedSourceFontError(
                f'Unsupported source font family detected: "{source_font.family}". '
                "ShreeLipi/Sri-Lipi conversion is disabled because verified font-specific mappings are unavailable. "
                "This document was not processed; no canonical artifacts were created or published."
            )
        if kind is None and _normalized(source_font.family) not in approved_unicode:
            raise UnsupportedSourceFontError(
                f'Unsupported source font family detected: "{source_font.family}". '
                "Gurubodh accepts only approved Unicode and APS font families. "
                "This document was not processed; no canonical artifacts were created or published."
            )
    return fonts


def validate_lab_source_fonts(path) -> list[SourceFont]:
    """Require resolvable approved-Unicode or APS fonts for lab proofreading."""
    approved_unicode = load_approved_unicode_font_families()
    runs = _text_run_fonts(path)
    for run in runs:
        unresolved = []
        unresolved.extend(run.unresolved_style_references)
        unresolved.extend(
            f'theme font reference "{reference}" is not defined by the DOCX theme'
            for reference in run.unresolved_theme_references
        )
        if not run.families and not unresolved:
            unresolved.append(
                "no direct, inherited style, document-default, or theme font "
                "declaration resolves this text-bearing run"
            )
        if unresolved:
            raise UnsupportedSourceFontError(
                "Lab proofread source-font validation failed: effective font "
                f"could not be resolved at {run.location}; "
                f"{'; '.join(unresolved)}. Supply a DOCX whose text-bearing "
                "runs use resolvable supported fonts (approved Unicode or "
                "supported APS). The document was not converted, extracted, "
                "or proofread."
            )

    fonts = [
        SourceFont(family, run.part_name)
        for run in runs
        for family in run.families
    ]
    for run in runs:
        for family in run.families:
            kind = _legacy_font_kind(family)
            if kind == "shreelipi":
                raise UnsupportedSourceFontError(
                    f'Unsupported source font family detected: "{family}" at '
                    f"{run.location}. ShreeLipi/Sri-Lipi conversion is disabled "
                    "because verified font-specific mappings are unavailable. "
                    "The document was not converted, extracted, or proofread."
                )
            if kind is None and _normalized(family) not in approved_unicode:
                raise UnsupportedSourceFontError(
                    f'Unsupported source font family detected: "{family}" at '
                    f"{run.location}. Gurubodh accepts only approved Unicode and "
                    "APS font families. The document was not converted, "
                    "extracted, or proofread."
                )
    return fonts


def validate_unicode_source_fonts(path) -> list[SourceFont]:
    """Require resolved, centrally approved Unicode fonts for Unicode ingest."""
    approved_unicode = load_approved_unicode_font_families()
    runs = _text_run_fonts(path)
    for run in runs:
        if run.unresolved_style_references:
            raise UnsupportedSourceFontError(
                "Unicode-only source-font requirement failed: effective font "
                f"could not be resolved at {run.location}; "
                f"{'; '.join(run.unresolved_style_references)}. The document "
                "was not processed."
            )
        if not run.families and run.unresolved_theme_references:
            references = ", ".join(
                f'"{reference}"'
                for reference in run.unresolved_theme_references
            )
            raise UnsupportedSourceFontError(
                "Unicode-only source-font requirement failed: effective font "
                f"could not be resolved at {run.location}; theme font "
                f"reference(s) {references} are not defined by the DOCX theme. "
                "The document was not processed."
            )
        if not run.families:
            raise UnsupportedSourceFontError(
                "Unicode-only source-font requirement failed: effective font "
                f"could not be resolved at {run.location}. The document was "
                "not processed."
            )
        for family in run.families:
            if _normalized(family) not in approved_unicode:
                raise UnsupportedSourceFontError(
                    "Unicode-only source-font requirement failed: font family "
                    f'"{family}" at {run.location} is not an approved Unicode '
                    "font family. APS, unsupported legacy, and other unapproved "
                    "fonts are rejected on unicode-docx-ingest; the document "
                    "was not processed."
                )
    return [
        SourceFont(family, run.part_name)
        for run in runs
        for family in run.families
    ]
