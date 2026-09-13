import tempfile
import unittest
import zipfile
from pathlib import Path

from docx import Document

from gurubodh.legacy.font_detection import (
    UnsupportedSourceFontError,
    source_fonts,
    validate_supported_source_fonts,
    validate_unicode_source_fonts,
)


def _part_xml(text, font_name):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<w:root xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p><w:r><w:rPr><w:rFonts w:ascii="{font_name}" /></w:rPr><w:t>{text}</w:t></w:r></w:p>
</w:root>'''


def _run_xml(text, font_attributes=""):
    rpr = f"<w:rPr><w:rFonts {font_attributes} /></w:rPr>" if font_attributes else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:root xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:p><w:r>{rpr}<w:t>{text}</w:t></w:r></w:p></w:root>"
    )


class SourceFontPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def source_docx(self, font_name="Mangal"):
        path = self.root / "source.docx"
        document = Document()
        run = document.add_paragraph("परीक्षण").runs[0]
        run.font.name = font_name
        document.save(path)
        return path

    def test_rejects_shreelipi_before_processing(self):
        path = self.source_docx("SHREE-DEV7-0708")

        with self.assertRaisesRegex(UnsupportedSourceFontError, "ShreeLipi/Sri-Lipi conversion is disabled"):
            validate_supported_source_fonts(path)

    def test_rejects_unapproved_font_family(self):
        path = self.source_docx("Unknown Legacy Family")

        with self.assertRaisesRegex(UnsupportedSourceFontError, '"Unknown Legacy Family"'):
            validate_supported_source_fonts(path)

    def test_accepts_approved_unicode_and_aps_families(self):
        for font_name in ("Mangal", "APS-DV-Prakash"):
            with self.subTest(font_name=font_name):
                validate_supported_source_fonts(self.source_docx(font_name))

    def test_rejects_font_in_an_inherited_paragraph_style(self):
        path = self.root / "styled.docx"
        document = Document()
        style = document.styles.add_style("UnsafeLegacy", 1)
        style.font.name = "ShreeLipi"
        document.add_paragraph("परीक्षण", style="UnsafeLegacy")
        document.save(path)

        with self.assertRaisesRegex(UnsupportedSourceFontError, '"ShreeLipi"'):
            validate_supported_source_fonts(path)

    def test_rejects_font_in_document_defaults(self):
        path = self.root / "default-font.docx"
        document_xml = _part_xml("परीक्षण", "")
        document_xml = document_xml.replace('<w:rPr><w:rFonts w:ascii="" /></w:rPr>', "")
        styles_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="ShreeLipi" /></w:rPr></w:rPrDefault></w:docDefaults>
</w:styles>'''
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr("word/document.xml", document_xml)
            package.writestr("word/styles.xml", styles_xml)

        with self.assertRaisesRegex(UnsupportedSourceFontError, '"ShreeLipi"'):
            validate_supported_source_fonts(path)

    def test_scans_every_text_bearing_docx_part(self):
        path = self.source_docx("Mangal")
        document = Document(path)
        for section in document.sections:
            for container in (section.header, section.footer):
                run = container.paragraphs[0].add_run("परीक्षण")
                run.font.name = "Mangal"
        document.save(path)
        with zipfile.ZipFile(path, "a", compression=zipfile.ZIP_DEFLATED) as package:
            for part_name in ("word/footnotes.xml", "word/endnotes.xml", "word/comments.xml"):
                package.writestr(part_name, _part_xml("परीक्षण", "Mangal"))

        fonts = source_fonts(path)

        self.assertTrue(
            {
                "word/document.xml",
                "word/header1.xml",
                "word/footer1.xml",
                "word/footnotes.xml",
                "word/endnotes.xml",
                "word/comments.xml",
            }.issubset({font.part_name for font in fonts})
        )
        validate_supported_source_fonts(path)

    def test_unicode_route_accepts_one_or_multiple_approved_families(self):
        path = self.root / "approved.docx"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr(
                "word/document.xml",
                _run_xml(
                    "परीक्षण",
                    'w:ascii="Mangal" w:hAnsi="Nirmala UI" w:eastAsia="Mangal"',
                ),
            )

        fonts = validate_unicode_source_fonts(path)

        self.assertEqual({font.family for font in fonts}, {"Mangal", "Nirmala UI"})

    def test_unicode_route_rejects_every_non_unicode_font_kind_with_location(self):
        for family in (
            "APS-DV-Prakash",
            "SHREE-DEV7-0708",
            "Unknown Legacy Family",
        ):
            with self.subTest(family=family):
                path = self.source_docx(family)
                with self.assertRaises(UnsupportedSourceFontError) as raised:
                    validate_unicode_source_fonts(path)
                message = str(raised.exception)
                self.assertIn("Unicode-only source-font requirement", message)
                self.assertIn(f'"{family}"', message)
                self.assertIn('DOCX part "word/document.xml"', message)
                self.assertIn("paragraph 1, run 1", message)

    def test_unicode_route_rejects_mixed_aps_and_unicode_runs(self):
        path = self.root / "mixed.docx"
        document = Document()
        paragraph = document.add_paragraph()
        paragraph.add_run("यूनिकोड").font.name = "Mangal"
        paragraph.add_run("legacy").font.name = "APS-DV-Prakash"
        document.save(path)

        with self.assertRaisesRegex(
            UnsupportedSourceFontError,
            r'APS-DV-Prakash.*word/document\.xml.*run 2',
        ):
            validate_unicode_source_fonts(path)

    def test_unicode_route_rejects_unresolved_font_location(self):
        path = self.root / "unresolved.docx"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr("word/document.xml", _run_xml("परीक्षण"))

        with self.assertRaises(UnsupportedSourceFontError) as raised:
            validate_unicode_source_fonts(path)

        message = str(raised.exception)
        self.assertIn("Unicode-only source-font requirement", message)
        self.assertIn("could not be resolved", message)
        self.assertIn('DOCX part "word/document.xml", paragraph 1, run 1', message)

    def test_unicode_route_resolves_inherited_character_and_paragraph_styles(self):
        path = self.root / "inherited.docx"
        document_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:pPr><w:pStyle w:val="ApprovedParagraph" /></w:pPr>
    <w:r><w:rPr><w:rStyle w:val="UnsafeCharacter" /></w:rPr><w:t>परीक्षण</w:t></w:r>
  </w:p></w:body>
