import json
import unittest
from unittest import mock

import build


def minimal_config():
    return {
        "curation": {
            "enabled": True,
            "philly_allow": [],
            "national_allow": ["CNN.us", "FXX.us"],
            "approved_unverified_families": ["shovo", "aria-tv", "iptv-org-issue"],
            "approved_source_aliases": {"FXX.us": ["FXX"]},
        },
        "discovery": {
            "enabled": True,
            "targeted_source_families": {
                "enabled": True,
                "sources": [
                    {
                        "name": "Test Shovo",
                        "family": "shovo",
                        "format": "m3u",
                        "url": "https://example.test/us.m3u",
                        "priority": 8,
                    }
                ],
            },
            "iptv_org_issues": {
                "enabled": True,
                "targets": [
                    {"tvg_id": "FXX.us", "name": "FXX", "aliases": ["FXX"]}
                ],
            },
        },
    }


class TargetedScannerTests(unittest.TestCase):
    def setUp(self):
        build._PREVIOUS_CHANNEL_STATE_CACHE = None

    def test_aria_parser_skips_upstream_not_working_rows(self):
        text = "\n".join(
            [
                '| 1 | FXX | [>](https://example.test/fxx.m3u8) | <img src="https://example.test/fxx.png"/> | &nbsp; | stable |',
                '| 2 | CNN | [>](https://example.test/cnn.m3u8) | <img src="https://example.test/cnn.png"/> | &nbsp; | not-working |',
            ]
        )
        entries, scanned = build._parse_aria_markdown(
            text,
            {"name": "aria US", "family": "aria-tv"},
        )
        self.assertEqual(scanned, 2)
        self.assertEqual([entry["name"] for entry in entries], ["FXX"])
        self.assertEqual(entries[0]["source_status"], "stable")

    def test_targeted_family_retains_only_remaining_exact_id(self):
        config = minimal_config()
        existing = [
            {
                "name": "CNN",
                "name_raw": "CNN",
                "tvg_id": "CNN.us",
                "url": "https://existing.test/cnn.m3u8",
                "source": "Existing",
                "family": "iptv-org",
                "quality": "HD",
            }
        ]
        playlist = "\n".join(
            [
                "#EXTM3U",
                '#EXTINF:-1 tvg-id="CNN.us",CNN',
                "https://new.test/cnn.m3u8",
                '#EXTINF:-1 tvg-id="FXX.us",FXX',
                "https://new.test/fxx.m3u8",
            ]
        )
        with mock.patch.object(build, "_load_previous_channel_state", return_value={}), mock.patch.object(
            build,
            "_fetch_public_text",
            return_value=(playlist, "https://example.test/us.m3u"),
        ):
            entries, rows, targets = build.discover_targeted_source_families(config, existing)

        self.assertEqual(targets, ["FXX.us"])
        self.assertEqual([entry["tvg_id"] for entry in entries], ["FXX.us"])
        family_row = next(row for row in rows if row.get("kind") == "targeted-source-family")
        self.assertEqual(family_row["records_scanned"], 2)
        self.assertEqual(family_row["candidates_found"], 1)

    def test_iptv_org_removals_are_diagnostics_not_candidates(self):
        config = minimal_config()
        issues = [
            {
                "number": 101,
                "title": "Add: FXX",
                "body": "https://example.test/fxx.m3u8",
                "html_url": "https://github.com/iptv-org/iptv/issues/101",
                "labels": [{"name": "streams:add"}, {"name": "check:passed"}],
            },
            {
                "number": 102,
                "title": "Broken: FXX",
                "body": "https://example.test/dead-fxx.m3u8",
                "html_url": "https://github.com/iptv-org/iptv/issues/102",
                "labels": [{"name": "streams:remove"}, {"name": "check:passed"}],
            },
        ]
        with mock.patch.object(
            build,
            "_fetch_public_text",
            return_value=(json.dumps(issues), "https://api.github.test/issues"),
        ):
            entries, rows = build.discover_iptv_org_passed_issues(config, ["FXX.us"])

        self.assertEqual([entry["url"] for entry in entries], ["https://example.test/fxx.m3u8"])
        self.assertTrue(any(row.get("status") == "removal-signal" for row in rows))


if __name__ == "__main__":
    unittest.main()
