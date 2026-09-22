import datetime as dt
import unittest

import build


class PriorityRecoveryTests(unittest.TestCase):
    def test_prioritizes_philly_then_favorites_with_host_and_channel_limits(self):
        now = dt.datetime(2026, 9, 22, 12, tzinfo=dt.timezone.utc)
        entries = [
            {"tvg_id": "Philly.us", "name": "Philly", "url": "https://a.test/1.m3u8", "philly": True, "priority": 5},
            {"tvg_id": "Favorite.us", "name": "Favorite", "url": "https://a.test/2.m3u8", "priority": 1},
            {"tvg_id": "Other.us", "name": "Other", "url": "https://b.test/3.m3u8", "priority": 1},
            {"tvg_id": "Recent.us", "name": "Recent", "url": "https://c.test/4.m3u8", "priority": 1},
        ]
        cooldown_entries = {(entry["url"], ()): entry for entry in entries}
        streams = {}
        for entry in entries:
            streams[build._stream_stability_key(entry)] = {
                "classification": "Dead",
                "last_probed_at": "2026-09-21T00:00:00Z",
            }
        streams[build._stream_stability_key(entries[-1])]["last_probed_at"] = "2026-09-22T10:00:00Z"
        channels = {
            f"National:{entry['tvg_id'].lower()}": {"pattern": entry["tvg_id"], "present": False}
            for entry in entries
        }
        config = {
            "favorites": ["Favorite.us"],
            "stream_health": {"priority_recovery": {
                "enabled": True,
                "max_forced_urls_per_build": 2,
                "min_retry_hours": 6,
                "max_per_host": 1,
            }},
        }

        selected, report = build.plan_priority_recovery_probes(
            cooldown_entries,
            {"streams": streams},
            {"channels": channels},
            config,
            now,
        )

        selected_urls = {key[0] for key in selected}
        self.assertEqual(selected_urls, {"https://a.test/1.m3u8", "https://b.test/3.m3u8"})
        self.assertEqual(report["selected_count"], 2)
        self.assertEqual(report["deferred_too_recent"], 1)
        self.assertTrue(report["restricted_to_prior_missing"])

    def test_limits_recovery_to_channels_missing_in_prior_state(self):
        now = dt.datetime(2026, 9, 22, 12, tzinfo=dt.timezone.utc)
        missing = {"tvg_id": "Missing.us", "name": "Missing", "url": "https://a.test/m.m3u8"}
        present = {"tvg_id": "Present.us", "name": "Present", "url": "https://b.test/p.m3u8"}
        cooldown_entries = {(entry["url"], ()): entry for entry in (missing, present)}
        streams = {
            build._stream_stability_key(entry): {
                "classification": "Dead",
                "last_probed_at": "2026-09-20T00:00:00Z",
            }
            for entry in (missing, present)
        }
        state = {"channels": {
            "National:missing.us": {"pattern": "Missing.us", "present": False},
            "National:present.us": {"pattern": "Present.us", "present": True},
        }}
        selected, report = build.plan_priority_recovery_probes(
            cooldown_entries,
            {"streams": streams},
            state,
            {"stream_health": {"priority_recovery": {"enabled": True}}},
            now,
        )
        self.assertEqual({key[0] for key in selected}, {missing["url"]})
        self.assertEqual(report["deferred_not_missing"], 1)


if __name__ == "__main__":
    unittest.main()
