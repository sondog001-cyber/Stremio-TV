import unittest

import build


def stream(family, url, *, quality="HD", stability_rank=0, passes=5, priority=0):
    return {
        "name": "ESPN",
        "name_raw": "ESPN",
        "tvg_id": "ESPN.us",
        "family": family,
        "source": family,
        "url": url,
        "quality": quality,
        "priority": priority,
        "content_kind": "full-linear",
        "stability": {
            "rank": stability_rank,
            "passes": passes,
            "samples": 5,
            "classification": "Stable" if stability_rank == 0 else "Quarantine",
        },
    }


def config_with_preferences(preferences):
    return {
        "stream_selection": {
            "target_hd": 2,
            "target_sd": 1,
            "prefer_distinct_families": True,
            "primary_family": "iptv-org",
            "fallback_families": ["free-tv", "shovo"],
            "channel_preferences": {"ESPN.us": preferences},
        }
    }


class SourceOrderingTests(unittest.TestCase):
    def test_exact_channel_preference_orders_primary_then_fallback(self):
        config = config_with_preferences(["free-tv", "iptv-org", "shovo"])
        streams = [
            stream("iptv-org", "https://example.test/iptv.m3u8", priority=0),
            stream("shovo", "https://example.test/shovo.m3u8", priority=1),
            stream("free-tv", "https://example.test/free.m3u8", priority=10),
        ]

        selected = build.select_streams(streams, 3, config, channel_id="ESPN.us")

        self.assertEqual([item["family"] for item in selected], ["free-tv", "iptv-org", "shovo"])
        self.assertEqual([item["preference_rank"] for item in selected], [1, 2, 3])

    def test_stable_fallback_outranks_quarantined_preferred_source(self):
        config = config_with_preferences(["free-tv", "iptv-org"])
        streams = [
            stream(
                "free-tv",
                "https://example.test/recovered.m3u8",
                stability_rank=2,
                passes=1,
            ),
            stream("iptv-org", "https://example.test/stable.m3u8", stability_rank=0, passes=5),
        ]

        selected = build.select_streams(streams, 3, config, channel_id="ESPN.us")

        self.assertEqual(selected[0]["family"], "iptv-org")
        self.assertEqual(selected[0]["stability"]["classification"], "Stable")

    def test_most_reliable_sd_can_be_primary_before_hd_fallback(self):
        config = config_with_preferences(["free-tv", "iptv-org"])
        streams = [
            stream("free-tv", "https://example.test/stable-sd.m3u8", quality="SD", stability_rank=0),
            stream("iptv-org", "https://example.test/new-hd.m3u8", quality="HD", stability_rank=2, passes=1),
        ]

        selected = build.select_streams(streams, 3, config, channel_id="ESPN.us")

        self.assertEqual(selected[0]["quality"], "SD")
        self.assertEqual(selected[1]["quality"], "HD")


if __name__ == "__main__":
    unittest.main()
