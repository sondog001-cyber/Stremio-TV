"""Guard against scheduled jobs preempting active Pages deployment attempts.

This only checks the workflow wiring; production coverage/identity guard
remains the authority on whether to publish a new curated lineup.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build-and-deploy.yml"


class BuildConcurrencyTests(unittest.TestCase):
    def test_scheduled_build_never_cancels_active_pages_run(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        match = re.search(
            r"(?m)^concurrency:\s*\n"
            r"\s{2}group:\s*pages\s*\n"
            r"\s{2}cancel-in-progress:\s*(true|false)\s*$",
            content,
        )
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "false")

    def test_scheduled_cadence_and_deployment_guard_unchanged(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "7 */2 * * *"', content)
        self.assertIn("run: python deployment_guard.py", content)
        self.assertIn("needs: build", content)
        self.assertIn("run: python build.py", content)


if __name__ == "__main__":
    unittest.main()
