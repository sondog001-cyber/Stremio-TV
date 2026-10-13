"""MS NOW: previously controlled Local Test is now user-confirmed production source.

Ten minutes of successful local Stremio playback plus 3x60 clean decoder
windows justify a scoped stream promotion, without changing unrelated channels.
"""
import json
import pathlib
import unittest

import build

ROOT = pathlib.Path(__file__).resolve().parents[1]
URL = "https://tvsen6.aynaott.com/msnbc/index.m3u8"


class MSNowPromotionRegressionTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        self.sources = json.loads((ROOT / "manual_sources.json").read_text(encoding="utf-8"))

    def test_single_exact_approved_msnow_source(self):
        items = [s for s in self.sources["streams"] if s.get("tvg_id") == "MSNOW.us"]
        self.assertEqual(len(items), 1)
        new = items[0]
        self.assertEqual(new["url"], URL)
        self.assertEqual(new["family"], "aynaott")
        self.assertTrue(new["local_verified_override"])
        self.assertEqual(new["content_kind"], "full-linear")
        self.assertEqual(new["headers"], {})
        self.assertIn("10 minutes", new["local_verified_note"])

    def test_production_source_preferred_without_touching_nicktoons(self):
        rows = [s for s in self.sources["streams"] if s.get("tvg_id") == "MSNOW.us"]
        first = build.select_streams(rows, 3, self.config, channel_id="MSNOW.us")
        self.assertEqual(first[0]["url"], URL)
        self.assertEqual(build.stream_object(first[0], 1)["url"], URL)
        self.assertEqual(
            build.channel_preference_rules(self.config, "MSNOW.us")[0]["family"],
            "aynaott",
        )
        self.assertEqual(
            build.channel_preference_rules(self.config, "Nicktoons.us")[0]["family"],
            "aynascope",
        )

    def test_exact_msnow_test_retired_and_no_other_aynaott_exception(self):
        local = self.config["local_test_catalog"]
        self.assertIn("aynaott.com", local["exclude_provider_hosts"])
        self.assertIn("aynascope.net", local["exclude_provider_hosts"])
        self.assertFalse(any(
            item.get("tvg_id") == "MSNOW.us"
            for item in local.get("controlled_sources", [])
        ))
        local_rows, _ = build.build_local_test_channels([], [], self.config)
        self.assertFalse(any(
            stream.get("url") == URL
            for c in local_rows for stream in c.get("streams", [])
        ))

    def test_existing_url_kill_switch_still_applies_to_manual_source(self):
        self.config["safety_controls"]["disabled_urls"].append(URL)
        source = next(s for s in self.sources["streams"] if s["tvg_id"] == "MSNOW.us")
        kept, rejected = build.apply_safety_controls([source], self.config)
        self.assertEqual(kept, [])
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["url"], URL)

    def test_existing_production_channel_qa_and_guard_remain_enabled(self):
        self.assertTrue(self.config["deployment_guard"]["enabled"])
        self.assertIn("DisneyChannel.us", self.config["deployment_guard"]["required_channel_ids"])
        self.assertIn("NationalGeographic.us", self.config["deployment_guard"]["required_channel_ids"])
        self.assertFalse(any(item.get("tvg_id") == "MSNOW.us" for item in
            self.config["curation"].get("stream_quarantine", [])))


if __name__ == "__main__":
    unittest.main()
