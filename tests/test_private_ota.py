"""Offline tests for the private, direct-to-HDHomeRun Philadelphia OTA adapter."""
import json
import os
import unittest
from pathlib import Path
from unittest import mock

import private_ota

ROOT = Path(__file__).resolve().parents[1]


class PrivateOTATests(unittest.TestCase):
    def setUp(self):
        self.mapping = json.loads((ROOT / "private_ota.example.json").read_text())
        self.base = "http://192.168.50.22"
        self.stations = [
            {"GuideNumber": "3.1", "GuideName": "CBS3", "URL": self.base + ":5004/auto/v3.1"},
            {"GuideNumber": "10.1", "GuideName": "NBC10", "URL": self.base + ":5004/auto/v10.1"},
            {"GuideNumber": "6.1", "GuideName": "6ABC", "URL": self.base + ":5004/auto/v6.1"},
            {"GuideNumber": "17.1", "GuideName": "PHL17", "URL": self.base + ":5004/auto/v17.1"},
            {"GuideNumber": "57.1", "GuideName": "PHL57", "URL": self.base + ":5004/auto/v57.1"},
        ]

    def test_all_five_original_affiliates_map_to_direct_tuner_urls(self):
        output = private_ota.compile_overlay(self.stations, self.mapping, self.base)
        self.assertEqual({x["tvg_id"] for x in output["streams"]}, set(private_ota.ALLOWED_IDS))
        self.assertEqual(len(output["streams"]), 5)
        self.assertEqual(output["streams"][0]["family"], "private-connector")
        self.assertEqual(output["streams"][0]["headers"], {})
        self.assertEqual(output["streams"][0]["content_kind"], "full-linear")
        self.assertTrue(all(x["url"].startswith(self.base + ":5004/auto/v") for x in output["streams"]))

    def test_rejects_public_ip_cloud_server_and_credentials(self):
        for address in (
            "https://192.168.50.22",
            "http://8.8.8.8",
            "http://127.0.0.1",
            "http://10.0.0.1.bad.example",
            "http://192.168.50.22:5004",
            "http://user:pass@192.168.50.22",
            "http://192.168.50.22/config",
            "http://192.168.50.22?secret=1",
            "http://169.254.2.1",
        ):
            with self.subTest(address=address), self.assertRaises(ValueError):
                private_ota.validate_base_url(address)

    def test_accepts_all_rfc1918_ranges(self):
        for address in ("http://10.2.3.4", "http://172.20.3.4", "http://192.168.1.3"):
            self.assertEqual(private_ota.validate_base_url(address), address)

    def test_wrong_station_name_on_correct_channel_number_fails_closed(self):
        rows = [dict(self.stations[0], GuideName="CBS News Philadelphia FAST")]
        output = private_ota.compile_overlay(rows, self.mapping, self.base)
        self.assertEqual(output["streams"], [])
        self.assertEqual(output["ota_mapping_status"][0]["status"], "not_found")

    def test_name_match_but_wrong_number_fails_closed(self):
        rows = [dict(self.stations[0], GuideNumber="3.2")]
        output = private_ota.compile_overlay(rows, self.mapping, self.base)
        self.assertEqual(output["streams"], [])

    def test_wrong_tuner_host_and_public_redirect_fail_closed(self):
        for url in (
            "http://192.168.50.23:5004/auto/v3.1",
            "http://8.8.8.8:5004/auto/v3.1",
            "http://192.168.50.22:5004/auto/v3.2",
            "http://192.168.50.22:5004/live/3.1",
            "http://192.168.50.22:5004/auto/v3.1?token=abc",
            "https://192.168.50.22:5004/auto/v3.1",
            "http://user:password@192.168.50.22:5004/auto/v3.1",
        ):
            with self.subTest(url=url):
                o = private_ota.compile_overlay([dict(self.stations[0], URL=url)], self.mapping, self.base)
                self.assertEqual(o["streams"], [])
                self.assertEqual(o["ota_mapping_status"][0]["status"], "invalid_or_external_stream_url")

    def test_drm_tag_disqualified(self):
        o = private_ota.compile_overlay([dict(self.stations[0], Tags="favorite, drm")], self.mapping, self.base)
        self.assertEqual(o["streams"], [])
        self.assertEqual(o["ota_mapping_status"][0]["status"], "drm_protected")

    def test_multiple_matches_ambiguous_not_first_win(self):
        row = self.stations[0]
        o = private_ota.compile_overlay([row, row], self.mapping, self.base)
        self.assertEqual(o["streams"], [])
        self.assertEqual(o["ota_mapping_status"][0]["status"], "ambiguous")

    def test_only_approved_ids_and_distinct_channels(self):
        for tid in ("ESPN.us", "WPSG.us@West"):
            mapping = {"channels": [{"tvg_id": tid, "guide_numbers": ["3.1"], "guide_names": ["CBS3"]}]}
            with self.subTest(tvg_id=tid), self.assertRaises(ValueError):
                private_ota.compile_overlay(self.stations, mapping, self.base)

    def test_public_actions_hard_stop(self):
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=False):
            with self.assertRaises(RuntimeError):
                private_ota._secure_local_only()

    def test_refuse_non_gitignored_output_filename(self):
        with self.assertRaises(ValueError):
            private_ota.write_overlay({"streams": []}, ROOT / "manual_sources.json")


if __name__ == "__main__":
    unittest.main()
