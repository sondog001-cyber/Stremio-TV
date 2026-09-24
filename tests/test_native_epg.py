import unittest

import build


class NativeEpgTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "addon": {
                "id": "com.example.stremio",
                "version": "1.0.0",
                "name": "Test TV",
                "description": "Test addon",
            },
            "catalogs": [],
        }

    def test_manifest_advertises_native_epg(self):
        manifest = build.build_manifest(self.config)

        self.assertTrue(manifest["behaviorHints"]["epgProvider"])

        channels_catalog = next(
            catalog for catalog in manifest["catalogs"]
            if catalog["type"] == "tv" and catalog["id"] == "channels"
        )
        extras = {extra["name"]: extra for extra in channels_catalog["extra"]}
        self.assertIn("skip", extras)
        self.assertIn("date", extras)
        self.assertFalse(extras["date"].get("isRequired", False))

    def test_matched_channel_meta_exposes_programmes_as_videos(self):
        channel = {
            "id": "stremiotv_test",
            "name": "Test Channel",
            "category": "Sports",
            "streams": [{"url": "https://example.test/live.m3u8"}],
            "philly": False,
            "epg_matched": True,
            "epg_status": "matched",
        }
        programmes = [
            {
                "id": "stremiotv_test:epg:2026-09-23T20:00:00Z",
                "title": "Test Programme",
                "released": "2026-09-23T20:00:00Z",
                "startTime": "2026-09-23T20:00:00Z",
                "endTime": "2026-09-23T21:00:00Z",
                "runtime": "60 min",
            }
        ]

        meta = build.channel_meta(channel, programmes)

        self.assertTrue(meta["behaviorHints"]["isLive"])
        self.assertTrue(meta["behaviorHints"]["hasScheduledVideos"])
        self.assertEqual(meta["videos"], programmes)

    def test_unmatched_channel_does_not_claim_scheduled_videos(self):
        channel = {
            "id": "stremiotv_test",
            "name": "Test Channel",
            "category": "Sports",
            "streams": [{"url": "https://example.test/live.m3u8"}],
            "philly": False,
            "epg_matched": False,
            "epg_status": "unmatched",
        }

        meta = build.channel_meta(channel, [])

        self.assertTrue(meta["behaviorHints"]["isLive"])
        self.assertNotIn("hasScheduledVideos", meta["behaviorHints"])
        self.assertNotIn("videos", meta)


if __name__ == "__main__":
    unittest.main()
