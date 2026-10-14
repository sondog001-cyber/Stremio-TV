"""Strict QA: no local pass permits failed health or video decoder streams."""
from pathlib import Path
from unittest import TestCase, mock
import json
import build

ROOT = Path(__file__).resolve().parents[1]


class FullQANoBypassTests(TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        self.sources = json.loads((ROOT / "manual_sources.json").read_text(encoding="utf-8"))

    def test_no_local_test_catalog_or_local_verified_flags_in_production(self):
        self.assertFalse(self.config["local_test_catalog"]["enabled"])
        self.assertEqual(
            self.config["stream_health"]["primary_playback_qa"]["required_passes"], 2
        )
        self.assertTrue(self.config["stream_health"]["require_passed_only"])
        self.assertTrue(self.config["deployment_guard"]["enabled"])
        self.assertFalse(any("local_verified_override" in item for item in self.sources["streams"]))
        manifest = build.build_manifest(self.config)
        self.assertNotIn("local-test", [c["id"] for c in manifest["catalogs"]])

    def test_legacy_local_verified_tag_cannot_bypass_failed_decoder(self):
        fake = {
            "url": "https://example.test/fail.m3u8",
            "local_verified_override": True,
            "health": {"status": "ok"},
        }
        decoder_failure = {
            "status": "failed", "detail": "0 decoded frames",
            "continuity_failure": "direct-media-short-decode",
            "direct_media_survival": {"passed": False, "attempts": []},
        }
        settings = {"enabled": True, "attempts": 2, "required_passes": 2}
        with mock.patch.object(build, "_validate_direct_media_survival", return_value=decoder_failure) as validate:
            outcome = build._validate_primary_playback_stream(fake, settings)
        validate.assert_called_once()
        self.assertEqual(outcome["status"], "failed")
        self.assertNotEqual(outcome.get("primary_playback_qa", {}).get("passed"), True)

    def test_primary_qa_checks_and_filters_every_backup(self):
        streams = [
            {"source": "primary", "family": "first", "url": "https://stream.test/primary", "health": {"status": "ok"}},
            {"source": "broken-backup", "family": "second", "url": "https://stream.test/broken", "health": {"status": "ok"}},
            {"source": "good-backup", "family": "third", "url": "https://stream.test/good", "health": {"status": "ok"}},
        ]
        channels = [{
            "id": "sample", "name": "Example", "tvg_id": "Example.us",
            "streams": streams,
        }]
        qa_ok = {"status": "ok", "detail": "decoded", "primary_playback_qa": {"passed": True}}
        qa_bad = {"status": "failed", "detail": "no video", "primary_playback_qa": {"passed": False}}
        config = {"stream_health": {"primary_playback_qa": {
            "enabled": True, "max_workers": 1, "controlled_rescue": {"enabled": False}
        }}}
        with mock.patch.object(
            build, "_validate_primary_playback_stream",
            side_effect=[qa_ok, qa_bad, qa_ok],
        ) as probe:
            kept, report = build.apply_primary_playback_qa(channels, config)
        self.assertEqual(probe.call_count, 3)
        self.assertEqual(
            [stream["source"] for stream in kept[0]["streams"]],
            ["primary", "good-backup"],
        )
        self.assertTrue(all(s["primary_playback_qa"]["passed"] for s in kept[0]["streams"]))
        self.assertEqual(report["channels"][0]["failed_streams_removed"], 1)
        self.assertEqual(report["channels"][0]["passing_stream_indexes"], [0, 2])

    def test_primary_qa_promotes_verified_backup_only(self):
        streams = [
            {"source": "bad-primary", "family": "first", "url": "https://stream.test/bad", "health": {"status": "ok"}},
            {"source": "backup", "family": "second", "url": "https://stream.test/good", "health": {"status": "ok"}},
        ]
        config = {"stream_health": {"primary_playback_qa": {
            "enabled": True, "max_workers": 1, "controlled_rescue": {"enabled": False}
        }}}
        with mock.patch.object(build, "_validate_primary_playback_stream", side_effect=[
            {"status": "failed", "primary_playback_qa": {"passed": False}},
            {"status": "ok", "primary_playback_qa": {"passed": True}},
        ]):
            kept, report = build.apply_primary_playback_qa(
                [{"id": "sample", "name": "Example", "tvg_id": "Example.us", "streams": streams}],
                config,
            )
        self.assertEqual([s["source"] for s in kept[0]["streams"]], ["backup"])
        self.assertEqual(report["summary"]["backup_promoted"], 1)
        self.assertEqual(report["channels"][0]["failed_streams_removed"], 1)


if __name__ == "__main__":
    import unittest
    unittest.main()
