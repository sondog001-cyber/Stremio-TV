import unittest

import build


def candidate(tvg_id, url, *, status="failed", detail="HTTP 403 Forbidden", headers=None):
    return {
        "name": tvg_id.split(".", 1)[0],
        "name_raw": tvg_id,
        "tvg_id": tvg_id,
        "family": "test-family",
        "source": "Test Source",
        "url": url,
        "quality": "HD",
        "priority": 10,
        "content_kind": "full-linear",
        "headers": headers or {},
        "health": {
            "status": status,
            "detail": detail,
            "http_status": 403 if "403" in detail else 500,
        },
        "stability": {
            "rank": 3,
            "passes": 0,
            "samples": 3,
            "classification": "Dead",
        },
    }


class LocalTestCatalogTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "addon": {
                "id": "com.example.stremio",
                "version": "1.0.0",
                "name": "Test TV",
                "description": "Test addon",
            },
            "catalogs": [],
            "favorites": [],
            "stream_selection": {
                "target_hd": 2,
                "target_sd": 1,
                "prefer_distinct_families": True,
                "prefer_distinct_provider_hosts": True,
                "primary_family": "test-family",
                "fallback_families": [],
            },
            "local_test_catalog": {
                "enabled": True,
                "id": "local-test",
                "name": "🧪 Local Test — Runner Blocked",
                "max_streams_per_channel": 8,
            },
        }

    def test_manifest_advertises_local_test_catalog(self):
        manifest = build.build_manifest(self.config)

        catalog = next(
            row for row in manifest["catalogs"]
            if row["id"] == "local-test"
        )
        self.assertEqual(catalog["name"], "🧪 Local Test — Runner Blocked")
        extras = {row["name"]: row for row in catalog["extra"]}
        self.assertTrue(extras["genre"]["isRequired"])
        self.assertEqual(extras["genre"]["options"], ["All"])
        self.assertIn("skip", extras)

    def test_build_local_test_channels_only_uses_current_access_failures(self):
        entries = [
            candidate(
                "CBSSportsNetwork.us",
                "https://blocked.example/one.m3u8",
                headers={"Referer": "https://player.example/"},
            ),
            candidate(
                "CBSSportsNetwork.us",
                "https://blocked2.example/two.m3u8",
                detail="Access denied by region",
            ),
            candidate(
                "DiscoveryChannel.us",
                "https://ordinary-fail.example/live.m3u8",
                detail="HTTP 500 Internal Server Error",
            ),
            candidate(
                "HGTV.us",
                "https://cooldown.example/live.m3u8",
                status="cooldown",
                detail="Dead source probe deferred by backoff; last failure: HTTP 403",
            ),
        ]

        channels, report = build.build_local_test_channels(
            entries,
            [],
            self.config,
        )

        self.assertEqual(
            {channel["tvg_id"] for channel in channels},
            {"CBSSportsNetwork.us", "HGTV.us"},
        )
        cbs = next(channel for channel in channels if channel["tvg_id"] == "CBSSportsNetwork.us")
        hgtv = next(channel for channel in channels if channel["tvg_id"] == "HGTV.us")
        self.assertTrue(cbs["name"].startswith("🧪 "))
        self.assertTrue(cbs["id"].startswith("stremiotv_localtest_"))
        self.assertEqual(len(cbs["streams"]), 2)
        self.assertEqual(
            [stream["display_role"] for stream in cbs["streams"]],
            ["LOCAL TEST 1", "LOCAL TEST 2"],
        )
        self.assertTrue(all(stream["local_test"] for stream in cbs["streams"]))
        self.assertEqual(len(hgtv["streams"]), 1)
        self.assertEqual(report["summary"]["channels"], 2)
        self.assertEqual(report["summary"]["streams"], 3)

    def test_published_channel_is_not_duplicated_into_local_test(self):
        entries = [
            candidate(
                "CBSSportsNetwork.us",
                "https://blocked.example/one.m3u8",
            )
        ]
        published = [{"tvg_id": "CBSSportsNetwork.us"}]

        channels, report = build.build_local_test_channels(
            entries,
            published,
            self.config,
        )

        self.assertEqual(channels, [])
        self.assertEqual(report["summary"]["channels"], 0)

    def test_local_test_stream_preserves_request_headers(self):
        stream = candidate(
            "CBSSportsNetwork.us",
            "https://blocked.example/one.m3u8",
            headers={
                "Referer": "https://player.example/",
                "Origin": "https://player.example",
            },
        )
        stream["local_test"] = True
        stream["display_role"] = "LOCAL TEST 1"

        obj = build.stream_object(stream, 1)

        self.assertEqual(obj["name"], "LOCAL TEST 1 • HD")
        self.assertTrue(obj["behaviorHints"]["notWebReady"])
        self.assertEqual(
            obj["behaviorHints"]["proxyHeaders"]["request"],
            stream["headers"],
        )
        self.assertIn("LOCAL TEST: runner/geo blocked on GitHub", obj["description"])


if __name__ == "__main__":
    unittest.main()
