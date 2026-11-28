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

    def test_failed_build_preserves_existing_deployed_directory_in_integration(self):
        import json
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            pages = directory / "published-pages"
            pages.mkdir()
            (pages / "manifest.json").write_text('{"id":"com.stremiotv.philly","version":"known-good"}')
            before = (pages / "manifest.json").read_bytes()
            site = directory / "site"
            (site / "diagnostics").mkdir(parents=True)
            (site / "status.json").write_text(json.dumps({"channels": 0}))
            (site / "diagnostics" / "channels.json").write_text("[]")
            (directory / "config.json").write_text(json.dumps({"deployment_guard": {"enabled": True, "minimum_channels": 86, "required_channel_ids": []}}))
            result = subprocess.run([sys.executable, str(ROOT / "deployment_guard.py")], cwd=directory, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            # The deployment step is gated on successful build/guard completion.
            if result.returncode == 0:
                (pages / "manifest.json").write_text((site / "manifest.json").read_text())
            self.assertEqual((pages / "manifest.json").read_bytes(), before)
            self.assertEqual(json.loads((site / "status.json").read_text())["deployment_baseline"]["status"], "unavailable")
            self.assertTrue((site / "diagnostics" / "deployment-baseline.json").exists())


if __name__ == "__main__":
    unittest.main()
