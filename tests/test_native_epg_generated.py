import gzip
import json
import tempfile
import unittest
from pathlib import Path

import build


class NativeEpgGeneratedOutputTests(unittest.TestCase):
    def make_channels(self, count=111):
        channels = []
        for index in range(count):
            channels.append(
                {
                    "id": f"stremiotv_test_{index:03d}",
                    "name": f"Test Channel {index:03d}",
                    "category": "Sports" if index == 0 else "Entertainment",
                    "streams": [{"url": f"https://example.test/{index}.m3u8"}],
                    "philly": False,
                    "epg_matched": True,
                    "epg_status": "matched",
                }
            )
        return channels

    def read_json(self, path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def test_111_channel_catalog_uses_exact_terminal_skip(self):
        channels = self.make_channels()

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            build.write_paginated_catalog(output, "channels", channels, page_size=100)

            first = self.read_json(output / "catalog" / "tv" / "channels.json")
            second = self.read_json(output / "catalog" / "tv" / "channels" / "skip=100.json")
            terminal = self.read_json(output / "catalog" / "tv" / "channels" / "skip=111.json")

            self.assertEqual(len(first["metas"]), 100)
            self.assertEqual(len(second["metas"]), 11)
            self.assertEqual(terminal["metas"], [])
            self.assertEqual(terminal["cacheMaxAge"], 300)
            self.assertEqual(terminal["staleRevalidate"], 1800)
            self.assertEqual(terminal["staleError"], 604800)
            self.assertFalse((output / "catalog" / "tv" / "channels" / "skip=200.json").exists())

    def test_generated_epg_pages_include_videos_midnight_overlap_and_exact_terminal_skip(self):
        channels = self.make_channels()

        xml = """<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <programme channel="epg0" start="20260923233000 +0000" stop="20260924003000 +0000">
    <title>Cross Midnight Test</title>
    <desc>Programme spans two UTC dates.</desc>
    <category>Sports</category>
  </programme>
</tv>
"""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            epg_path = root / "epg.xml.gz"
            with gzip.open(epg_path, "wb") as handle:
                handle.write(xml.encode("utf-8"))

            schedules, dates = build.build_program_index(
                epg_path,
                {"epg0": [channels[0]["id"]]},
            )

            self.assertEqual(dates, {"2026-09-23", "2026-09-24"})
            build.write_epg_pages(root, channels, schedules, dates, page_size=100)

            catalog_dir = root / "catalog" / "tv" / "channels"

            day_one = self.read_json(catalog_dir / "date=2026-09-23.json")
            day_two = self.read_json(catalog_dir / "date=2026-09-24.json")
            second_page = self.read_json(catalog_dir / "date=2026-09-23&skip=100.json")
            terminal = self.read_json(catalog_dir / "date=2026-09-23&skip=111.json")

            self.assertEqual(len(day_one["metasDetailed"]), 100)
            self.assertEqual(len(second_page["metasDetailed"]), 11)
            self.assertEqual(terminal["metasDetailed"], [])
            self.assertEqual(terminal["cacheMaxAge"], 300)
            self.assertEqual(terminal["staleRevalidate"], 1800)
            self.assertEqual(terminal["staleError"], 604800)
            self.assertFalse((catalog_dir / "date=2026-09-23&skip=200.json").exists())

            first_day_channel = day_one["metasDetailed"][0]
            second_day_channel = day_two["metasDetailed"][0]

            self.assertTrue(first_day_channel["behaviorHints"]["hasScheduledVideos"])
            self.assertTrue(second_day_channel["behaviorHints"]["hasScheduledVideos"])
            self.assertEqual(first_day_channel["videos"][0]["title"], "Cross Midnight Test")
            self.assertEqual(second_day_channel["videos"][0]["title"], "Cross Midnight Test")
            self.assertEqual(first_day_channel["videos"][0]["startTime"], "2026-09-23T23:30:00Z")
            self.assertEqual(first_day_channel["videos"][0]["endTime"], "2026-09-24T00:30:00Z")


if __name__ == "__main__":
    unittest.main()
