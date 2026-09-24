import unittest
from unittest import mock

import build


class PlaybackContinuityTests(unittest.TestCase):
    def test_detects_immediately_repeated_hls_segment_sequence(self):
        segments = [
            "seg-100.ts",
            "seg-101.ts",
            "seg-100.ts",
            "seg-101.ts",
            "seg-102.ts",
        ]

        repeated = build._repeated_hls_segment_sequence(segments)

        self.assertIsNotNone(repeated)
        self.assertEqual(repeated["sequence_width"], 2)
        self.assertEqual(repeated["sequence"], ["seg-100.ts", "seg-101.ts"])

    def test_normal_hls_sequence_is_not_flagged(self):
        segments = ["seg-100.ts", "seg-101.ts", "seg-102.ts", "seg-103.ts"]
        self.assertIsNone(build._repeated_hls_segment_sequence(segments))

    def test_stalled_live_hls_window_fails_second_probe(self):
        entry = {
            "name": "HGTV",
            "tvg_id": "HGTV.us",
            "source": "Test HLS feed",
            "family": "test",
            "url": "https://example.test/live.m3u8",
            "headers": {},
        }
        config = {
            "stream_health": {
                "enabled": True,
                "require_passed_only": True,
                "timeout_seconds": 1,
                "max_workers": 1,
                "verify_segment_for_all_candidates": True,
                "double_probe": True,
                "second_probe_delay_seconds": 0,
                "priority_recovery": {"enabled": False},
            },
            "stream_stability": {
                "enabled": True,
                "history_size": 5,
                "retention_builds": 20,
                "dead_source_cooldown_hours": [1, 6, 24],
            },
            "favorites": [],
        }
        probe_result = {
            "status": "ok",
            "detail": "Valid HLS playlist + segment",
            "http_status": 200,
            "final_url": "https://example.test/media.m3u8",
            "latency_ms": 10,
            "hls_is_live": True,
            "hls_media_sequence": 100,
            "hls_tail_sha256": "same-tail",
            "hls_segment_count": 6,
        }

        with (
            mock.patch.object(build, "_probe_stream", return_value=probe_result),
            mock.patch.object(build, "_load_previous_stream_stability", return_value={}),
            mock.patch.object(build, "_load_previous_channel_state", return_value={}),
            mock.patch.object(build.time, "sleep", return_value=None),
        ):
            healthy, rows, _state = build.probe_candidate_entries([entry], config)

        self.assertEqual(healthy, [])
        self.assertEqual(rows[0]["health"]["status"], "failed")
        self.assertEqual(
            rows[0]["health"]["continuity_failure"],
            "stalled-live-hls-window",
        )

    def test_identical_direct_media_samples_fail_second_probe(self):
        entry = {
            "name": "HGTV",
            "tvg_id": "HGTV.us",
            "source": "Test direct feed",
            "family": "test",
            "url": "http://example.test/live",
            "headers": {},
        }
        config = {
            "stream_health": {
                "enabled": True,
                "require_passed_only": True,
                "timeout_seconds": 1,
                "max_workers": 1,
                "verify_segment_for_all_candidates": True,
                "double_probe": True,
                "second_probe_delay_seconds": 0,
                "priority_recovery": {"enabled": False},
            },
            "stream_stability": {
                "enabled": True,
                "history_size": 5,
                "retention_builds": 20,
                "dead_source_cooldown_hours": [1, 6, 24],
            },
            "favorites": [],
        }
        probe_result = {
            "status": "ok",
            "detail": "Reachable direct media URL",
            "http_status": 200,
            "final_url": "http://example.test/live",
            "latency_ms": 10,
            "media_sample_sha256": "abc123",
            "media_sample_bytes": 65536,
        }

        with (
            mock.patch.object(build, "_probe_stream", return_value=probe_result),
            mock.patch.object(build, "_load_previous_stream_stability", return_value={}),
            mock.patch.object(build, "_load_previous_channel_state", return_value={}),
            mock.patch.object(build.time, "sleep", return_value=None),
        ):
            healthy, rows, _state = build.probe_candidate_entries([entry], config)

        self.assertEqual(healthy, [])
        self.assertEqual(rows[0]["health"]["status"], "failed")
        self.assertEqual(
            rows[0]["health"]["continuity_failure"],
            "identical-direct-media-sample",
        )


if __name__ == "__main__":
    unittest.main()