</w:document>'''
        styles_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="ApprovedBase"><w:rPr><w:rFonts w:ascii="Mangal" /></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="ApprovedParagraph"><w:basedOn w:val="ApprovedBase" /></w:style>
  <w:style w:type="character" w:styleId="UnsafeBase"><w:rPr><w:rFonts w:hAnsi="APS-DV-Prakash" /></w:rPr></w:style>
  <w:style w:type="character" w:styleId="UnsafeCharacter"><w:basedOn w:val="UnsafeBase" /></w:style>
</w:styles>'''
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr("word/document.xml", document_xml)
            package.writestr("word/styles.xml", styles_xml)

        with self.assertRaisesRegex(UnsupportedSourceFontError, "APS-DV-Prakash"):
            validate_unicode_source_fonts(path)

    def test_unicode_route_resolves_theme_fonts_and_rejects_missing_theme_mapping(self):
        theme_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <a:themeElements><a:fontScheme name="Test">
    <a:majorFont><a:latin typeface="Mangal" /><a:ea typeface="" /><a:cs typeface="" /></a:majorFont>
    <a:minorFont><a:latin typeface="APS-DV-Prakash" /><a:ea typeface="" /><a:cs typeface="" /></a:minorFont>
  </a:fontScheme></a:themeElements>
</a:theme>'''
        path = self.root / "theme.docx"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr(
                "word/document.xml",
                _run_xml("परीक्षण", 'w:asciiTheme="minorAscii"'),
            )
            package.writestr("word/theme/theme1.xml", theme_xml)

        with self.assertRaisesRegex(UnsupportedSourceFontError, "APS-DV-Prakash"):
            validate_unicode_source_fonts(path)

        approved = self.root / "approved-theme.docx"
        with zipfile.ZipFile(approved, "w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr(
                "word/document.xml",
                _run_xml("परीक्षण", 'w:asciiTheme="majorAscii"'),
            )
            package.writestr("word/theme/theme1.xml", theme_xml)
        self.assertEqual(
            [font.family for font in validate_unicode_source_fonts(approved)],
            ["Mangal"],
        )

        missing = self.root / "missing-theme.docx"
        with zipfile.ZipFile(missing, "w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr(
                "word/document.xml",
                _run_xml("परीक्षण", 'w:asciiTheme="majorAscii"'),
            )
        with self.assertRaisesRegex(
            UnsupportedSourceFontError,
            r'theme font reference\(s\) "majorAscii".*not defined',
        ):
            validate_unicode_source_fonts(missing)

    def test_unicode_route_rejects_unsafe_font_in_non_body_part(self):
        path = self.root / "comments.docx"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr("word/document.xml", _part_xml("परीक्षण", "Mangal"))
            package.writestr(
                "word/comments.xml", _part_xml("legacy", "APS-DV-Prakash")
            )

        with self.assertRaisesRegex(
            UnsupportedSourceFontError,
            r'APS-DV-Prakash.*word/comments\.xml',
        ):
            validate_unicode_source_fonts(path)
