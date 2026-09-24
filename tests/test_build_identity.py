import datetime as dt
import unittest
from unittest import mock

import build


class BuildIdentityTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "addon": {
                "id": "com.example.stremio",
                "version": "9.8.7",
                "name": "Test TV",
                "description": "Test addon",
            },
            "catalogs": [],
        }
        self.now = dt.datetime(2026, 9, 22, 4, 5, 6, tzinfo=dt.timezone.utc)

    def test_build_info_contains_version_timestamp_and_revision(self):
        with mock.patch.dict(
            build.os.environ,
            {
                "GITHUB_SHA": "1234567890abcdef1234567890abcdef12345678",
                "GITHUB_REPOSITORY": "owner/repo",
                "GITHUB_RUN_ID": "42",
                "GITHUB_RUN_NUMBER": "7",
            },
            clear=False,
        ):
            info = build.make_build_info(self.config, now=self.now)

        self.assertEqual(info["version"], "9.8.7")
        self.assertEqual(info["built_at"], "2026-09-22T04:05:06Z")
        self.assertEqual(info["source_revision"], "1234567890abcdef1234567890abcdef12345678")
        self.assertEqual(info["build_id"], "v9.8.7-20260922T040506Z-1234567890ab")
        self.assertEqual(info["workflow_run_id"], "42")

    def test_manifest_channel_and_stream_share_same_build_identity(self):
        info = {
            "build_id": "v9.8.7-20260922T040506Z-1234567890ab",
            "version": "9.8.7",
            "built_at": "2026-09-22T04:05:06Z",
            "source_revision": "1234567890abcdef",
        }
        manifest = build.build_manifest(self.config, info)
        self.assertEqual(manifest["stremioTvBuild"], info)

        channel = {
            "id": "stremiotv_test",
            "name": "Test Channel",
            "category": "Entertainment",
            "streams": [{"url": "https://example.test/live.m3u8"}],
            "philly": False,
            "epg_matched": False,
            "build_version": info["version"],
            "built_at": info["built_at"],
            "build_id": info["build_id"],
            "build_revision": info["source_revision"],
        }
        meta = build.channel_meta(channel)
        self.assertEqual(meta["stremioTvBuild"]["build_id"], info["build_id"])
        self.assertNotIn(info["build_id"], meta["description"])
        self.assertNotIn(info["built_at"], meta["description"])
        self.assertEqual(meta["stremioTvDiagnostics"]["source_count"], 1)
        self.assertEqual(meta["stremioTvDiagnostics"]["epg_status"], "unmatched")

        stream = {
            "url": "https://example.test/live.m3u8",
            "source": "Test Source",
            "family": "test",
            "quality": "HD",
            "health": {"status": "ok"},
        }
        stream_payload = build.stream_object(stream, 1, info)
        self.assertEqual(stream_payload["stremioTvBuild"]["build_id"], info["build_id"])
        self.assertIn(f"Build {info['build_id']}", stream_payload["description"])


if __name__ == "__main__":
    unittest.main()
