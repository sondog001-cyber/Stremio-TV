import unittest

import build


class EpgOverrideTests(unittest.TestCase):
    def test_all_manual_aliases_point_to_known_guide_ids(self):
        aliases = build.load_json(build.DEFAULT_ALIASES)
        guide_channels = [
            {"id": epg_id, "names": [epg_id], "icon": ""}
            for epg_id in aliases["by_tvg_id"].values()
        ]
        indexes = build.make_epg_indexes(guide_channels)
        for tvg_id, epg_id in aliases["by_tvg_id"].items():
            matched, method, score = build.match_epg_channel(
                {"tvg_id": tvg_id, "name": tvg_id}, indexes, aliases
            )
            self.assertEqual(matched, epg_id)
            self.assertEqual(method, "manual-tvg-id")
            self.assertEqual(score, 1.0)

    def test_unavailable_override_does_not_substitute_another_channel(self):
        aliases = build.load_json(build.DEFAULT_ALIASES)
        matched, method, score = build.match_epg_channel(
            {"tvg_id": "HallmarkMoviesMore.us@SD", "name": "Hallmark Movies & More"},
            build.make_epg_indexes([]),
            aliases,
        )
        self.assertIsNone(matched)
        self.assertTrue(method.startswith("manual-unavailable:"))
        self.assertEqual(score, 1.0)


if __name__ == "__main__":
    unittest.main()
