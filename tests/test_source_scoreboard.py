import unittest

import build


class SourceScoreboardTests(unittest.TestCase):
    def test_tracks_yield_selection_recovery_and_history(self):
        health = [{
            "family": "direct", "source": "Source A", "url": "https://origin.test/a",
            "effective_url": "https://cdn.test/live.m3u8", "provider_host": "cdn.test",
            "health": {"status": "ok"},
        }]
        stream = {
            "family": "direct", "source": "Source A", "url": "https://origin.test/a",
            "effective_url": "https://cdn.test/live.m3u8",
        }
        channels = [{"tvg_id": "Recovered.us", "streams": [stream]}]
        changes = {"recovered_this_build": [{"tvg_id": "Recovered.us"}]}

        report = build.build_source_family_scoreboard(
            health, channels, changes, [], {"source_scoreboard": {"history_size": 5}},
            enabled=False, previous={},
        )

        row = report["sources"][0]
        self.assertEqual(row["recommendation"], "keep")
        self.assertEqual(row["current"]["unique_effective_urls"], 1)
        self.assertEqual(row["current"]["selected_channels"], 1)
        self.assertEqual(row["current"]["recovered_channels"], 1)

    def test_recommends_review_after_three_zero_yield_builds(self):
        key = "dead::Dead Source"
        prior = {
            "updated_at": "prior",
            "sources": [{
                "key": key, "family": "dead", "source": "Dead Source",
                "history": [
                    {"candidates": 1, "passing": 0, "selected_streams": 0},
                    {"candidates": 2, "passing": 0, "selected_streams": 0},
                ],
            }],
        }
        health = [{
            "family": "dead", "source": "Dead Source", "url": "https://dead.test/a",
            "health": {"status": "failed"},
        }]

        report = build.build_source_family_scoreboard(
            health, [], {}, [], {"source_scoreboard": {"remove_review_min_builds": 3}},
            enabled=False, previous=prior,
        )

        self.assertEqual(report["sources"][0]["recommendation"], "remove-review")
        self.assertEqual(report["summary"]["remove_review"], 1)


if __name__ == "__main__":
    unittest.main()
