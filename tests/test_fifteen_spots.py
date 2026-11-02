import datetime as dt
import json
from pathlib import Path
import unittest

from research import fifteen_new_spots as review


class FifteenSpotTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())
        self.now = dt.datetime(2026, 10, 15, tzinfo=dt.timezone.utc)

    def test_no_device_credentials_numeric_accounts_or_expired_tokens(self):
        for url in ["https://example.com/live.php?mac=00:11:22:33:44:55",
                    "http://example.com/123456/987654/123.ts",
                    "https://example.com/live/user/password/23.m3u8",
                    "https://example.com/x.m3u8?e=1600000000&token=public"]:
            with self.subTest(url=url):
                self.assertFalse(review.permitted({"tvg_id": "History.us", "url": url}, self.config, self.now))
        self.assertTrue(review.permitted({"tvg_id": "History.us", "url": "https://example.com/live/history/index.m3u8"}, self.config, self.now))

    def test_mirrors_name_only_and_fast_are_distinct_from_exact_probe_candidates(self):
        text = ('#EXTM3U\n#EXTINF:-1 tvg-id="History.us@East",History\nhttps://example.com/history.m3u8\n'
                '#EXTINF:-1,History\nhttps://example.com/name-only.m3u8\n'
                '#EXTINF:-1 tvg-id="History.us@West",History West\nhttps://example.com/west.m3u8\n'
                '#EXTINF:-1 tvg-id="SmithsonianChannel.us",Smithsonian\nhttps://example.pluto.tv/fast.m3u8\n')
        doc = {"repo": "example/source", "path": "us.m3u", "url": "https://example.com/us.m3u", "status": "ok", "observed_sha256": "hash"}
        report = review.inspect([(doc, text), ({**doc, "repo": "example/mirror"}, text)],
                                self.config, ["History.us", "SmithsonianChannel.us"],
                                {"known_url_sha256": [], "provider_hosts": []}, self.now)
        self.assertEqual(report["summary"]["actual_channel_catalogs"], 2)
        self.assertEqual(report["summary"]["novel_safe_candidate_combinations"], 3)
        self.assertEqual(len(report["eligible_candidates"]), 1)
        self.assertEqual(len(report["eligible_candidates"][0]["provenance"]), 2)

    def test_unsafe_matching_urls_are_counted_without_copying_credentials(self):
        doc = {"repo": "example/source", "path": "us.m3u", "url": "https://example.com/us.m3u", "status": "ok", "observed_sha256": "hash"}
        text = '#EXTM3U\n#EXTINF:-1 tvg-id="History.us",History\nhttps://example.com/live/secretname/secretpass/1.m3u8\n'
        report = review.inspect([(doc, text)], self.config, ["History.us"],
                                {"known_url_sha256": [], "provider_hosts": []}, self.now)
        self.assertEqual(report["spots"][0]["rejected"], 1)
        self.assertNotIn("secret", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
