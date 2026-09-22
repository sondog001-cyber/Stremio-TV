import unittest

import build


class MissingSourceDiagnosticsTests(unittest.TestCase):
    def test_actionable_buckets_separate_absent_blocked_failed_and_quality(self):
        candidate = [
            {"group": "National", "pattern": "None.us", "candidate_count": 0, "sources": []},
            {"group": "National", "pattern": "Blocked.us", "candidate_count": 1, "sources": ["A"]},
            {"group": "National", "pattern": "Failed.us", "candidate_count": 1, "sources": ["B"]},
            {"group": "National", "pattern": "Unknown.us", "candidate_count": 1, "sources": ["C"]},
        ]
        passing = [
            {"pattern": "None.us", "candidate_count": 0},
            {"pattern": "Blocked.us", "candidate_count": 0},
            {"pattern": "Failed.us", "candidate_count": 0},
            {"pattern": "Unknown.us", "candidate_count": 1},
        ]
        health = [
            {"tvg_id": "Blocked.us", "health": {"status": "failed", "detail": "HTTP 403"}},
            {"tvg_id": "Failed.us", "health": {"status": "failed", "detail": "Invalid playlist"}},
            {"tvg_id": "Unknown.us", "health": {"status": "ok"}},
        ]
        channels = [
            {"tvg_id": "Unknown.us", "streams": [{"url": "https://example.test/u.m3u8"}]}
        ]
        report = build.build_missing_source_diagnostics(
            candidate,
            passing,
            health,
            channels,
            {"stream_selection": {"target_hd": 2, "target_sd": 1}},
        )
        buckets = {row["tvg_id"]: row["bucket"] for row in report["channels"]}
        self.assertEqual(buckets["None.us"], "no_candidate")
        self.assertEqual(buckets["Blocked.us"], "runner_or_geo_blocked")
        self.assertEqual(buckets["Failed.us"], "failed_probes")
        self.assertEqual(buckets["Unknown.us"], "missing_quality_metadata")


if __name__ == "__main__":
    unittest.main()
