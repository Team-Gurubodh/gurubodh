import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gurubodh.audit import resolved_build_provenance


class BuildProvenanceTests(unittest.TestCase):
    def test_embedded_manifest_takes_precedence_over_git_checkout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "build-provenance.json"
            manifest.write_text(
                json.dumps(
                    {
                        "source_revision": "a" * 40,
                        "image_revision": "a" * 40,
                        "image_version": "sha-" + "a" * 40,
                        "image_created": "2026-08-19T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"GURUBODH_BUILD_PROVENANCE_FILE": str(manifest)}), patch(
                "gurubodh.audit.git_commit_sha", return_value="b" * 40
            ) as git_commit:
                provenance = resolved_build_provenance(Path(temp_dir))

        self.assertEqual(provenance["source"], "embedded-container-manifest")
        self.assertEqual(provenance["source_revision"], "a" * 40)
        git_commit.assert_not_called()

    def test_native_git_checkout_is_used_when_manifest_is_unavailable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.json"
            with patch.dict("os.environ", {"GURUBODH_BUILD_PROVENANCE_FILE": str(missing)}), patch(
                "gurubodh.audit.git_commit_sha", return_value="b" * 40
            ):
                provenance = resolved_build_provenance(Path(temp_dir))

        self.assertEqual(provenance["source"], "native-git-checkout")
        self.assertEqual(provenance["source_revision"], "b" * 40)

    def test_missing_manifest_and_git_commit_are_reported_as_unavailable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"GURUBODH_BUILD_PROVENANCE_FILE": str(Path(temp_dir) / "missing.json")}), patch(
                "gurubodh.audit.git_commit_sha", return_value=None
            ):
                provenance = resolved_build_provenance(Path(temp_dir))

        self.assertEqual(provenance["source"], "unavailable")
        self.assertIsNone(provenance["source_revision"])
