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
            "attempts": 1,
            "required_passes": 1,
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
        self.assertEqual(result["continuity_failure"], "direct-media-insufficient-survival")
        self.assertEqual(result["direct_media_survival"]["attempts"][0]["decoded_seconds"], 4.0)
        self.assertFalse(result["direct_media_survival"]["passed"])

    def test_direct_media_decoder_accepts_ten_seconds_of_video(self):
        settings = {
            "enabled": True,
            "duration_seconds": 12,
            "min_decoded_seconds": 10,
            "fps": 2,
            "timeout_seconds": 20,
            "detect_repeated_clips": True,
            "attempts": 1,
            "required_passes": 1,
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
        self.assertEqual(result["direct_media_survival"]["attempts"][0]["decoded_seconds"], 12.0)
        self.assertEqual(result["direct_media_survival"]["passed_attempts"], 1)
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
            "attempts": 1,
            "required_passes": 1,
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
        self.assertEqual(result["direct_media_survival"]["attempts"][0]["repeat"]["clip_seconds"], 2.0)

    def test_direct_media_decoder_requires_two_of_three_attempts(self):
        settings = {
            "enabled": True,
            "duration_seconds": 12,
            "min_decoded_seconds": 10,
            "fps": 2,
            "timeout_seconds": 20,
            "detect_repeated_clips": True,
            "attempts": 3,
            "required_passes": 2,
        }
        short_output = "\n".join(
            f"0, {index}, {index}, 1, 1, {index + 1:032x}"
            for index in range(8)
        )
        good_output = "\n".join(
            f"0, {index}, {index}, 1, 1, {index + 100:032x}"
            for index in range(24)
        )
        short = mock.Mock(stdout=short_output, stderr="", returncode=0)
        good_1 = mock.Mock(stdout=good_output, stderr="", returncode=0)
        good_2 = mock.Mock(stdout=good_output, stderr="", returncode=0)

        with (
            mock.patch.object(build.shutil, "which", return_value="/usr/bin/ffmpeg"),
            mock.patch.object(
                build.subprocess,
                "run",
                side_effect=[short, good_1, good_2],
            ) as run,
        ):
            result = build._validate_direct_media_survival(
                {"url": "http://example.test/live", "headers": {}},
                settings,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["direct_media_survival"]["passed_attempts"], 2)
        self.assertEqual(result["direct_media_survival"]["attempts_completed"], 3)
        self.assertEqual(run.call_count, 3)

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
            "detail": "Direct media passed 0/2 decoder attempts; requires 2",
            "continuity_failure": "direct-media-insufficient-survival",
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
        self.assertEqual(rows[0]["health"]["continuity_failure"], "direct-media-insufficient-survival")
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

    def test_primary_playback_qa_promotes_first_passing_backup(self):
        channels = [{
            "id": "ch1",
            "name": "Example",
            "tvg_id": "Example.us",
            "streams": [
                {"url": "https://bad.test/a.m3u8", "source": "bad", "family": "bad"},
                {"url": "https://good.test/b.m3u8", "source": "good", "family": "good"},
                {"url": "https://later.test/c.m3u8", "source": "later", "family": "later"},
            ],
        }]
        config = {
            "stream_health": {
                "primary_playback_qa": {
                    "enabled": True,
                    "duration_seconds": 10,
                    "min_decoded_seconds": 8,
                    "fps": 2,
                    "max_workers": 1,
                }
            }
        }
        results = [
            {
                "status": "failed",
                "detail": "decode failed",
                "continuity_failure": "primary-playback-decode-failed",
                "primary_playback_qa": {"passed": False},
            },
            {
                "status": "ok",
                "detail": "decode passed",
                "primary_playback_qa": {"passed": True},
            },
        ]
        with mock.patch.object(
            build,
            "_validate_primary_playback_stream",
            side_effect=results,
        ):
            kept, report = build.apply_primary_playback_qa(channels, config)

        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["streams"][0]["source"], "good")
        self.assertEqual(
            [stream["source"] for stream in kept[0]["streams"]],
            ["good", "later"],
        )
        self.assertEqual(report["summary"]["backup_promoted"], 1)
        self.assertEqual(report["summary"]["channels_dropped"], 0)

    def test_primary_playback_qa_drops_channel_when_every_selected_stream_fails(self):
        channels = [{
            "id": "ch1",
            "name": "Example",
            "tvg_id": "Example.us",
            "streams": [
                {"url": "https://bad.test/a.m3u8", "source": "a", "family": "a"},
                {"url": "https://bad.test/b.m3u8", "source": "b", "family": "b"},
            ],
        }]
        config = {
            "stream_health": {
                "primary_playback_qa": {
                    "enabled": True,
                    "duration_seconds": 10,
                    "min_decoded_seconds": 8,
                    "fps": 2,
                    "max_workers": 1,
                }
            }
        }
        failure = {
            "status": "failed",
            "detail": "no decoded video",
            "continuity_failure": "primary-playback-decode-failed",
            "primary_playback_qa": {"passed": False},
        }
        with mock.patch.object(
            build,
            "_validate_primary_playback_stream",
            side_effect=[failure, failure],
        ):
            kept, report = build.apply_primary_playback_qa(channels, config)

        self.assertEqual(kept, [])
        self.assertEqual(report["summary"]["channels_dropped"], 1)
        self.assertEqual(report["channels"][0]["action"], "dropped-channel")


if __name__ == "__main__":
    unittest.main()
