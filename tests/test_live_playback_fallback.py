import copy
import unittest

import build


class LivePlaybackFallbackTests(unittest.TestCase):
    def setUp(self):
        self.channel = {
            "id": "stremiotv_test", "name": "Test TV", "epg_matched": True,
            "logo": "https://example.test/logo.png",
            "streams": [{"url": "https://example.test/live.m3u8"}],
        }
        self.programmes = [{
            "id": "stremiotv_test:epg:2099-01-01T12:00:00Z",
            "title": "Future programme", "released": "2099-01-01T12:00:00Z",
            "startTime": "2099-01-01T12:00:00Z",
            "endTime": "2099-01-01T13:00:00Z",
        }]

    def test_catalog_and_detail_default_to_existing_channel_stream_id(self):
        preview = build.channel_preview(self.channel)
        detail = build.channel_meta(self.channel, self.programmes, live_fallback=True)
        for meta in (preview, detail):
            self.assertEqual(meta["behaviorHints"]["defaultVideoId"], self.channel["id"])
            self.assertTrue(meta["behaviorHints"]["isLive"])
        self.assertEqual(detail["videos"][0]["id"], self.channel["id"])

    def test_live_entry_is_available_without_claiming_a_scheduled_programme(self):
        detail = build.channel_meta(self.channel, self.programmes, live_fallback=True)
        live = detail["videos"][0]
        self.assertEqual(live["title"], "Watch live")
        self.assertTrue(live["available"])
        self.assertEqual(live["released"], "1970-01-01T00:00:00Z")
        self.assertIn("not recordings", live["overview"])
        for field in ("startTime", "endTime", "season", "episode", "streams"):
            self.assertNotIn(field, live)

    def test_native_guide_and_future_programmes_are_unchanged(self):
        original = copy.deepcopy((self.channel, self.programmes))
        guide = build.channel_meta(self.channel, self.programmes)
        detail = build.channel_meta(self.channel, self.programmes, live_fallback=True)
        self.assertEqual(guide["videos"], self.programmes)
        self.assertEqual(detail["videos"][1:], self.programmes)
        self.assertTrue(guide["behaviorHints"]["hasScheduledVideos"])
        self.assertTrue(detail["behaviorHints"]["hasScheduledVideos"])
        self.assertNotIn("available", detail["videos"][1])
        self.assertEqual((self.channel, self.programmes), original)

    def test_channel_without_epg_still_has_live_playback(self):
        self.channel["epg_matched"] = False
        self.channel.pop("logo")
        detail = build.channel_meta(self.channel, [], live_fallback=True)
        self.assertEqual(len(detail["videos"]), 1)
        self.assertNotIn("hasScheduledVideos", detail["behaviorHints"])
        self.assertNotIn("thumbnail", detail["videos"][0])


if __name__ == "__main__":
    unittest.main()
