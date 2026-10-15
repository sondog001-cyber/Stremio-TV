import copy
import unittest

import build


class ChannelReadinessTests(unittest.TestCase):
    def setUp(self):
        self.config = {"curation": {"national_allow": ["Example.us", "Missing.us"], "philly_allow": ["Fox.us@WTXFTV"]}}
        self.channels = [{"tvg_id": "Example.us", "streams": [
            {"url": "https://a.example/live", "tvg_id": "Example.us", "family": "one"},
            {"url": "https://b.example/live", "tvg_id": "Example.us", "family": "two"}]}]
        self.health = [{"tvg_id": "Example.us", "url": "https://a.example/live", "health": {"status": "ok"}}]
        self.qa = {"built_at": "2026-10-15T02:00:00Z", "channels": [{"tvg_id": "Example.us", "attempts": [
            {"url": "https://a.example/live", "status": "ok", "qa": {"passed": True, "attempts": [
                {"passed": True, "decoded_frames": 20, "decoded_seconds": 10, "repeat": None}]}}]}]}

    def report(self):
        return build.build_channel_readiness_diagnostics(self.channels, self.health, self.qa, {}, {}, {}, self.config, {})

    def test_all_curated_rows_present_and_untested_backups_never_gain_qa_or_independence(self):
        report = self.report()
        self.assertEqual(report["summary"]["curated"], 3)
        self.assertEqual(report["summary"]["missing"], 2)
        self.assertEqual(report["summary"]["normal_primary_qa_passed"], 1)
        row = next(r for r in report["channels"] if r["tvg_id"] == "Example.us")
        self.assertTrue(row["different_host_backup_observed"])
        self.assertIsNone(row["genuine_independent_backup_verified"])
        self.assertEqual(row["backups"][0]["decoder_status"], "not-tested")
        self.assertFalse(row["backups"][0]["normal_full_qa_passed"])

    def test_local_override_preserves_error_and_is_excluded_from_normal_passes(self):
        a = self.qa["channels"][0]["attempts"][0]
        a["qa"] = {"passed": True, "local_verified_override": True, "ci_playback_status": "failed",
                   "ci_playback_detail": "Decoder timeout", "ci_continuity_failure": "direct-media-insufficient-survival",
                   "ci_direct_media_survival": {"passed": False, "attempts": [{"decoded_frames": 0}]}}
        report = self.report()
        self.assertEqual(report["summary"]["normal_primary_qa_passed"], 0)
        self.assertEqual(report["summary"]["local_primary_overrides"], 1)
        primary = next(r for r in report["channels"] if r["tvg_id"] == "Example.us")["primary"]
        self.assertEqual(primary["underlying_ci_detail"], "Decoder timeout")
        self.assertEqual(primary["decoded_attempts"][0]["decoded_frames"], 0)
        self.assertIsNone(primary["last_successful_normal_validation"])

    def test_other_affiliate_and_west_variant_cannot_supply_curated_rows(self):
        self.channels += [{"tvg_id": "Fox.us@WNYW", "streams": []}]
        self.channels[0]["tvg_id"] = "Example.us@West"
        self.assertEqual(self.report()["summary"]["published"], 0)

    def test_inputs_unchanged_and_false_aggregate_pass_cannot_supply_frame_evidence(self):
        before = copy.deepcopy((self.channels, self.health, self.qa))
        self.report()
        self.assertEqual(before, (self.channels, self.health, self.qa))
        self.qa["channels"][0]["attempts"][0]["qa"]["attempts"][0]["decoded_frames"] = 0
        self.assertEqual(self.report()["summary"]["normal_primary_qa_passed"], 0)


if __name__ == "__main__":
    unittest.main()
