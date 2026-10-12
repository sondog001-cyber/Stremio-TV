import unittest

from reliability_watchdog import evaluate, markdown_summary


def inputs(published=88, previous=86, overridden=16, single=58):
    status = {
        "build_id": "current",
        "built_at": "2026-10-12T15:00:00Z",
        "channels": published,
        "epg_unmatched_channels": 6,
        "primary_playback_qa": {"channels_tested": published, "primary_passed": published},
        "missing_source_buckets": {"expected_channels": 111},
    }
    ids = [f"Channel{i}.us" for i in range(published)]
    old_ids = [f"Channel{i}.us" for i in range(previous)]
    reliability = {
        "summary": {
            "normal_decoder_passes_latest": max(0, published - overridden),
            "locally_overridden_playback_attempts_latest": overridden,
            "five_build_history_complete": True,
        },
        "history": [
            {"build_id": "previous", "published": previous, "published_tvg_ids": old_ids},
            {"build_id": "current", "published": published, "published_tvg_ids": ids},
        ],
    }
    redundancy = {"summary": {"single_stream": single, "with_independent_backup": 27}}
    hunt = {
        "host_concentration": [{"host": "provider.test", "published_channels": 26}],
        "top_10": [{"tvg_id": "Example.us", "kind": "independent_backup"}],
    }
    return status, reliability, redundancy, hunt


class ReadOnlyWatchdogTests(unittest.TestCase):
    def test_baseline_counts_are_separate_and_read_only(self):
        data = inputs()
        report = evaluate(*data)
        summary = report["summary"]
        self.assertEqual(summary["published"], 88)
        self.assertEqual(summary["previous_published"], 86)
        self.assertEqual(summary["normal_decoder_passes"], 72)
        self.assertEqual(summary["local_override_attempts"], 16)
        self.assertEqual(summary["final_qa_reported_passes"], 88)
        self.assertTrue(report["advisory_only"])
        self.assertNotIn("coverage_regression", [a["code"] for a in report["alerts"]])
        self.assertEqual(report["next_hunt_targets"][0]["tvg_id"], "Example.us")
        self.assertIn("Normal decoder passes and local overrides", markdown_summary(report))

    def test_large_coverage_regression_is_advisory_not_release_blocker(self):
        data = inputs(published=75, previous=90, overridden=0, single=35)
        report = evaluate(*data)
        self.assertEqual(report["summary"]["coverage_drop"], 15)
        self.assertEqual(report["summary"]["coverage_drop_alert_threshold"], 8)
        self.assertIn("coverage_regression", [a["code"] for a in report["alerts"]])
        self.assertTrue(report["does_not_change_qa_or_publication"])

    def test_small_decline_is_not_a_catastrophic_alert(self):
        data = inputs(published=84, previous=88, overridden=0, single=35)
        report = evaluate(*data)
        self.assertNotIn("coverage_regression", [a["code"] for a in report["alerts"]])

    def test_first_build_without_history_does_not_create_false_decline(self):
        status, reliability, redundancy, hunt = inputs()
        reliability["history"] = [{"build_id": "current", "published": 88}]
        report = evaluate(status, reliability, redundancy, hunt)
        self.assertIsNone(report["summary"]["previous_published"])
        self.assertIsNone(report["summary"]["coverage_drop"])

    def test_stale_history_must_not_be_used_for_regression_alert(self):
        status, reliability, redundancy, hunt = inputs()
        reliability["history"] = [{"build_id": "old", "published": 120}]
        report = evaluate(status, reliability, redundancy, hunt)
        self.assertIsNone(report["summary"]["coverage_drop"])

    def test_empty_diagnostics_do_not_crash(self):
        report = evaluate({}, {}, {}, {})
        self.assertEqual(report["summary"]["published"], 0)
        self.assertEqual(report["alerts"], [])


if __name__ == "__main__":
    unittest.main()
