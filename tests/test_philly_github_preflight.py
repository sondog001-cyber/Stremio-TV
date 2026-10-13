import copy
import json
import unittest
from pathlib import Path
from unittest import mock

from research import philly_github_preflight as probe

REGISTRY = json.loads((Path(__file__).resolve().parents[1] / "research" / "philly-github-candidates-2026-10-12.json").read_text())


class PhillyGithubSourceResearchTests(unittest.TestCase):
    def test_five_exact_id_targets_and_all_candidate_urls_safe(self):
        probe.validate_registry(REGISTRY)
        self.assertEqual(tuple(REGISTRY["channels"]), probe.CHANNEL_IDS)
        self.assertEqual(sum(len(x["candidates"]) for x in REGISTRY["channels"].values()), 17)

    def test_not_substituting_news_fast_for_full_local_broadcast(self):
        for item in REGISTRY["channels"].values():
            for entry in item["candidates"]:
                self.assertNotIn("wpvi_24x7_news", entry["url"].lower())
                self.assertNotIn("cbsn-phi", entry["url"].lower())
                self.assertNotIn("nbcphiladelphianews", entry["url"].lower())

    def test_rejects_publicly_leaked_provider_account_urls(self):
        dangerous = [
            "http://provider.example:8080/live/user/password/418.m3u8",
            "https://host.test/api/stream/foo/bar/418",
            "http://10.10.0.1/channel.m3u8",
            "https://user:password@host.test/play.m3u8",
            "https://host.test/live/u%40email.com/xyz/123.m3u8",
        ]
        for url in dangerous:
            data = copy.deepcopy(REGISTRY)
            data["channels"]["KYW.us"]["candidates"][0]["url"] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                probe.validate_registry(data)

    def test_preflight_can_never_approve_or_recover_channel(self):
        fake = {"stage": "progressing-hls-readable-not-decoded", "media_host": "example.com"}
        with mock.patch.object(probe.checks, "load_known_paths", return_value=(set(), set(), set())), mock.patch.object(
            probe.checks, "probe_manifest", return_value=fake
        ):
            result = probe.analyze_station("KYW.us", REGISTRY)
        self.assertEqual(result["candidate_count"], 5)
        self.assertEqual(result["progressing_readable_count"], 5)
        self.assertEqual(result["promotion_count"], 0)
        self.assertEqual(result["decoded_or_approved_count"], 0)
        self.assertTrue(all(not row["production_eligible"] and not row["local_test_eligible"] for row in result["candidates"]))

    def test_known_failed_url_is_skipped_without_network_probe(self):
        blocked = REGISTRY["channels"]["KYW.us"]["candidates"][0]["url"]
        with mock.patch.object(probe.checks, "load_known_paths", return_value=(set(), {blocked}, set())), mock.patch.object(
            probe.checks, "probe_manifest", return_value={"stage": "manifest-or-segment-unavailable"}
        ) as called:
            result = probe.analyze_station("KYW.us", REGISTRY)
        self.assertEqual(result["candidates"][0]["probe"]["stage"], "rejected-by-existing-kill-switch")
        self.assertEqual(called.call_count, 4)

    def test_wpsg_no_public_credentials_no_false_recovery(self):
        with mock.patch.object(probe.checks, "load_known_paths", return_value=(set(), set(), set())), mock.patch.object(
            probe.checks, "probe_manifest"
        ) as called:
            result = probe.analyze_station("WPSG.us", REGISTRY)
        called.assert_not_called()
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["promotion_count"], 0)
        self.assertIn("no eligible", result["no_link_reason"])

    def test_mismatched_station_and_duplicate_candidate_rejected(self):
        missing = copy.deepcopy(REGISTRY)
        del missing["channels"]["WPSG.us"]
        with self.assertRaises(ValueError):
            probe.validate_registry(missing)
        dupe = copy.deepcopy(REGISTRY)
        dupe["channels"]["KYW.us"]["candidates"].append(dupe["channels"]["KYW.us"]["candidates"][0])
        with self.assertRaises(ValueError):
            probe.validate_registry(dupe)


if __name__ == "__main__":
    unittest.main()
