import datetime as dt
import unittest
from unittest import mock

import build


class FakeResponse:
    def __init__(self, url, body, content_type="application/vnd.apple.mpegurl", status=200):
        self._url = url
        self._body = body.encode() if isinstance(body, str) else body
        self.headers = {"Content-Type": content_type}
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self):
        return self._url

    def read(self, limit=-1):
        return self._body if limit < 0 else self._body[:limit]


class HlsQualityTests(unittest.TestCase):
    def test_master_probe_measures_highest_rendition_and_verifies_it(self):
        master_url = "https://example.test/master.m3u8"
        master = """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=700000,RESOLUTION=640x360
low/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080
high/index.m3u8
"""
        media = "#EXTM3U\n#EXTINF:6,\nsegment.ts\n"
        requested = []

        def urlopen(request, timeout=None):
            url = request.full_url
            requested.append(url)
            if url == master_url:
                return FakeResponse(url, master)
            if url.endswith("high/index.m3u8"):
                return FakeResponse(url, media)
            if url.endswith("high/segment.ts"):
                return FakeResponse(url, b"x", "video/mp2t")
            raise AssertionError(f"unexpected URL: {url}")

        with mock.patch.object(build.urllib.request, "urlopen", side_effect=urlopen):
            result = build._probe_stream({"url": master_url}, timeout=2, verify_segment=True)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["measured_width"], 1920)
        self.assertEqual(result["measured_height"], 1080)
        self.assertEqual(result["measured_quality"], "1080P")
        self.assertEqual(result["available_resolutions"], ["1920x1080", "640x360"])
        self.assertIn("https://example.test/high/index.m3u8", requested)

    def test_measured_height_overrides_incorrect_declared_quality(self):
        self.assertTrue(build.is_hd_stream({"quality": "SD", "measured_height": 1080}))
        self.assertTrue(build.is_sd_stream({"quality": "HD", "measured_height": 480}))
        self.assertEqual(build.quality_label({"quality": "SD", "measured_quality": "1080P"}), "1080P")


class DeadSourceCooldownTests(unittest.TestCase):
    def test_dead_source_waits_until_retry_time(self):
        entry = {"url": "https://example.test/dead.m3u8", "headers": {}}
        key = build._stream_stability_key(entry)
        previous = {
            "streams": {
                key: {
                    "classification": "Dead",
                    "history": [False],
                    "last_result": "fail",
                    "last_probed_at": "2026-09-22T04:00:00Z",
                    "consecutive_failures": 1,
                }
            }
        }
        config = {"stream_stability": {"enabled": True, "dead_source_cooldown_hours": [1, 6, 24]}}
        result = build._dead_source_cooldown(
            entry,
            previous,
            config,
            dt.datetime(2026, 9, 22, 4, 30, tzinfo=dt.timezone.utc),
        )
        self.assertEqual(result["status"], "cooldown")
        self.assertEqual(result["cooldown_until"], "2026-09-22T05:00:00Z")


if __name__ == "__main__":
    unittest.main()
