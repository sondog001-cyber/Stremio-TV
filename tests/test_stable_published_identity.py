import unittest
from unittest import mock

import build


class StableCuratedPublishedIdentityTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "curation": {
                "enabled": True,
                "national_allow": ["DisneyChannel.us", "NationalGeographic.us"],
                "philly_allow": ["Fox.us@WTXFTV"],
                "published_tvg_id_pins": {
                    "DisneyChannel.us": "DisneyChannel.us",
                    "NationalGeographic.us": "NationalGeographic.us",
                },
            },
        }

    @staticmethod
    def stream(tvg_id, label, url):
        return {
            "name": label,
            "tvg_id": tvg_id,
            "url": url,
            "source": "source",
            "family": "test",
            "quality": "HD",
            "health": {"status": "ok"},
        }

    def merge(self, entries, config=None):
        # Source selection is out of scope for this metadata-only change.
        with mock.patch.object(build, "select_streams", side_effect=lambda streams, *args, **kwargs: list(streams)):
            return build.merge_channels(entries, [], 3, self.config if config is None else config)

    def test_east_only_disney_has_stable_catalog_id_and_pinned_display_tvg_id(self):
        source = self.stream("DisneyChannel.us@East", "Disney Channel (United States)",
                             "https://example.test/disney.m3u8")
        out = self.merge([source])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["tvg_id"], "DisneyChannel.us")
        self.assertEqual(out[0]["streams"][0]["tvg_id"], "DisneyChannel.us@East")
        self.assertEqual(out[0]["streams"][0]["url"], source["url"])
        self.assertEqual(out[0]["key"], "id:disneychannel.us")
        base = self.merge([self.stream("DisneyChannel.us", "Disney Channel", source["url"])])[0]
        self.assertEqual(out[0]["id"], base["id"])

    def test_natgeo_east_only_and_base_both_publish_same_exact_id(self):
        for upstream_tvg_id in ("NationalGeographic.us@East", "NationalGeographic.us"):
            with self.subTest(upstream_tvg_id=upstream_tvg_id):
                out = self.merge([self.stream(upstream_tvg_id, "National Geographic",
                                              "https://example.test/natgeo.m3u8")])
                self.assertEqual(out[0]["tvg_id"], "NationalGeographic.us")
                self.assertEqual(out[0]["streams"][0]["tvg_id"], upstream_tvg_id)

    def test_without_explicit_pin_variants_are_unchanged(self):
        config = {"curation": {"philly_allow": [], "national_allow": ["DisneyChannel.us"]}}
        out = self.merge([self.stream("DisneyChannel.us@East", "Disney", "https://x.example/live")], config)
        self.assertEqual(out[0]["tvg_id"], "DisneyChannel.us@East")

    def test_affiliate_specific_ids_not_collapsed_to_generic_brand(self):
        bad_config = {"curation": {
            "philly_allow": ["Fox.us@WTXFTV"], "national_allow": [],
            "published_tvg_id_pins": {"Fox.us@WTXFTV": "Fox.us"},
        }}
        out = self.merge([self.stream("Fox.us@WTXFTV", "FOX 29", "https://x.example/live")], bad_config)
        self.assertEqual(out[0]["tvg_id"], "Fox.us@WTXFTV")

    def test_unallowed_or_mismatched_pin_cannot_relabel_channel(self):
        config = {"curation": {
            "philly_allow": [], "national_allow": ["NationalGeographic.us"],
            "published_tvg_id_pins": {"DisneyChannel.us": "NationalGeographic.us"},
        }}
        out = self.merge([self.stream("DisneyChannel.us@East", "Disney", "https://x.example/live")], config)
        self.assertEqual(out[0]["tvg_id"], "DisneyChannel.us@East")


if __name__ == "__main__":
    unittest.main()
