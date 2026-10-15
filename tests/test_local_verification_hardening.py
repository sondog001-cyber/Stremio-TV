"""Manual local approval cannot hide observed playback defects or spread by tag."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import build
from deployment_guard import evaluate_deployment_guard


class LocalVerificationHardeningTests(unittest.TestCase):
    def approved(self):
        row = {"tvg_id": "Example.us", "url": "https://media.example/test.m3u8",
               "family": "tvnow", "headers": {"Referer": "https://tvnow.st/"},
               "local_verified_override": True}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manual.json").write_text(json.dumps({"streams": [row]}))
            return build.load_manual_streams({"manual_sources_file": "manual.json"}, root / "config.json")[0]

    def failure(self, continuity="direct-media-insufficient-survival", **extra):
        return {"status": "failed", "detail": "Decoder timed out", "continuity_failure": continuity,
                "decoder_failure_class": "timeout", "direct_media_survival": {
                    "passed": False, "attempts": [{"passed": False, "decoded_frames": 0,
                    "decoded_seconds": 0, "failure": "timeout", "repeat": None}]}, **extra}

    def test_exact_manual_approval_retains_underlying_failed_ci_evidence(self):
        stream = self.approved()
        failure = self.failure()
        with mock.patch.object(build, "_validate_direct_media_survival", return_value=failure):
            result = build._validate_primary_playback_stream(stream, {})
        self.assertEqual(result["status"], "ok")
        qa = result["primary_playback_qa"]
        self.assertTrue(qa["local_verified_override"])
        self.assertTrue(qa["publication_accepted"])
        self.assertFalse(qa["passed"])
        self.assertEqual(qa["ci_playback_status"], "failed")
        self.assertEqual(qa["ci_direct_media_survival"], failure["direct_media_survival"])

    def test_boolean_tag_or_mutated_approved_record_cannot_bypass_decoder(self):
        original = self.approved()
        variants = []
        for key, value in (("url", "https://unapproved.example/other.m3u8"),
                           ("tvg_id", "Other.us"), ("family", "unrelated"),
                           ("headers", {"Referer": "https://other.example/"})):
            changed = copy.deepcopy(original)
            changed[key] = value
            variants.append(changed)
        tagged_only = copy.deepcopy(original)
        tagged_only.pop("_local_verification_record")
        variants.append(tagged_only)
        with mock.patch.object(build, "_validate_direct_media_survival", return_value=self.failure()):
            for stream in variants:
                with self.subTest(stream=stream):
                    self.assertFalse(build._approved_local_verification(stream))
                    self.assertEqual(build._validate_primary_playback_stream(stream, {})["status"], "failed")

    def test_all_existing_explicit_approvals_survive_normal_pipeline_identity_and_safety(self):
        config = json.loads((build.ROOT / "config.json").read_text())
        rows = build.load_manual_streams(config, build.ROOT / "config.json")
        approved = [row for row in rows if row.get("local_verified_override")]
        self.assertEqual(len(approved), 19)
        self.assertEqual(sum(row["family"] == "tvnow" for row in approved), 17)
        approved = build.canonicalize_approved_sources(approved, config)
        approved, rejected = build.apply_safety_controls(approved, config)
        self.assertFalse(rejected)
        self.assertEqual(len(approved), 19)
        self.assertTrue(all(build._approved_local_verification(row) for row in approved))

    def test_repeats_frozen_playback_and_stalled_health_cannot_be_overridden(self):
        for continuity in ("direct-media-repeated-clip", "repeated-hls-segments",
                           "stalled-live-hls-window", "identical-direct-media-sample", "frozen-video"):
            with self.subTest(continuity=continuity):
                stream = self.approved()
                failure = self.failure(continuity)
                with mock.patch.object(build, "_validate_direct_media_survival", return_value=failure):
                    self.assertEqual(build._validate_primary_playback_stream(stream, {})["status"], "failed")
                stream["health"] = failure
                self.assertFalse(build._approved_local_verification(stream))
        failure = self.failure()
        failure["direct_media_survival"]["attempts"][0]["repeat"] = {"clip_seconds": 3}
        with mock.patch.object(build, "_validate_direct_media_survival", return_value=failure):
            self.assertEqual(build._validate_primary_playback_stream(self.approved(), {})["status"], "failed")

    def test_looping_approved_primary_yields_to_normal_passing_backup(self):
        primary = self.approved()
        backup = {"url": "https://backup.example/stream.m3u8", "family": "other"}
        channels = [{"id": "example", "tvg_id": "Example.us", "streams": [primary, backup]}]
        config = {"stream_health": {"primary_playback_qa": {"enabled": True, "max_workers": 1}}}
        passed = {"status": "ok", "direct_media_survival": {"passed": True}}
        with mock.patch.object(build, "_validate_direct_media_survival", side_effect=[self.failure("direct-media-repeated-clip"), passed]):
            kept, report = build.apply_primary_playback_qa(channels, config)
        self.assertEqual(kept[0]["streams"][0]["url"], backup["url"])
        self.assertEqual(report["summary"]["backup_promoted"], 1)
        self.assertEqual(report["channels"][0]["attempts"][0]["status"], "failed")

    def test_manual_override_still_obeys_safety_kill_switches_and_deployment_floor(self):
        stream = self.approved()
        for settings in ({"disabled_urls": [stream["url"]]}, {"disabled_channels": [stream["tvg_id"]]}):
            kept, rejected = build.apply_safety_controls([stream], {"safety_controls": settings})
            self.assertEqual(kept, [])
            self.assertEqual(len(rejected), 1)
        stream["headers"]["Authorization"] = "Bearer test-only"
        kept, rejected = build.apply_safety_controls([stream], {})
        self.assertEqual(kept, [])
        config = json.loads((build.ROOT / "config.json").read_text())
        self.assertTrue(evaluate_deployment_guard(config, {"channels": 1}, [{"tvg_id": "Example.us", "streams": [stream]}]))

    def test_tvnow_diagnostics_never_borrow_decoder_success_from_another_url(self):
        failed, good = "https://media.example/failed", "https://media.example/good"
        health = [{"tvg_id": "Example.us", "url": url, "family": "tvnow", "health": {"status": "ok"}} for url in (failed, good)]
        ordering = [{"tvg_id": "Example.us", "streams": [{"url": good, "family": "tvnow", "role": "Primary"}]}]
        qa = {"channels": [{"tvg_id": "Example.us", "attempts": [
            {"url": failed, "family": "tvnow", "status": "failed", "continuity_failure": "primary-playback-repeated-clip"},
            {"url": good, "family": "tvnow", "status": "ok"}]}]}
        report = build.build_tvnow_qa_diagnostics(health, ordering, qa)
        first, second = report["channels"]
        self.assertFalse(first["published"])
        self.assertFalse(first["normal_playback_passed"])
        self.assertEqual(first["ci_continuity_failure"], "primary-playback-repeated-clip")
        self.assertTrue(second["published"])
        self.assertTrue(second["normal_playback_passed"])


if __name__ == "__main__":
    unittest.main()
