"""Ensure three recovery streams remain exact-ID QA candidates, never shortcuts."""
import json
from pathlib import Path
import unittest

import build


class IndependentRecoveryStagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(Path("config.json").read_text())
        cls.manual = json.loads(Path("manual_sources.json").read_text())["streams"]

    def test_exact_candidate_identifiers_and_source_urls(self):
        expected = {
            "BigTenNetwork.us@SD": "https://cache0.wonvt.st/live/12ttivn0fhm14f0yr8ber/master.m3u8",
            "OneAmericaNewsNetwork.us@SD": "https://a-cdn.klowdtv.com/live1/oan_720p/playlist.m3u8",
            "History.us@East": "https://tvsen5.aynascope.net/historyen/index.m3u8",
        }
        for tvg_id, url in expected.items():
            with self.subTest(tvg_id=tvg_id):
                entries = [x for x in self.manual if x.get("tvg_id")==tvg_id and x.get("url")==url]
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0].get("content_kind"), "full-linear")
                self.assertNotIn("local_verified_override", entries[0])
                self.assertFalse(entries[0].get("local_test_only", False))
                self.assertEqual(build.canonical_tvg_id(tvg_id), build.canonical_tvg_id(tvg_id.split("@")[0]))

    def test_all_candidates_survive_exact_identity_curation_without_cross_network_mapping(self):
        streams = [x for x in self.manual if x.get("family") in {"klowdtv", "tvnow"} and
                   x.get("tvg_id") in {"OneAmericaNewsNetwork.us@SD", "BigTenNetwork.us@SD"}]
        streams += [x for x in self.manual if x.get("tvg_id")=="History.us@East" and
                    "aynascope.net/historyen/" in x.get("url", "")]
        canonical = build.canonicalize_approved_sources(streams, self.config)
        curated, rejected = build.curate_entries(canonical, self.config)
        self.assertEqual(len(curated), 3, f"Rejected wanted streams: {rejected!r}")
        self.assertEqual(len(rejected), 0)
        self.assertEqual(
            {build.canonical_tvg_id(x["tvg_id"]) for x in curated},
            {"bigtennetwork.us", "oneamericanewsnetwork.us", "history.us"},
        )

    def test_normal_deployment_guard_remains_enabled(self):
        self.assertTrue(self.config["stream_health"]["require_passed_only"])
        self.assertTrue(self.config["stream_health"]["primary_playback_qa"]["enabled"])
        self.assertTrue(self.config["deployment_guard"]["enabled"])
        self.assertGreaterEqual(self.config["deployment_guard"]["minimum_channels"], 86)
        self.assertIn("History.us", self.config["deployment_guard"]["required_channel_ids"])


if __name__ == "__main__":
    unittest.main()
