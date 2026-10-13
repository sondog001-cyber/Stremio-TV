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

    def test_production_quarantines_brazil_espn_from_espn_us(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        rules = {
            (row.get("tvg_id"), row.get("url"))
            for row in config["curation"]["stream_quarantine"]
        }

        self.assertIn(
            (
                "ESPN.us",
                "http://181.78.197.59:8000/play/a07z/index.m3u8",
            ),
            rules,
        )

    def test_user_confirmed_bravo_west_avformat_is_exactly_quarantined(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        bad = "http://206.212.244.63/26/index.m3u8"
        different = "http://tvsen7.aynascope.net/bravo/index.m3u8"
        candidates = [
            {"tvg_id": "Bravo.us", "name": "Bravo West", "url": bad},
            {"tvg_id": "Bravo.us", "name": "Other Bravo", "url": different},
            {"tvg_id": "MSNOW.us", "name": "MS NOW", "url": "https://tvsen6.aynaott.com/msnbc/index.m3u8"},
            {"tvg_id": "Other.us", "name": "Other", "url": bad},
        ]
        kept, quarantined = build.apply_stream_quarantine(candidates, config)
        self.assertEqual([row["name"] for row in quarantined], ["Bravo West"])
        self.assertEqual([row["name"] for row in kept], ["Other Bravo", "MS NOW", "Other"])
        self.assertIn("AVFormat", quarantined[0]["reason"])

    def test_failed_bravo_west_does_not_reappear_in_local_test(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        bad = "http://206.212.244.63/26/index.m3u8"
        input_rows = [
            {"tvg_id": "Bravo.us", "name": "Bravo West", "url": bad, "source": "Shovo",
             "family": "shovo", "health": {"status": "cooldown", "detail": "The read operation timed out"}},
        ]
        vetted, quarantined = build.apply_stream_quarantine(input_rows, config)
        channels, _ = build.build_local_test_channels(vetted, [], config)
        self.assertEqual(len(quarantined), 1)
        self.assertFalse(any(
            stream.get("url") == bad
            for channel in channels for stream in channel.get("streams", [])
        ))

    def test_empty_quarantine_is_noop(self):
        entries = [{"tvg_id": "HGTV.us", "url": "https://example.test/hgtv.m3u8"}]
        kept, quarantined = build.apply_stream_quarantine(entries, {"curation": {}})
        self.assertEqual(kept, entries)
        self.assertEqual(quarantined, [])


if __name__ == "__main__":
    unittest.main()
