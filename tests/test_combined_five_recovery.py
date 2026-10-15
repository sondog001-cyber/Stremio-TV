"""Verify the five-source staging is exact-ID, isolated and never QA-bypassed."""
import json
from pathlib import Path
import unittest
import build

EXPECTED = {
    "BigTenNetwork.us@SD": "https://cache0.wonvt.st/live/12ttivn0fhm14f0yr8ber/master.m3u8",
    "OneAmericaNewsNetwork.us@SD": "https://a-cdn.klowdtv.com/live1/oan_720p/playlist.m3u8",
    "History.us@East": "https://tvsen5.aynascope.net/historyen/index.m3u8",
    "SECNetwork.us@SD": "https://cache0.wonvt.st/live/0wvobh902biwzw08m7trv/master.m3u8",
    "ScienceChannel.us": "https://cache0.wonvt.st/live/1qy87o21k84k1r0zek1wt/master.m3u8",
}

class CombinedFiveRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(Path("config.json").read_text())
        cls.streams = json.loads(Path("manual_sources.json").read_text())["streams"]

    def test_five_sources_are_present_without_bypass(self):
        for identity, url in EXPECTED.items():
            with self.subTest(identity=identity):
                matches = [s for s in self.streams if s.get("tvg_id") == identity and s.get("url") == url]
                self.assertEqual(len(matches), 1)
                row = matches[0]
                self.assertEqual(row.get("content_kind"), "full-linear")
                self.assertNotIn("local_verified_override", row)
                self.assertFalse(row.get("local_test_only", False))
                self.assertEqual(build.canonical_tvg_id(identity), build.canonical_tvg_id(identity.split("@")[0]))

    def test_failing_candidates_are_not_staged(self):
        for identity in ("CookingChannel.us@SD", "E.us@East"):
            self.assertFalse(any(s.get("tvg_id") == identity and (
                s.get("url") in {
                    "https://tvsen7.aynascope.net/cooking/index.m3u8",
                    "https://cache0.wonvt.st/live/15a0cd61f3w7um0229g5g/master.m3u8"
                }) for s in self.streams))

    def test_all_five_survive_curation(self):
        wanted = [s for s in self.streams if s.get("url") in EXPECTED.values()]
        self.assertEqual(len(wanted), 5)
        canonical = build.canonicalize_approved_sources(wanted, self.config)
        curated, rejected = build.curate_entries(canonical, self.config)
        self.assertEqual(len(curated), 5, f"Rejected wanted streams: {rejected!r}")
        self.assertEqual(len(rejected), 0)

    def test_guards_stay_strict(self):
        self.assertTrue(self.config["stream_health"]["require_passed_only"])
        self.assertTrue(self.config["stream_health"]["primary_playback_qa"]["enabled"])
        self.assertTrue(self.config["deployment_guard"]["enabled"])
        self.assertGreaterEqual(self.config["deployment_guard"]["minimum_channels"], 86)

if __name__ == "__main__":
    unittest.main()
