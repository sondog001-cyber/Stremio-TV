import datetime as dt
import unittest

import build
import record_client_result


class ClientVerificationTests(unittest.TestCase):
    def test_fresh_result_expires_at_configured_ttl(self):
        result = build.evaluate_client_verification(
            {"status": "passed", "tested_at": "2026-09-20T12:00:00Z"},
            {"default_ttl_hours": 72},
            dt.datetime(2026, 9, 22, 12, tzinfo=dt.timezone.utc),
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["expires_at"], "2026-09-23T12:00:00Z")
        self.assertEqual(result["age_hours"], 48.0)

    def test_old_result_is_expired_not_passing(self):
        result = build.evaluate_client_verification(
            {"status": "passed", "tested_at": "2026-09-01T00:00:00Z"},
            {"default_ttl_hours": 168},
            dt.datetime(2026, 9, 22, tzinfo=dt.timezone.utc),
        )
        self.assertEqual(result["status"], "expired")
        self.assertEqual(result["recorded_status"], "passed")

    def test_missing_timestamp_is_invalid(self):
        result = build.evaluate_client_verification(
            {"status": "failed"},
            {"default_ttl_hours": 168},
            dt.datetime(2026, 9, 22, tzinfo=dt.timezone.utc),
        )
        self.assertEqual(result["status"], "invalid")

    def test_recorder_uses_exact_configured_channel_key(self):
        config = {
            "discovery": {"philly_local_sources": {"target_ids": ["WPVI.us"]}},
            "stremio_client_results": {},
        }
        matched = record_client_result.update_config(
            config,
            "wpvi.us",
            "passed",
            "2026-09-22T12:00:00Z",
            "Played in Stremio desktop",
            24,
        )
        self.assertEqual(matched, "WPVI.us")
        self.assertEqual(config["stremio_client_results"]["WPVI.us"]["ttl_hours"], 24)


if __name__ == "__main__":
    unittest.main()
