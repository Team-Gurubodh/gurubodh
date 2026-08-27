import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docx import Document

from gurubodh.docx.export import validate_chapter_docx
from gurubodh.lab_proofread import LAB_HEADING_2_PARAGRAPHS, run_lab_proofread
from gurubodh.proofreading import ProofreadingError, ProofreadingSettings
from gurubodh.project import ProjectContext


class FakeProofreader:
    def __init__(self, correction="सही"):
        self.calls = []
        self.correction = correction

    def proofread(self, text, progress=None):
        self.calls.append(text)
        return {
            "corrected_text": text.replace("गलत", self.correction),
            "edits": [
                {"original": "गलत", "corrected": self.correction, "category": "spelling", "reason": "वर्तनी"}
            ] if "गलत" in text else [],
            "estimated_input_tokens": 10,
            "attempts": 1,
            "throttle_seconds": 0.0,
            "usage": {"input_tokens": 10},
        }


class LabProofreadTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.context = ProjectContext(
            root=self.root,
            legacy_converter=Path(__file__).parents[1] / "scripts" / "legacy_font_convert.js",
        )

    def source_docx(self, name="source.docx", text="यह गलत वाक्य है।"):
        path = self.root / name
        document = Document()
        document.add_paragraph(text)
        document.save(path)
        return path

    def test_unicode_run_is_confined_immutable_and_has_validated_artifacts(self):
        source = self.source_docx()
        source_before = source.read_bytes()
        proofreader = FakeProofreader()
        result = run_lab_proofread(self.context, source, "hi-IN", self.root / "lab", proofreader=proofreader)

        run_dir = result["run_directory"]
        self.assertTrue(run_dir.is_relative_to((self.root / "lab").resolve()))
        self.assertRegex(result["run_id"], r"^\d{8}-\d{6}-[a-f0-9]{6}$")
        self.assertEqual(source.read_bytes(), source_before)
        self.assertEqual(len(proofreader.calls), 1)
        manifest = json.loads(result["manifest_path"].read_text(encoding="utf-8"))
        self.assertEqual(manifest["outcome"], "succeeded")
        self.assertTrue(manifest["non_canonical"])
        self.assertEqual(manifest["source"]["sha256"], hashlib.sha256(source_before).hexdigest())
        self.assertEqual(manifest["source"]["font_encoding"], "unicode")
        self.assertEqual(manifest["locale"]["language"], "hi-IN")
        self.assertEqual(manifest["command"]["name"], "lab proofread")
        self.assertTrue((run_dir / "report" / "extracted_source.txt").is_file())
        self.assertTrue((run_dir / "output" / "source_proofread.txt").is_file())
        self.assertTrue((run_dir / "output" / "source_proofread.docx").is_file())
        self.assertTrue((run_dir / "output" / "README.md").is_file())
        self.assertTrue((run_dir / "report" / "proofreading.diff.txt").is_file())
        self.assertTrue((run_dir / "report" / "proofreading_details.json").is_file())
        corrected = (run_dir / "output" / "source_proofread.txt").read_text(encoding="utf-8")
        validate_chapter_docx(run_dir / "output" / "source_proofread.docx", corrected, "source: proofread")
        self.assertEqual(Document(run_dir / "output" / "source_proofread.docx").paragraphs[1].text, "यह सही वाक्य है।")
        self.assertIn("non-canonical", (run_dir / "output" / "README.md").read_text(encoding="utf-8"))
        for relative, expected_sha256 in manifest["artifact_sha256"].items():
            self.assertEqual(hashlib.sha256((run_dir / relative).read_bytes()).hexdigest(), expected_sha256)

    def test_marathi_selects_the_marathi_locale(self):
        source = self.source_docx(text="हे गलत वाक्य आहे.")
        result = run_lab_proofread(self.context, source, "mr-IN", self.root / "lab", proofreader=FakeProofreader("चुकीचे"))
        manifest = json.loads(result["manifest_path"].read_text(encoding="utf-8"))
        self.assertEqual(manifest["locale"]["language"], "mr-IN")
        self.assertEqual(manifest["locale"]["instruction_template"]["id"], "mr-IN-proofreading")

    def test_exact_configured_marathi_paragraphs_render_as_heading_2(self):
        source = self.root / "source.docx"
        document = Document()
        document.add_paragraph("प्रबोधनातील स्मरणीय मुद्दे")
        document.add_paragraph("स्वामी विश्वसंदेश")
        document.add_paragraph("ही सामान्य ओळ आहे।")
        document.save(source)
        result = run_lab_proofread(self.context, source, "mr-IN", self.root / "lab", proofreader=FakeProofreader())
        output = result["run_directory"] / "output"
        corrected = (output / "source_proofread.txt").read_text(encoding="utf-8")
        docx_path = output / "source_proofread.docx"
        validate_chapter_docx(docx_path, corrected, "source: proofread", LAB_HEADING_2_PARAGRAPHS)
        paragraphs = Document(docx_path).paragraphs[1:]
        self.assertEqual([paragraph.style.name for paragraph in paragraphs], ["Heading 2", "Heading 2", "Normal"])

    def test_legacy_font_source_uses_transient_conversion_path(self):
        source = self.source_docx(text="fdn")
        document = Document(source)
        document.paragraphs[0].runs[0].font.name = "APS-DV-Prakash"
        document.save(source)
        proofreader = FakeProofreader()

        def fake_convert(source_path, font_name, converter, output_path, text_path=None, progress=None):
            shutil.copyfile(source_path, output_path)
            return {"converter_counts": {"aps": 1}, "total_nodes": 1, "total_chars": 3}

        with patch("gurubodh.lab_proofread.convert_docx", side_effect=fake_convert) as convert:
            result = run_lab_proofread(self.context, source, "hi-IN", self.root / "lab", proofreader=proofreader)

        convert.assert_called_once()
        manifest = json.loads(result["manifest_path"].read_text(encoding="utf-8"))
        self.assertEqual(manifest["source"]["font_encoding"], "aps")
        self.assertEqual(manifest["source"]["legacy_conversion"]["converter_counts"], {"aps": 1})

    def test_over_limit_fails_before_a_proofreading_request_and_preserves_the_source(self):
        source = self.source_docx(text="बहुत लंबा पाठ")
        before = source.read_bytes()
        proofreader = FakeProofreader()
        with self.assertRaisesRegex(ProofreadingError, "configured proofreading limit"):
            run_lab_proofread(
                self.context,
                source,
                "hi-IN",
                self.root / "lab",
                proofreader=proofreader,
                settings=ProofreadingSettings(max_input_characters=5),
            )
        self.assertEqual(proofreader.calls, [])
        self.assertEqual(source.read_bytes(), before)
        manifests = list((self.root / "lab" / "proofread" / "runs").glob("*/run_manifest.json"))
        self.assertEqual(len(manifests), 1)
        self.assertEqual(json.loads(manifests[0].read_text(encoding="utf-8"))["outcome"], "failed")

    def test_rejects_canonical_lab_root_and_invalid_locale(self):
        source = self.source_docx()
        with self.assertRaisesRegex(ValueError, "cms_library"):
            run_lab_proofread(self.context, source, "hi-IN", self.root / "cms_library")
        with self.assertRaisesRegex(ValueError, "Unsupported language"):
            run_lab_proofread(self.context, source, "en-IN", self.root / "lab")
