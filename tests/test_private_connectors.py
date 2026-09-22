import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import build
import private_connectors


class PrivateConnectorTests(unittest.TestCase):
    def test_hdhomerun_maps_wpsg_by_guide_number(self):
        connector = {
            "type": "hdhomerun",
            "name": "OTA",
            "base_url_env": "TEST_HDHR_URL",
            "channels": [{
                "tvg_id": "WPSG.us",
                "name": "Philly 57",
                "guide_numbers": ["57.1"],
                "philly": True,
            }],
        }
        lineup = json.dumps([{"GuideNumber": "57.1", "GuideName": "WPSG", "URL": "http://tuner.test/auto/v57"}])
        with mock.patch.dict(os.environ, {"TEST_HDHR_URL": "http://tuner.test"}, clear=False):
            rows = private_connectors.resolve_hdhomerun(connector, lambda url: lineup)
        self.assertEqual(rows[0]["tvg_id"], "WPSG.us")
        self.assertEqual(rows[0]["url"], "http://tuner.test/auto/v57")

    def test_provider_maps_nbc_sports_plus_without_committing_auth(self):
        connector = {
            "type": "provider-m3u",
            "name": "Provider",
            "playlist_url_env": "TEST_PROVIDER_URL",
            "authorization_env": "TEST_PROVIDER_AUTH",
            "forward_authorization": False,
            "channels": [{
                "tvg_id": "NBCSportsPhiladelphiaPlus.us",
                "match_ids": ["NBCSportsPhiladelphiaPlus.us"],
            }],
        }
        playlist = '#EXTM3U\n#EXTINF:-1 tvg-id="NBCSportsPhiladelphiaPlus.us",NBCSP+\nhttps://provider.test/plus.m3u8\n'

        def fetch(url, headers=None):
            self.assertEqual(headers, {"Authorization": "Bearer secret"})
            return playlist

        with mock.patch.dict(os.environ, {
            "TEST_PROVIDER_URL": "https://provider.test/lineup.m3u",
            "TEST_PROVIDER_AUTH": "Bearer secret",
        }, clear=False):
            rows = private_connectors.resolve_provider_m3u(connector, fetch)
        self.assertEqual(rows[0]["tvg_id"], "NBCSportsPhiladelphiaPlus.us")
        self.assertEqual(rows[0]["headers"], {})

    def test_public_actions_build_refuses_private_overlay(self):
        config = {"curation": {"philly_allow": ["WPSG.us"], "national_allow": []}}
        with mock.patch.dict(os.environ, {
            "GITHUB_ACTIONS": "true",
            "STREMIO_TV_PRIVATE_SOURCES_FILE": "private_sources.generated.json",
        }, clear=False):
            with self.assertRaises(RuntimeError):
                build.load_private_connector_streams(config, Path("config.json"))

    def test_local_build_loads_only_curated_private_ids(self):
        config = {"curation": {"philly_allow": ["WPSG.us"], "national_allow": []}}
        payload = {"streams": [
            {"tvg_id": "WPSG.us", "url": "http://tuner.test/wpsg", "name": "WPSG"},
            {"tvg_id": "Other.us", "url": "http://tuner.test/other", "name": "Other"},
        ]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.dict(os.environ, {
                "GITHUB_ACTIONS": "false",
                "STREMIO_TV_PRIVATE_SOURCES_FILE": str(path),
            }, clear=False):
                rows = build.load_private_connector_streams(config, Path(directory) / "config.json")
        self.assertEqual([row["tvg_id"] for row in rows], ["WPSG.us"])
        self.assertTrue(rows[0]["private_connector"])


if __name__ == "__main__":
    unittest.main()
