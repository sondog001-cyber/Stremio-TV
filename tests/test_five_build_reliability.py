import unittest
from unittest import mock

import build


class DecoderHeaderTests(unittest.TestCase):
    def test_ffmpeg_http_headers_use_real_crlf(self):
        entry = {
            "url": "https://example.test/master.m3u8",
            "headers": {"Referer": "https://tvnow.st/", "Origin": "https://tvnow.st"},
        }
        settings = {
            "enabled": True, "duration_seconds": 2, "min_decoded_seconds": 1,
            "fps": 2, "attempts": 1, "required_passes": 1,
        }
        completed = mock.Mock(returncode=1, stdout="", stderr="Invalid data found")
        with mock.patch("build.shutil.which", return_value="/usr/bin/ffmpeg"), \
             mock.patch("build.subprocess.run", return_value=completed) as run:
            result = build._validate_direct_media_survival(entry, settings)
        args = run.call_args.args[0]
        header = args[args.index("-headers") + 1]
        self.assertEqual(
            header,
            "Referer: https://tvnow.st/\r\nOrigin: https://tvnow.st\r\n",
        )
        self.assertNotIn("\\r\\n", header)
        self.assertEqual(result["status"], "failed")


class FiveBuildReliabilityTests(unittest.TestCase):
    def test_window_and_override_truth_are_preserved(self):
        history = [
            {"build_id": str(i), "published": 90, "published_tvg_ids": ["DiscoveryChannel.us"],
             "lost_ids": [], "recovered_ids": []}
            for i in range(1, 5)
        ]
        channels = [{
            "tvg_id": "DiscoveryChannel.us", "name": "Discovery",
            "category": "Entertainment", "philly": False,
        }]
        changes = {
            "expected_channels": 111,
            "lost_this_build": [{"channel_id": "History.us"}],
            "recovered_this_build": [],
        }
        qa = {"channels": [{
            "tvg_id": "DiscoveryChannel.us",
            "attempts": [{
                "status": "ok", "family": "tvnow",
                "qa": {"local_verified_override": True},
            }, {
                "status": "ok", "family": "other",
                "qa": {},
            }],
        }]}
        redundancy = {"summary": {"with_independent_backup": 0, "single_stream": 1}, "channels": [{
            "tvg_id": "DiscoveryChannel.us", "name": "Discovery",
            "has_independent_backup": False, "stream_count": 1,
            "primary_family": "tvnow", "provider_hosts": ["wonvt.st"],
            "locally_verified_count": 1,
        }]}
        tvnow = {"summary": {"normal_health_passed": 1, "rate_limited": 0},
                 "channels": [{"normal_playback_passed": False, "override_used_for_playback": True,
                               "ci_decoder_failure_class": "codec-or-demux"}]}
        missing = {"channels": [{
            "tvg_id": "History.us", "bucket": "failed_probes",
            "candidate_count": 1, "public_search_eligible": True,
            "action": "Repair candidate",
        }]}
        score = build.build_five_build_reliability(
            channels, changes, qa, redundancy, tvnow, missing,
            {"build_id": "5", "built_at": "2026-10-12T10:00:00Z"},
            previous={"history": history},
        )
        self.assertTrue(score["summary"]["five_build_history_complete"])
        self.assertFalse(score["summary"]["five_consecutive_builds_at_least_90"])
        self.assertEqual(score["summary"]["normal_decoder_passes_latest"], 1)
        self.assertEqual(score["summary"]["locally_overridden_playback_attempts_latest"], 1)
        self.assertEqual(score["tvnow_decoder_diagnosis"]["decoder_overrides"], 1)
        self.assertEqual(score["recovery_priorities"][0]["tvg_id"], "History.us")
        self.assertEqual(score["independent_backup_priorities"][0]["primary_family"], "tvnow")


if __name__ == "__main__":
    unittest.main()
