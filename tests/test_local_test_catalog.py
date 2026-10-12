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
                "target_ids": [
                    "CBSSportsNetwork.us",
                    "HGTV.us",
                ],
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
        self.assertNotIn("genre", extras)
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

    def test_pinned_published_channel_stays_in_local_test(self):
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

        self.assertEqual([channel["tvg_id"] for channel in channels], ["CBSSportsNetwork.us"])
        self.assertEqual(report["summary"]["channels"], 1)

    def test_unpinned_published_channel_is_not_duplicated(self):
        entries = [
            candidate(
                "DiscoveryChannel.us",
                "https://blocked.example/discovery.m3u8",
            )
        ]
        published = [{"tvg_id": "DiscoveryChannel.us"}]

        channels, report = build.build_local_test_channels(
            entries,
            published,
            self.config,
        )

        self.assertEqual(channels, [])
        self.assertEqual(report["summary"]["channels"], 0)

    def test_previously_tested_families_and_hosts_are_hidden(self):
        self.config["local_test_catalog"]["exclude_families"] = ["daddylive"]
        self.config["local_test_catalog"]["exclude_provider_hosts"] = ["tested.example"]
        entries = [
            {
                **candidate("CBSSportsNetwork.us", "https://newkso.ru/old.m3u8"),
                "family": "daddylive",
            },
            {
                **candidate("CBSSportsNetwork.us", "https://tested.example/old.m3u8"),
                "family": "research-seed",
            },
            {
                **candidate("CBSSportsNetwork.us", "https://fresh.example/new.m3u8"),
                "family": "new-family",
            },
        ]

        channels, report = build.build_local_test_channels(entries, [], self.config)

        self.assertEqual(len(channels), 1)
        self.assertEqual(len(channels[0]["streams"]), 1)
        self.assertEqual(channels[0]["streams"][0]["url"], "https://fresh.example/new.m3u8")
        self.assertEqual(report["summary"]["excluded_tested_streams"], 2)


    def test_initially_healthy_missing_channel_is_test_only(self):
        self.config["local_test_catalog"].update({
            "target_ids": ["Bravo.us", "HallmarkChannel.us"],
            "include_initially_healthy_unpublished_ids": ["Bravo.us", "HallmarkChannel.us"],
            "reject_known_http_failures": [401, 404, 410],
        })
        entries = [
            candidate("Bravo.us", "https://example.test/bravo.m3u8",
                      status="ok", detail="Passed established two-probe validation"),
            candidate("HallmarkChannel.us", "https://example2.test/hallmark.m3u8",
                      status="ok", detail="Passed established two-probe validation"),
        ]
        channels, report = build.build_local_test_channels(entries, [], self.config)
        self.assertEqual({c["tvg_id"] for c in channels},
                         {"Bravo.us", "HallmarkChannel.us"})
        self.assertEqual(report["summary"]["initially_healthy_unpublished"], 2)
        self.assertTrue(all(s["local_test"] and not s.get("local_verified_override")
                            for c in channels for s in c["streams"]))
        republished, _ = build.build_local_test_channels(
            entries, [{"tvg_id": "Bravo.us"}, {"tvg_id": "HallmarkChannel.us"}],
            self.config,
        )
        self.assertEqual(republished, [])

    def test_local_test_rejects_known_404_401_and_expiring_media(self):
        self.config["local_test_catalog"].update({
            "target_ids": ["BET.us"],
            "include_runner_timeout_targets": True,
            "reject_known_http_failures": [401, 404, 410],
        })
        entries = [
            candidate("BET.us", "https://old.example/bet.m3u8",
                      status="cooldown", detail="Dead source probe deferred; last failure: HTTP 404"),
            candidate("BET.us", "https://private.example/bet.m3u8",
                      status="cooldown", detail="Dead source probe deferred; last failure: HTTP 401"),
            {
                **candidate("BET.us", "https://temporary.example/bet.m3u8",
                            status="cooldown", detail="Last failure: HTTP 403"),
                "ephemeral_signed": True, "expires_at": 1,
            },
            candidate("BET.us", "https://maybe.example/bet.m3u8",
                      status="cooldown", detail="The read operation timed out"),
        ]
        channels, report = build.build_local_test_channels(entries, [], self.config)
        self.assertEqual(len(channels), 1)
        self.assertEqual(len(channels[0]["streams"]), 1)
        self.assertEqual(channels[0]["streams"][0]["url"],
                         "https://maybe.example/bet.m3u8")
        reasons = report["summary"]["rejected_source_reasons"]
        self.assertGreaterEqual(reasons.get("known denied/dead source in cooldown", 0), 2)
        self.assertEqual(reasons.get("expired or expiring signed URL"), 1)

    def test_local_tests_never_publish_private_login_or_proxy_links(self):
        self.config["local_test_catalog"]["target_ids"] = ["CNBC.us"]
        entries = [
            candidate("CNBC.us", "https://user:secret@provider.example/cnbc.m3u8"),
            candidate("CNBC.us", "https://example.test/api/proxy/cnbc.m3u8"),
            candidate("CNBC.us", "https://public.example/cnbc.m3u8?username=x&password=y"),
            candidate("CNBC.us", "http://xtream.example:25461/userpass/secret/48152"),
            candidate("CNBC.us", "https://gateway.workers.dev/?id=CNBC"),
            candidate("CNBC.us", "https://public.example/cnbc.m3u8"),
        ]
        channels, report = build.build_local_test_channels(entries, [], self.config)
        self.assertEqual(len(channels), 1)
        self.assertEqual([s["url"] for s in channels[0]["streams"]],
                         ["https://public.example/cnbc.m3u8"])
        self.assertEqual(sum(report["summary"]["rejected_source_reasons"].values()), 5)

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
