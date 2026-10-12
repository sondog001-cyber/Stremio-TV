import unittest

import build


class JointSourceHuntQueueTests(unittest.TestCase):
    def test_single_provider_backup_and_recent_loss_share_prioritized_queue(self):
        redundancy = {"channels": [
            {
                "tvg_id": "FoxSports2.us", "stream_count": 1,
                "provider_hosts": ["wonvt.st"], "provider_families": ["tvnow"],
                "has_independent_backup": False,
            },
            {
                "tvg_id": "TwoProviders.us", "stream_count": 2,
                "provider_hosts": ["a.test", "b.test"],
                "has_independent_backup": True,
            },
        ]}
        missing = {"channels": [
            {"tvg_id": "DisneyChannel.us", "bucket": "runner_or_geo_blocked",
             "group": "National", "candidate_count": 3, "public_search_eligible": True},
            {"tvg_id": "KYW.us", "bucket": "failed_probes", "group": "Philadelphia",
             "candidate_count": 2, "public_search_eligible": True},
            {"tvg_id": "WPSG.us", "bucket": "private_connector_required",
             "group": "Philadelphia", "candidate_count": 0, "public_search_eligible": False},
            {"tvg_id": "AlreadyGood.us", "bucket": "complete",
             "group": "National", "candidate_count": 2, "public_search_eligible": True},
        ]}
        reliability = {
            "independent_backup_priorities": [
                {"tvg_id": "FoxSports2.us", "priority_score": 90,
                 "locally_verified": True},
                {"tvg_id": "TwoProviders.us", "priority_score": 99},
            ],
            "recovery_priorities": [
                {"tvg_id": "DisneyChannel.us", "recent_losses": 1},
            ],
        }
        report = build.build_resilience_hunt_queue(redundancy, missing, reliability)
        self.assertEqual(report["summary"]["backup_targets"], 1)
        self.assertEqual(report["summary"]["missing_targets"], 2)
        self.assertEqual(report["summary"]["private_connector_excluded"], 1)
        self.assertEqual(report["summary"]["total_targets"], 3)
        self.assertEqual(report["queue"][0]["tvg_id"], "DisneyChannel.us")
        indexed = {row["tvg_id"]: row for row in report["queue"]}
        self.assertNotIn("WPSG.us", indexed)
        self.assertNotIn("AlreadyGood.us", indexed)
        self.assertNotIn("TwoProviders.us", indexed)
        self.assertEqual(indexed["FoxSports2.us"]["avoid_existing_upstream_hosts"], ["wonvt.st"])
        self.assertTrue(indexed["FoxSports2.us"]["has_local_override"])
        self.assertTrue(all(row["requires_normal_qa_before_publishing"] for row in report["queue"]))

    def test_cooldown_and_geo_block_have_different_search_modes(self):
        report = build.build_resilience_hunt_queue(
            {"channels": []},
            {"channels": [
                {"tvg_id": "CNBC.us", "bucket": "quarantined_or_cooldown", "candidate_count": 12},
                {"tvg_id": "ESPN.us", "bucket": "runner_or_geo_blocked", "candidate_count": 9},
            ]},
            {"independent_backup_priorities": [], "recovery_priorities": []},
        )
        items = {row["tvg_id"]: row for row in report["queue"]}
        self.assertEqual(items["CNBC.us"]["search_mode"], "wait_for_cooldown_or_new_independent_source")
        self.assertEqual(items["ESPN.us"]["search_mode"], "local_runner_comparison_or_authorized_alternative")


if __name__ == "__main__":
    unittest.main()
