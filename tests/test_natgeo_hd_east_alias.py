import json
import unittest
from pathlib import Path

import build


class NatGeoHDEastStandbyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(Path("config.json").read_text(encoding="utf-8"))

    def test_only_natgeo_hd_east_variant_gets_targeted_remap(self):
        entries = [
            {
                "name": "National Geographic HD East",
                "tvg_id": "NationalGeographic.us@HDEast",
                "family": "iptv-org",
                "url": "http://198.58.104.90:8989/natgeo/index.m3u8",
            },
            {
                "name": "National Geographic",
                "tvg_id": "NationalGeographic.us@East",
                "family": "iptv-org",
                "url": "http://212.5.144.156:8080/natgeo/index.m3u8",
            },
            {
                "name": "History East",
                "tvg_id": "History.us@East",
                "family": "iptv-org",
                "url": "http://212.5.144.156:8080/history/index.m3u8",
            },
            {
                "name": "National Geographic Latin America",
                "tvg_id": "NationalGeographicLatinAmerica.us@Panregional",
                "family": "iptv-org",
                "url": "https://example.test/latam.m3u8",
            },
        ]
        mapped = build.canonicalize_approved_sources(entries, self.config)
        by_url = {e["url"]: e for e in mapped}
        alt = by_url["http://198.58.104.90:8989/natgeo/index.m3u8"]
        primary = by_url["http://212.5.144.156:8080/natgeo/index.m3u8"]
        self.assertEqual(alt["tvg_id"], "NationalGeographic.us")
        self.assertEqual(alt["source_tvg_id"], "NationalGeographic.us@HDEast")
        self.assertEqual(primary["tvg_id"], "NationalGeographic.us@East")
        self.assertEqual(
            build.playlist_key(alt), build.playlist_key(primary)
        )
        self.assertEqual(
            by_url["https://example.test/latam.m3u8"]["tvg_id"],
            "NationalGeographicLatinAmerica.us@Panregional",
        )
        kept, dropped = build.curate_entries(mapped, self.config)
        kept_urls = {row["url"] for row in kept}
        self.assertIn(alt["url"], kept_urls)
        self.assertIn(primary["url"], kept_urls)
        self.assertIn("http://212.5.144.156:8080/history/index.m3u8", kept_urls)
        self.assertIn(
            "https://example.test/latam.m3u8",
            {row["url"] for row in dropped},
        )

    def test_primary_and_guard_configuration_unchanged(self):
        curation = self.config["curation"]
        self.assertEqual(
            curation["canonical_id_aliases"]["NationalGeographic.us@HDEast"],
            "NationalGeographic.us",
        )
        self.assertEqual(
            curation["published_tvg_id_pins"]["NationalGeographic.us"],
            "NationalGeographic.us",
        )
        self.assertIn(
            "NationalGeographic.us",
            self.config["deployment_guard"]["required_channel_ids"],
        )


if __name__ == "__main__":
    unittest.main()
