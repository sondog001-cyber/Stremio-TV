import unittest

import build


class MissingSourceDiagnosticsTests(unittest.TestCase):
    def test_actionable_buckets_separate_absent_blocked_failed_and_quality(self):
        candidate = [
            {"group": "National", "pattern": "None.us", "candidate_count": 0, "sources": []},
            {"group": "National", "pattern": "Blocked.us", "candidate_count": 1, "sources": ["A"]},
            {"group": "National", "pattern": "Failed.us", "candidate_count": 1, "sources": ["B"]},
            {"group": "National", "pattern": "Unknown.us", "candidate_count": 1, "sources": ["C"]},
            {"group": "Local", "pattern": "Private.us", "candidate_count": 0, "sources": []},
            {"group": "National", "pattern": "Cooldown.us", "candidate_count": 1, "sources": ["D"]},
        ]
        passing = [
            {"pattern": "None.us", "candidate_count": 0},
            {"pattern": "Blocked.us", "candidate_count": 0},
            {"pattern": "Failed.us", "candidate_count": 0},
            {"pattern": "Unknown.us", "candidate_count": 1},
            {"pattern": "Private.us", "candidate_count": 0},
            {"pattern": "Cooldown.us", "candidate_count": 0},
        ]
        health = [
            {"tvg_id": "Blocked.us", "health": {"status": "failed", "detail": "HTTP 403"}},
            {"tvg_id": "Failed.us", "health": {"status": "failed", "detail": "Invalid playlist"}},
            {"tvg_id": "Unknown.us", "health": {"status": "ok"}},
            {"tvg_id": "Cooldown.us", "health": {"status": "cooldown"}},
        ]
        channels = [
            {"tvg_id": "Unknown.us", "streams": [{"url": "https://example.test/u.m3u8"}]}
        ]
        report = build.build_missing_source_diagnostics(
            candidate,
            passing,
            health,
            channels,
            {
                "stream_selection": {"target_hd": 2, "target_sd": 1},
                "discovery": {"public_search_policy": {"private_connector_only_ids": ["Private.us"]}},
            },
        )
        buckets = {row["tvg_id"]: row["bucket"] for row in report["channels"]}
        self.assertEqual(buckets["None.us"], "no_candidate")
        self.assertEqual(buckets["Blocked.us"], "runner_or_geo_blocked")
        self.assertEqual(buckets["Failed.us"], "failed_probes")
        self.assertEqual(buckets["Unknown.us"], "missing_quality_metadata")
        self.assertEqual(buckets["Private.us"], "private_connector_required")
        self.assertEqual(buckets["Cooldown.us"], "quarantined_or_cooldown")


if __name__ == "__main__":
    unittest.main()
