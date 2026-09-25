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

    def test_burn_in_rejects_candidate_that_dies_mid_window(self):
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
                "second_probe_delay_seconds": 60,
                "burn_in": {
                    "enabled": True,
                    "duration_seconds": 60,
                    "interval_seconds": 15,
                },
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
        good_1 = {
            "status": "ok",
            "detail": "Valid HLS playlist + segment",
            "http_status": 200,
            "final_url": "https://example.test/media.m3u8",
            "hls_is_live": True,
            "hls_media_sequence": 100,
            "hls_tail_sha256": "tail-100",
        }
        good_2 = {
            **good_1,
            "hls_media_sequence": 101,
            "hls_tail_sha256": "tail-101",
        }
        failed = {
            "status": "failed",
            "detail": "timed out",
            "latency_ms": 1000,
        }

        with (
            mock.patch.object(build, "_probe_stream", side_effect=[good_1, good_2, failed]),
            mock.patch.object(build, "_load_previous_stream_stability", return_value={}),
            mock.patch.object(build, "_load_previous_channel_state", return_value={}),
            mock.patch.object(build.time, "sleep", return_value=None),
        ):
            healthy, rows, _state = build.probe_candidate_entries([entry], config)

        self.assertEqual(healthy, [])
        health = rows[0]["health"]
        self.assertEqual(health["continuity_failure"], "burn-in-probe-failed")
        self.assertEqual(health["burn_in"]["failed_probe"], 3)
        self.assertEqual(health["burn_in"]["probes_attempted"], 3)
        self.assertFalse(health["burn_in"]["passed"])

    def test_burn_in_accepts_stream_that_survives_all_five_probes(self):
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
                "burn_in": {
                    "enabled": True,
                    "duration_seconds": 60,
                    "interval_seconds": 15,
                },
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
        probes = [
            {
                "status": "ok",
                "detail": "Valid HLS playlist + segment",
                "http_status": 200,
                "final_url": "https://example.test/media.m3u8",
                "hls_is_live": True,
                "hls_media_sequence": 100 + index,
                "hls_tail_sha256": f"tail-{100 + index}",
            }
            for index in range(5)
        ]

        with (
            mock.patch.object(build, "_probe_stream", side_effect=probes),
            mock.patch.object(build, "_load_previous_stream_stability", return_value={}),
            mock.patch.object(build, "_load_previous_channel_state", return_value={}),
            mock.patch.object(build.time, "sleep", return_value=None),
        ):
            healthy, rows, _state = build.probe_candidate_entries([entry], config)

        self.assertEqual(len(healthy), 1)
        health = rows[0]["health"]
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["burn_in"]["planned_probes"], 5)
        self.assertEqual(health["burn_in"]["probes_attempted"], 5)
        self.assertEqual(health["burn_in"]["elapsed_seconds"], 60)
        self.assertTrue(health["burn_in"]["passed"])
        self.assertIn("Passed 60s burn-in (5 probes)", health["detail"])

    def test_established_stable_url_uses_two_probe_validation_not_burn_in(self):
        entry = {
            "name": "CNN",
            "tvg_id": "CNN.us",
            "source": "Established source",
            "family": "test",
            "url": "https://example.test/cnn.m3u8",
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
                "second_probe_delay_seconds": 60,
                "burn_in": {
                    "enabled": True,
                    "scope": "promotion-only",
                    "duration_seconds": 60,
                    "interval_seconds": 15,
                    "established_classifications": ["Stable", "Backup"],
                },
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
        stable_key = build._stream_stability_key(entry)
        previous = {
            "streams": {
                stable_key: {
                    "classification": "Stable",
                    "history": [True, True, True, True, True],
                    "consecutive_failures": 0,
                    "last_result": "pass",
                }
            }
        }
        probe_1 = {
            "status": "ok",
            "detail": "Valid HLS playlist + segment",
            "http_status": 200,
            "final_url": "https://example.test/cnn-media.m3u8",
            "hls_is_live": True,
            "hls_media_sequence": 100,
            "hls_tail_sha256": "tail-100",
        }
        probe_2 = {
            **probe_1,
            "hls_media_sequence": 104,
            "hls_tail_sha256": "tail-104",
        }

        with (
            mock.patch.object(build, "_probe_stream", side_effect=[probe_1, probe_2]) as probe,
            mock.patch.object(build, "_load_previous_stream_stability", return_value=previous),
            mock.patch.object(build, "_load_previous_channel_state", return_value={}),
            mock.patch.object(build.time, "sleep", return_value=None) as sleep,
        ):
            healthy, rows, _state = build.probe_candidate_entries([entry], config)

        self.assertEqual(len(healthy), 1)
        health = rows[0]["health"]
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["validation_mode"], "established-two-probe")
        self.assertEqual(health["prior_classification"], "Stable")
        self.assertNotIn("burn_in", health)
        self.assertEqual(probe.call_count, 2)
        self.assertEqual(sleep.call_count, 4)

    def test_direct_media_decoder_rejects_short_stream(self):
        settings = {
            "enabled": True,
            "duration_seconds": 12,
            "min_decoded_seconds": 10,
            "fps": 2,
            "timeout_seconds": 20,
            "detect_repeated_clips": True,
        }
        output = "\n".join(
            f"0, {index}, {index}, 1, 1, {index + 1:032x}"
            for index in range(8)
        )
        completed = mock.Mock(stdout=output, stderr="Stream ends prematurely", returncode=0)
        with (
            mock.patch.object(build.shutil, "which", return_value="/usr/bin/ffmpeg"),
            mock.patch.object(build.subprocess, "run", return_value=completed),
        ):
            result = build._validate_direct_media_survival(
                {"url": "http://example.test/live", "headers": {}},
                settings,
            )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["continuity_failure"], "direct-media-short-decode")
        self.assertEqual(result["direct_media_survival"]["decoded_seconds"], 4.0)
        self.assertFalse(result["direct_media_survival"]["passed"])

    def test_direct_media_decoder_accepts_ten_seconds_of_video(self):
        settings = {
            "enabled": True,
            "duration_seconds": 12,
            "min_decoded_seconds": 10,
            "fps": 2,
            "timeout_seconds": 20,
            "detect_repeated_clips": True,
        }
        output = "\n".join(
            f"0, {index}, {index}, 1, 1, {index + 1:032x}"
            for index in range(24)
        )
        completed = mock.Mock(stdout=output, stderr="", returncode=0)
        with (
            mock.patch.object(build.shutil, "which", return_value="/usr/bin/ffmpeg"),
            mock.patch.object(build.subprocess, "run", return_value=completed),
        ):
            result = build._validate_direct_media_survival(
                {"url": "http://example.test/live", "headers": {}},
                settings,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["direct_media_survival"]["decoded_seconds"], 12.0)
        self.assertTrue(result["direct_media_survival"]["passed"])

    def test_direct_media_decoder_detects_replayed_clip(self):
        settings = {
            "enabled": True,
            "duration_seconds": 12,
            "min_decoded_seconds": 10,
            "fps": 2,
            "timeout_seconds": 20,
            "detect_repeated_clips": True,
            "repeat_min_seconds": 2,
            "repeat_max_seconds": 4,
        }
        clip = [f"{index + 1:032x}" for index in range(4)]
        hashes = clip + clip + [f"{index + 10:032x}" for index in range(20)]
        output = "\n".join(
            f"0, {index}, {index}, 1, 1, {digest}"
            for index, digest in enumerate(hashes)
        )
        completed = mock.Mock(stdout=output, stderr="", returncode=0)
        with (
            mock.patch.object(build.shutil, "which", return_value="/usr/bin/ffmpeg"),
            mock.patch.object(build.subprocess, "run", return_value=completed),
        ):
            result = build._validate_direct_media_survival(
                {"url": "http://example.test/live", "headers": {}},
                settings,
            )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["continuity_failure"], "direct-media-repeated-clip")
        self.assertEqual(result["direct_media_survival"]["repeat"]["clip_seconds"], 2.0)

    def test_direct_decoder_gate_marks_candidate_failed_before_stability_scoring(self):
        entry = {
            "name": "NBC Sports Philadelphia",
            "tvg_id": "NBCSportsPhiladelphia.us",
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
                "double_probe": False,
                "direct_media_survival": {"enabled": True, "max_workers": 1},
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
            "media_sample_sha256": "abc123",
            "media_sample_bytes": 65536,
        }
        gate_result = {
            "status": "failed",
            "detail": "Direct media decoded only 3.0s; requires 10s",
            "continuity_failure": "direct-media-short-decode",
            "direct_media_survival": {
                "decoded_seconds": 3.0,
                "passed": False,
            },
        }
        with (
            mock.patch.object(build, "_probe_stream", return_value=probe_result),
            mock.patch.object(build, "_validate_direct_media_survival", return_value=gate_result),
            mock.patch.object(build, "_load_previous_stream_stability", return_value={}),
            mock.patch.object(build, "_load_previous_channel_state", return_value={}),
        ):
            healthy, rows, state = build.probe_candidate_entries([entry], config)

        self.assertEqual(healthy, [])
        self.assertEqual(rows[0]["health"]["continuity_failure"], "direct-media-short-decode")
        key = build._stream_stability_key(entry)
        self.assertEqual(state["streams"][key]["last_result"], "fail")
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
