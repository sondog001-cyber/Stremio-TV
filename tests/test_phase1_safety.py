import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from failure_report import issue_body

ROOT = Path(__file__).resolve().parent.parent


class Phase1SafetyTests(unittest.TestCase):
    def test_missing_build_parts_refuses_assembly(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "assemble_build.py").write_text((ROOT / "assemble_build.py").read_text())
            (directory / "build_parts").mkdir()
            (directory / "build_parts" / "part01.txt").write_text("print('partial')")
            result = subprocess.run([sys.executable, str(directory / "assemble_build.py")], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((directory / "build.py").exists())

    def test_missing_parts_preserves_preexisting_builder(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "assemble_build.py").write_text((ROOT / "assemble_build.py").read_text())
            (directory / "build_parts").mkdir()
            (directory / "build.py").write_text("known-good")
            result = subprocess.run([sys.executable, str(directory / "assemble_build.py")], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((directory / "build.py").read_text(), "known-good")

    def test_failed_guard_prevents_pages_upload(self):
        workflow = (ROOT / ".github/workflows/build-and-deploy.yml").read_text()
        self.assertLess(workflow.index("Guard against channel coverage"), workflow.index("Upload Pages artifact"))
        self.assertIn("needs: build", workflow)

    def test_issue_report_never_contains_secrets(self):
        secret = "ghp_SUPER_SECRET_EXAMPLE"
        with patch.dict("os.environ", {"GITHUB_TOKEN": secret, "STREAM_PASSWORD": secret}):
            report = issue_body("https://github.com/owner/repo/actions/runs/123")
        self.assertNotIn(secret, report)
        self.assertNotIn("STREAM_PASSWORD", report)
        self.assertNotIn("GITHUB_TOKEN", report)
        self.assertEqual(issue_body("https://example.com/?token=" + secret), "A deployment failed. Inspect the Actions page for this repository.")


if __name__ == "__main__":
    unittest.main()
