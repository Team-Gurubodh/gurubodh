import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gurubodh.project import resolve_project_context


class ProjectContextTests(unittest.TestCase):
    def make_project_root(self):
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        (root / "config" / "jobs").mkdir(parents=True)
        (root / "config" / "jobs" / "prep_subject_job.schema.json").write_text("{}", encoding="utf-8")
        (root / "jobs" / "subjects").mkdir(parents=True)
        self.addCleanup(temp_dir.cleanup)
        return root

    def test_resolves_project_root_from_cli_env_var(self):
        root = self.make_project_root()

        with patch.dict(os.environ, {"GURUBODH_CLI_ROOT": str(root)}, clear=False):
            context = resolve_project_context()

        self.assertEqual(context.root, root.resolve())

    def test_missing_project_root_message_mentions_cli_env_var(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {}, clear=True), patch("pathlib.Path.cwd", return_value=Path(temp_dir)):
                with self.assertRaises(SystemExit) as exc:
                    resolve_project_context()

        message = str(exc.exception)
        old_env_name = "_".join(("GURUBODH", "CONTENT", "ROOT"))

        self.assertIn("GURUBODH_CLI_ROOT", message)
        self.assertNotIn(old_env_name, message)


if __name__ == "__main__":
    unittest.main()
