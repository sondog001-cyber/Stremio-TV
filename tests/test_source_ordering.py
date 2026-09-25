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
            "prefer_distinct_provider_hosts": True,
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

    def test_backup_prefers_independent_provider_over_same_host_mirror(self):
        config = config_with_preferences(["iptv-org", "free-tv", "shovo"])
        streams = [
            stream("iptv-org", "https://a.moveonjoy.com/primary.m3u8"),
            stream("free-tv", "https://b.moveonjoy.com/mirror.m3u8"),
            stream("shovo", "https://cdn.independent.net/backup.m3u8"),
        ]

        selected = build.select_streams(streams, 2, config, channel_id="ESPN.us")

        self.assertEqual([item["family"] for item in selected], ["iptv-org", "shovo"])
        self.assertTrue(selected[1]["independent_provider"])

    def test_sourpatchkid_is_not_primary_when_an_alternative_exists(self):
        config = config_with_preferences([])
        config["stream_selection"]["primary_deprioritized_source_contains"] = [
            "SourPatchKid"
        ]
        streams = [
            {
                **stream(
                    "github-gist",
                    "http://themyst.icu:826/SourPatchKid/test/1",
                    priority=0,
                ),
                "source": "SourPatchKid Plus public gist",
            },
            stream(
                "free-tv",
                "https://independent.example/live.m3u8",
                priority=20,
            ),
        ]

        selected = build.select_streams(streams, 2, config, channel_id="ESPN.us")

        self.assertEqual(selected[0]["family"], "free-tv")
        self.assertFalse(selected[0]["primary_deprioritized"])
        self.assertEqual(selected[1]["source"], "SourPatchKid Plus public gist")
        self.assertTrue(selected[1]["primary_deprioritized"])

    def test_sourpatchkid_can_be_primary_when_it_is_the_only_passing_source(self):
        config = config_with_preferences([])
        config["stream_selection"]["primary_deprioritized_source_contains"] = [
            "SourPatchKid"
        ]
        only = {
            **stream(
                "github-gist",
                "http://themyst.icu:826/SourPatchKid/test/1",
            ),
            "source": "SourPatchKid Plus public gist",
        }

        selected = build.select_streams([only], 3, config, channel_id="ESPN.us")

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["source"], "SourPatchKid Plus public gist")
        self.assertTrue(selected[0]["primary_deprioritized"])

    def test_redirected_duplicates_collapse_by_effective_url(self):
        config = config_with_preferences(["iptv-org", "free-tv", "shovo"])
        streams = [
            {**stream("iptv-org", "https://one.example/a"), "effective_url": "https://cdn.example/live.m3u8"},
            {**stream("free-tv", "https://two.example/b"), "effective_url": "https://cdn.example/live.m3u8"},
            stream("shovo", "https://backup.test/live.m3u8"),
        ]

        selected = build.select_streams(streams, 3, config, channel_id="ESPN.us")

        self.assertEqual(len(selected), 2)
        self.assertEqual(len({item["effective_url"] for item in selected}), 2)

    def test_host_redundancy_flags_same_provider_mirrors(self):
        channels = [{
            "tvg_id": "ESPN.us",
            "name": "ESPN",
            "streams": [
                stream("iptv-org", "https://a.moveonjoy.com/a.m3u8"),
                stream("free-tv", "https://b.moveonjoy.com/b.m3u8"),
            ],
        }]

        report = build.build_host_redundancy_diagnostics(channels)

        self.assertEqual(report["summary"]["fragile_single_provider"], 1)
        self.assertFalse(report["channels"][0]["has_independent_backup"])


if __name__ == "__main__":
    unittest.main()
