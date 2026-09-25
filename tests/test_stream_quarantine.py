import json
import pathlib
import unittest

import build


class StreamQuarantineTests(unittest.TestCase):
    def test_exact_channel_scoped_playback_quarantine(self):
        bad_url = "http://example.test/hgtv"
        entries = [
            {
                "name": "HGTV",
                "tvg_id": "HGTV.us",
                "source": "Public playlist",
                "family": "test",
                "url": bad_url,
            },
            {
                "name": "Other Channel",
                "tvg_id": "Other.us",
                "source": "Public playlist",
                "family": "test",
                "url": bad_url,
            },
            {
                "name": "HGTV Backup",
                "tvg_id": "HGTV.us",
                "source": "Backup",
                "family": "backup",
                "url": "https://example.test/hgtv-good.m3u8",
            },
        ]
        config = {
            "curation": {
                "stream_quarantine": [
                    {
                        "tvg_id": "HGTV.us",
                        "url": bad_url,
                        "reason": "Confirmed repeating playback",
                        "observed_at": "2026-09-23",
                    }
                ]
            }
        }

        kept, quarantined = build.apply_stream_quarantine(entries, config)

        self.assertEqual(len(kept), 2)
        self.assertEqual({item["name"] for item in kept}, {"Other Channel", "HGTV Backup"})
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(quarantined[0]["tvg_id"], "HGTV.us")
        self.assertEqual(quarantined[0]["reason"], "Confirmed repeating playback")

    def test_production_quarantines_two_decoder_dead_hls_primaries(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        rules = {
            (row.get("tvg_id"), row.get("url"))
            for row in config["curation"]["stream_quarantine"]
        }

        self.assertIn(
            (
                "CinemaxClassics.us@East",
                "http://23.237.104.106:8080/USA_5STARMAX/index.m3u8",
            ),
            rules,
        )
        self.assertIn(
            (
                "StarzComedy.us@East",
                "http://23.237.104.106:8080/USA_STARZ_COMEDY/index.m3u8",
            ),
            rules,
        )

    def test_empty_quarantine_is_noop(self):
        entries = [{"tvg_id": "HGTV.us", "url": "https://example.test/hgtv.m3u8"}]
        kept, quarantined = build.apply_stream_quarantine(entries, {"curation": {}})
        self.assertEqual(kept, entries)
        self.assertEqual(quarantined, [])


if __name__ == "__main__":
    unittest.main()
