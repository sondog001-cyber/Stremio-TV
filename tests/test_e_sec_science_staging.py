"""Exact-identity staging tests for E!, SEC Network and Science Channel."""
import json
from pathlib import Path
import unittest
import build

EXPECTED = {
    "E.us@East": "https://cache0.wonvt.st/live/15a0cd61f3w7um0229g5g/master.m3u8",
    "SECNetwork.us@SD": "https://cache0.wonvt.st/live/0wvobh902biwzw08m7trv/master.m3u8",
    "ScienceChannel.us": "https://cache0.wonvt.st/live/1qy87o21k84k1r0zek1wt/master.m3u8",
}
class NewBackupQATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=json.loads(Path("config.json").read_text())
        cls.manual=json.loads(Path("manual_sources.json").read_text())["streams"]

    def test_candidates_are_unprivileged_exact_id_and_public_headers_only(self):
        for identity,url in EXPECTED.items():
            with self.subTest(identity=identity):
                rows=[x for x in self.manual if x.get("tvg_id")==identity and x.get("url")==url]
                self.assertEqual(len(rows),1)
                row=rows[0]
                self.assertEqual(row["family"],"tvnow")
                self.assertEqual(row["headers"]["Referer"],"https://tvnow.st/")
                self.assertEqual(row["content_kind"],"full-linear")
                self.assertNotIn("local_verified_override",row)
                self.assertNotIn("local_test_only",row)

    def test_curation_accepts_without_aliasing_other_programme_identites(self):
        wanted=[x for x in self.manual if x.get("url") in EXPECTED.values()]
        canon=build.canonicalize_approved_sources(wanted,self.config)
        curated,rejected=build.curate_entries(canon,self.config)
        self.assertEqual(len(curated),3,f"Rejected: {rejected!r}")
        self.assertEqual({build.canonical_tvg_id(x["tvg_id"]) for x in curated},
                         {"e.us","secnetwork.us","sciencechannel.us"})

    def test_unchanged_full_qa_and_coverage_guard(self):
        self.assertTrue(self.config["stream_health"]["require_passed_only"])
        self.assertTrue(self.config["stream_health"]["primary_playback_qa"]["enabled"])
        self.assertTrue(self.config["deployment_guard"]["enabled"])
        self.assertGreaterEqual(self.config["deployment_guard"]["minimum_channels"],86)

if __name__=="__main__":
    unittest.main()
