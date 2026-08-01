import json
import tempfile
import unittest
from pathlib import Path

from gurubodh.content_identity import build_content_identity
from gurubodh.content_manifest import build_chapter_content_manifest, write_chapter_content_manifest


class ContentManifestTests(unittest.TestCase):
    def test_manifest_is_ordered_and_uses_metadata_artifact_references(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            paths = {"subject": root, "text_and_metadata": root / "chapters" / "text_and_metadata"}
            paths["text_and_metadata"].mkdir(parents=True)
            config = {"naming": {"category_code": "CAT001", "subject_code": "SUB123"}, "metadata_defaults": {"language": "hi-Deva"}}
            for number, text in [(2, "दूसरा"), (1, "पहला")]:
                filename = f"chapter-{number:03d}"
                (paths["text_and_metadata"] / f"{filename}.txt").write_text(text + "\n", encoding="utf-8")
                identity = build_content_identity("CAT001", "SUB123", "hi-Deva", text)
                metadata = {
                    "document": {"category_code": "CAT001", "subject_code": "SUB123", "language": "hi-Deva", "chapter_number": f"{number:03d}"},
                    "files": {"text_filename": f"{filename}.txt"},
                    "content_identity": identity,
                    "storage": {"artifacts": {"metadata": {"backend": "local", "path": f"chapters/text_and_metadata/{filename}.json", "url": None}, "text": {"backend": "local", "path": f"chapters/text_and_metadata/{filename}.txt", "url": None}}},
                }
                (paths["text_and_metadata"] / f"{filename}.json").write_text(json.dumps(metadata), encoding="utf-8")

            manifest = build_chapter_content_manifest(config, paths["text_and_metadata"])
            self.assertEqual([chapter["generated_chapter_number"] for chapter in manifest["chapters"]], ["001", "002"])
            self.assertEqual(
                write_chapter_content_manifest(config, paths),
                root / "chapters" / "chapter_content_manifest.json",
            )


if __name__ == "__main__":
    unittest.main()
