import json
import pathlib
import unittest
import urllib.parse
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
    def test_production_config_uses_direct_scanners_instead_of_code_search(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        discovery = config["discovery"]
        self.assertFalse(discovery["github_candidate_search"]["enabled"])

        sources = discovery["targeted_source_families"]["sources"]
        urls = {source["url"] for source in sources}
        self.assertIn("https://raw.githubusercontent.com/gogetta69/public-files/main/m3u_formatted.dat", urls)
        self.assertIn("https://dearbulut.github.io/iptv/playlists/best.m3u", urls)
        self.assertIn("https://raw.githubusercontent.com/wizakorhd/iptv/main/playlist.m3u", urls)
        self.assertIn("https://raw.githubusercontent.com/ivanminier/Playlists/main/playlist.m3u", urls)
        self.assertIn("https://raw.githubusercontent.com/nightah/daddylive/main/daddylive-channels-kodi.m3u8", urls)
        self.assertIn("https://raw.githubusercontent.com/arquerido/mych/main/TV247.m3u8", urls)
        self.assertIn("https://raw.githubusercontent.com/arquerido/mych/main/USAIR.m3u", urls)
        self.assertIn("https://raw.githubusercontent.com/aphrodite747/iptv-scraper/main/thetvapp.m3u8", urls)
        self.assertNotIn("https://raw.githubusercontent.com/judy-gotv/iptv/main/smart.m3u", urls)
        self.assertNotIn("https://raw.githubusercontent.com/judy-gotv/iptv/main/TVPass.m3u", urls)
        self.assertEqual(sum(source["family"] == "github-playlist" for source in sources), 4)
        self.assertTrue(discovery["targeted_source_families"]["hunt_unstable_channels"])

    def test_production_burn_in_is_promotion_gated(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        burn_in = config["stream_health"]["burn_in"]

        self.assertTrue(burn_in["enabled"])
        self.assertEqual(burn_in["scope"], "promotion-only")
        self.assertEqual(burn_in["duration_seconds"], 60)
        self.assertEqual(burn_in["interval_seconds"], 15)
        self.assertEqual(
            set(burn_in["established_classifications"]),
            {"Stable", "Backup"},
        )

    def test_production_config_retires_dead_historical_seeds_and_retests_current_exact_ids(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        seed_urls = {
            seed["url"]
            for seed in config["discovery"]["seed_candidates"]
        }

        current_exact = {
            "http://tvsen7.aynascope.net/teennick/index.m3u8",
            "http://168.228.44.241:9998/play/a0e0/index.m3u8",
        }
        self.assertTrue(current_exact.issubset(seed_urls))

        retired_or_rejected = {
            "http://170.254.18.106/HGTV/index.m3u8",
            "http://livex.pop-app.live/s4n/poplive/ch323/playlist.m3u8",
            "http://23.237.104.106:8080/USA_REELZ/index.m3u8",
            "http://168.228.44.241:9998/play/a0e1/index.m3u8",
            "https://sra72yz.s.gy/STARZ_ENCORE_ESPANOL_EAST_HD",
            "https://tvsen3.aynaott.com/5fUWDMxZ/index.m3u8",
            "https://tvsen6.aynaott.com/nfl/index.m3u8",
            "http://40.160.24.55/REELZ/index.m3u8",
            "http://40.160.24.55/TV_LAND/index.m3u8",
            "http://40.160.24.58/NEWSNATION/index.m3u8",
            "http://206.212.244.63/144/index.m3u8",
            "http://206.212.244.63/712/index.m3u8",
            "http://185.246.209.113/TVLandHD/index.m3u8",
            "https://messi.damitv.st/papi/ts/nflnetwork-usa/playlist.m3u8",
        }
        self.assertTrue(retired_or_rejected.isdisjoint(seed_urls))

        id_aliases = config["curation"]["canonical_id_aliases"]
        self.assertEqual(id_aliases["TeenNick.-.Eastern.us"], "TeenNick.us")
        self.assertEqual(id_aliases["TeenNick.(East).(TNCK).us"], "TeenNick.us")
        self.assertEqual(id_aliases["Starz.Edge.-.Eastern.us"], "StarzEdge.us")
        self.assertEqual(id_aliases["CW57WPSG.us"], "WPSG.us")
        self.assertEqual(
            id_aliases["NBC.Sports.Philadelphia.Plus.us2"],
            "NBCSportsPhiladelphiaPlus.us",
        )

    def test_m3u_parser_preserves_origin_referrer_and_kodi_inline_headers(self):
        text = "\n".join(
            [
                '#EXTINF:-1 tvg-id="HGTV.USA.-.Eastern.Feed.us",HGTV',
                '#EXTVLCOPT:http-origin=https://jxoxkplay.xyz',
                '#EXTVLCOPT:http-referrer=https://jxoxkplay.xyz/',
                '#EXTVLCOPT:http-user-agent=Mozilla/5.0 Test',
                'https://example.test/hgtv.m3u8|Origin=https%3A%2F%2Foverride.example&Referer=https%3A%2F%2Foverride.example%2F&User-Agent=Kodi%2F21',
            ]
        )

        rows = build.parse_m3u(
            text,
            {"name": "Header test", "family": "daddylive", "priority": 1},
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://example.test/hgtv.m3u8")
        self.assertEqual(rows[0]["headers"]["Origin"], "https://override.example")
        self.assertEqual(rows[0]["headers"]["Referer"], "https://override.example/")
        self.assertEqual(rows[0]["headers"]["User-Agent"], "Kodi/21")

    def setUp(self):
        build._PREVIOUS_CHANNEL_STATE_CACHE = None
        build._PUBLIC_TEXT_CACHE.clear()

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

    def test_target_set_canonicalizes_existing_approved_aliases(self):
        config = minimal_config()
        existing = [
            {
                "name": "FXX",
                "name_raw": "FXX",
                "tvg_id": "",
                "url": "https://existing.test/fxx.m3u8",
                "source": "Existing alias source",
                "family": "shovo",
                "quality": "HD",
            }
        ]
        with mock.patch.object(build, "_load_previous_channel_state", return_value={}):
            targets = build._target_ids_for_source_hunt(config, existing)

        self.assertEqual(targets, ["CNN.us"])

    def test_explicit_id_alias_applies_to_trusted_source_family(self):
        config = minimal_config()
        config["curation"]["national_allow"].extend(["BloombergTelevision.us", "BloombergTV.us"])
        config["curation"]["canonical_id_aliases"] = {
            "BloombergTelevision.us": "BloombergTV.us",
        }
        entries = [{
            "name": "Bloomberg",
            "name_raw": "Bloomberg",
            "tvg_id": "BloombergTelevision.us",
            "url": "https://example.test/bloomberg.m3u8",
            "source": "Trusted playlist",
            "family": "iptv-org",
        }]

        normalized = build.canonicalize_approved_sources(entries, config)

        self.assertEqual(normalized[0]["tvg_id"], "BloombergTV.us")
        self.assertEqual(normalized[0]["source_tvg_id"], "BloombergTelevision.us")

    def test_missing_channel_variant_ids_normalize_only_via_explicit_aliases(self):
        config = minimal_config()
        config["curation"]["national_allow"].extend([
            "TeenNick.us",
            "StarzEdge.us",
            "NBCSportsPhiladelphiaPlus.us",
        ])
        config["curation"]["philly_allow"].append("WPSG.us")
        config["curation"]["canonical_id_aliases"] = {
            "TeenNick.-.Eastern.us": "TeenNick.us",
            "TeenNick.(East).(TNCK).us": "TeenNick.us",
            "Starz.Edge.-.Eastern.us": "StarzEdge.us",
            "CW57WPSG.us": "WPSG.us",
            "NBC.Sports.Philadelphia.Plus.us2": "NBCSportsPhiladelphiaPlus.us",
        }
        entries = [
            {
                "name": "TeenNick",
                "tvg_id": "TeenNick.-.Eastern.us",
                "url": "https://example.test/teennick.m3u8",
                "source": "Trusted playlist",
                "family": "daddylive",
            },
            {
                "name": "Starz Edge",
                "tvg_id": "Starz.Edge.-.Eastern.us",
                "url": "https://example.test/starz-edge.m3u8",
                "source": "Trusted playlist",
                "family": "tv247",
            },
            {
                "name": "CW57 WPSG",
                "tvg_id": "CW57WPSG.us",
                "url": "https://example.test/wpsg.m3u8",
                "source": "Trusted playlist",
                "family": "iptv-org",
            },
            {
                "name": "NBCSN Philadelphia Plus",
                "tvg_id": "NBC.Sports.Philadelphia.Plus.us2",
                "url": "https://example.test/nbcsn-plus.m3u8",
                "source": "Trusted playlist",
                "family": "iptv-org",
            },
        ]

        normalized = build.canonicalize_approved_sources(entries, config)

        self.assertEqual(
            [row["tvg_id"] for row in normalized],
            [
                "TeenNick.us",
                "StarzEdge.us",
                "WPSG.us",
                "NBCSportsPhiladelphiaPlus.us",
            ],
        )
        self.assertEqual(
            [row["source_tvg_id"] for row in normalized],
            [
                "TeenNick.-.Eastern.us",
                "Starz.Edge.-.Eastern.us",
                "CW57WPSG.us",
                "NBC.Sports.Philadelphia.Plus.us2",
            ],
        )

    def test_target_hunt_keeps_recovered_channel_until_stream_is_established(self):
        config = minimal_config()
        config["discovery"]["targeted_source_families"]["hunt_unstable_channels"] = True
        entry = {
            "name": "FXX",
            "name_raw": "FXX",
            "tvg_id": "FXX.us",
            "url": "https://example.test/fxx.m3u8",
            "source": "Candidate",
            "family": "shovo",
            "quality": "HD",
            "headers": {},
        }
        key = build._stream_stability_key(entry)
        prior_channel_state = {
            "channels": {
                "National:FXX.us": {
                    "pattern": "FXX.us",
                    "present": True,
                }
            }
        }
        quarantine_state = {
            "streams": {
                key: {
                    "classification": "Quarantine",
                    "history": [True, False],
                }
            }
        }
        stable_state = {
            "streams": {
                key: {
                    "classification": "Stable",
                    "history": [True, True, True, True, True],
                }
            }
        }

        with (
            mock.patch.object(build, "_load_previous_channel_state", return_value=prior_channel_state),
            mock.patch.object(build, "_load_previous_stream_stability", return_value=quarantine_state),
        ):
            quarantine_targets = build._target_ids_for_source_hunt(
                config,
                [entry],
                scope="national",
            )

        with (
            mock.patch.object(build, "_load_previous_channel_state", return_value=prior_channel_state),
            mock.patch.object(build, "_load_previous_stream_stability", return_value=stable_state),
        ):
            stable_targets = build._target_ids_for_source_hunt(
                config,
                [entry],
                scope="national",
            )

        self.assertIn("FXX.us", quarantine_targets)
        self.assertNotIn("FXX.us", stable_targets)

    def test_local_and_national_target_sets_are_disjoint(self):
        config = minimal_config()
        config["curation"]["philly_allow"] = ["WPVI.us", "WPSG.us"]
        config["discovery"]["philly_local_sources"] = {
            "target_ids": ["WPVI.us", "WPSG.us"],
        }
        with mock.patch.object(build, "_load_previous_channel_state", return_value={}):
            national = build._target_ids_for_source_hunt(config, [], scope="national")
            philly = build._target_ids_for_source_hunt(config, [], scope="philly")

        self.assertEqual(national, ["CNN.us", "FXX.us"])
        self.assertEqual(philly, ["WPVI.us", "WPSG.us"])
        self.assertFalse(set(national) & set(philly))

    def test_public_hunt_excludes_private_connector_only_ids(self):
        config = minimal_config()
        config["discovery"]["public_search_policy"] = {
            "private_connector_only_ids": ["FXX.us"]
        }
        with mock.patch.object(build, "_load_previous_channel_state", return_value={}):
            targets = build._target_ids_for_source_hunt(config, [])

        self.assertEqual(targets, ["CNN.us"])

    def test_philly_scanner_retains_only_exact_local_ids(self):
        config = minimal_config()
        config["curation"]["philly_allow"] = ["WPVI.us"]
        config["discovery"]["philly_local_sources"] = {
            "enabled": True,
            "target_ids": ["WPVI.us"],
            "official_pages": [],
            "playlists": [
                {
                    "name": "Local test",
                    "family": "localbtv-relay",
                    "format": "m3u",
                    "url": "https://example.test/locals.m3u",
                    "philly": True,
                }
            ],
        }
        playlist = "\n".join(
            [
                "#EXTM3U",
                '#EXTINF:-1 tvg-id="WPVI.us",6ABC WPVI',
                "https://local.test/wpvi.m3u8",
                '#EXTINF:-1 tvg-id="ESPN.us",ESPN',
                "https://national.test/espn.m3u8",
            ]
        )
        with mock.patch.object(build, "_load_previous_channel_state", return_value={}), mock.patch.object(
            build,
            "_fetch_public_text",
            return_value=(playlist, "https://example.test/locals.m3u"),
        ):
            entries, rows, targets = build.discover_philly_local_sources(config, [])

        self.assertEqual(targets, ["WPVI.us"])
        self.assertEqual([entry["tvg_id"] for entry in entries], ["WPVI.us"])
        self.assertTrue(entries[0]["philly"])
        self.assertTrue(entries[0]["philly_local_scan"])
        self.assertTrue(all(row.get("scope") == "philly-local" for row in rows))

    def test_research_only_official_page_never_emits_candidate(self):
        config = minimal_config()
        page = '<script>const live = "https://example.test/cbs-news-live.m3u8";</script>'
        item = {
            "name": "Philly 57 / WPSG",
            "tvg_id": "WPSG.us",
            "page_url": "https://example.test/philly-57/",
            "candidate_mode": "research-only",
        }
        with mock.patch.object(
            build,
            "_fetch_public_text",
            return_value=(page, item["page_url"]),
        ):
            entries, rows = build.discover_official_page_streams(
                config,
                items=[item],
                target_ids=["WPSG.us"],
                row_kind="philly-official-page",
            )

        self.assertEqual(entries, [])
        self.assertEqual(rows[0]["candidates_emitted"], 0)
        self.assertEqual(rows[0]["status"], "research-only-public-hls-found")
        self.assertEqual(rows[0]["candidates"], ["https://example.test/cbs-news-live.m3u8"])

    def test_official_page_scans_public_iframe_for_manifest(self):
        config = minimal_config()
        config["discovery"]["official_player_scan"] = {
            "enabled": True,
            "max_documents": 4,
            "max_depth": 2,
        }
        item = {
            "name": "Station",
            "tvg_id": "WPVI.us",
            "page_url": "https://station.test/live",
            "content_kind": "full-linear",
        }
        page = '<iframe src="https://player.test/embed/live"></iframe>'
        player = '<script>const livestream = "https://cdn.test/station-live.m3u8";</script>'

        def fetch(url, **kwargs):
            if url == item["page_url"]:
                return page, url
            if url == "https://player.test/embed/live":
                return player, url
            raise AssertionError(f"unexpected URL: {url}")

        with mock.patch.object(build, "_fetch_public_text", side_effect=fetch):
            entries, rows = build.discover_official_page_streams(config, items=[item])

        self.assertEqual([entry["url"] for entry in entries], ["https://cdn.test/station-live.m3u8"])
        self.assertEqual(entries[0]["manifest_provenance"]["document_kind"], "iframe")
        self.assertEqual(len(rows[0]["documents_scanned"]), 2)

    def test_official_player_scan_rejects_private_document_urls(self):
        links = build._extract_player_document_urls(
            '<iframe src="http://127.0.0.1/player"></iframe>',
            "https://station.test/live",
        )
        self.assertEqual(links, [])

    def test_iptv_org_explicit_stream_id_prevents_cross_channel_alias_leakage(self):
        config = minimal_config()
        config["curation"]["national_allow"].extend([
            "InvestigationDiscovery.us",
            "TeenNick.us",
        ])
        config["discovery"]["iptv_org_issues"]["targets"] = [
            {
                "tvg_id": "InvestigationDiscovery.us",
                "name": "Investigation Discovery",
                "aliases": ["ID"],
            },
            {
                "tvg_id": "TeenNick.us",
                "name": "TeenNick",
                "aliases": ["TeenNick"],
            },
        ]
        issues = [{
            "number": 52643,
            "title": "Add: TeenNick IL SD",
            "body": "\n".join([
                "### Stream ID (required)",
                "",
                "TeenNick.il@SD",
                "",
                "### Stream URL (required)",
                "",
                "http://89.33.29.115:8080/TeenNick/index.m3u8",
            ]),
            "html_url": "https://github.com/iptv-org/iptv/issues/52643",
            "labels": [{"name": "streams:add"}, {"name": "check:passed"}],
        }]

        with mock.patch.object(
            build,
            "_fetch_public_text",
            return_value=(json.dumps(issues), "https://api.github.test/issues"),
        ):
            entries, rows = build.discover_iptv_org_passed_issues(
                config,
                ["InvestigationDiscovery.us", "TeenNick.us"],
            )

        self.assertEqual(entries, [])
        self.assertEqual(rows, [])

    def test_iptv_org_removals_are_diagnostics_not_candidates(self):
        config = minimal_config()
        issues = [
            {
                "number": 101,
                "title": "Add: FXX",
                "body": "\n".join([
                    "### Stream ID (required)",
                    "",
                    "FXX.us",
                    "",
                    "### Stream URL (required)",
                    "",
                    "https://example.test/fxx.m3u8",
                ]),
                "html_url": "https://github.com/iptv-org/iptv/issues/101",
                "labels": [{"name": "streams:add"}, {"name": "check:passed"}],
            },
            {
                "number": 102,
                "title": "Broken: FXX",
                "body": "\n".join([
                    "### Stream ID (required)",
                    "",
                    "FXX.us",
                    "",
                    "### Stream URL (required)",
                    "",
                    "https://example.test/dead-fxx.m3u8",
                ]),
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

    def test_github_search_keeps_fresh_exact_alias_candidate(self):
        config = minimal_config()
        config["curation"]["approved_unverified_families"].append("github-candidate")
        config["discovery"]["github_candidate_search"] = {
            "enabled": True,
            "max_targets_per_build": 1,
            "max_queries_per_build": 2,
            "min_freshness_score": 55,
        }
        search_payload = {
            "items": [{
                "path": "channels.m3u",
                "html_url": "https://github.com/example/tv/blob/abc123/channels.m3u",
                "repository": {
                    "full_name": "example/tv",
                    "pushed_at": "2026-09-20T00:00:00Z",
                },
            }]
        }
        playlist = "\n".join([
            "#EXTM3U",
            '#EXTINF:-1 tvg-id="",FXX',
            "https://stream.test/fxx.m3u8",
        ])

        def fetch(url, **kwargs):
            if "api.github.com/search/code" in url:
                if "FXX.us" in urllib.parse.unquote(url):
                    return json.dumps({"items": []}), url
                return json.dumps(search_payload), url
            return playlist, url

        with mock.patch.object(build, "_fetch_public_text", side_effect=fetch):
            entries, rows = build.discover_github_candidates(config, ["FXX.us"])

        self.assertEqual([entry["tvg_id"] for entry in entries], ["FXX.us"])
        self.assertEqual(entries[0]["github_repository"], "example/tv")
        self.assertGreaterEqual(entries[0]["freshness_score"], 55)
        self.assertEqual(rows[0]["candidates_found"], 1)
        search_rows = [row for row in rows if row["kind"] == "github-candidate-search"]
        self.assertEqual([row["match_kind"] for row in search_rows], ["exact-id", "approved-alias"])

    def test_github_freshness_penalizes_old_alias_matches(self):
        now = build.dt.datetime(2026, 9, 22, tzinfo=build.UTC)
        fresh = build.score_github_candidate_freshness("2026-09-20T00:00:00Z", "exact-id", now)
        stale = build.score_github_candidate_freshness("2024-01-01T00:00:00Z", "approved-alias", now)
        self.assertGreater(fresh["score"], stale["score"])
        self.assertEqual(stale["label"], "stale")

    def test_github_search_gives_every_target_exact_id_first(self):
        config = minimal_config()
        config["discovery"]["github_candidate_search"] = {
            "enabled": True,
            "max_targets_per_build": 2,
            "max_queries_per_build": 3,
            "min_query_interval_seconds": 0,
        }
        requested = []

        def fetch(url, **kwargs):
            requested.append(urllib.parse.unquote(url))
            return json.dumps({"items": []}), url

        with mock.patch.dict(build.os.environ, {"GITHUB_RUN_NUMBER": "0"}), mock.patch.object(
            build,
            "_fetch_public_text",
            side_effect=fetch,
        ):
            _, rows = build.discover_github_candidates(config, ["FXX.us", "CNN.us"])

        search_rows = [row for row in rows if row["kind"] == "github-candidate-search"]
        self.assertEqual(
            [(row["tvg_id"], row["match_kind"]) for row in search_rows],
            [
                ("FXX.us", "exact-id"),
                ("CNN.us", "exact-id"),
                ("FXX.us", "approved-alias"),
            ],
        )
        self.assertEqual(len(requested), 3)

    def test_github_search_paces_code_search_requests(self):
        config = minimal_config()
        config["discovery"]["github_candidate_search"] = {
            "enabled": True,
            "max_targets_per_build": 2,
            "max_queries_per_build": 2,
            "min_query_interval_seconds": 7,
        }
        with mock.patch.object(
            build,
            "_fetch_public_text",
            return_value=(json.dumps({"items": []}), "https://api.github.test/search"),
        ), mock.patch.object(
            build.time,
            "monotonic",
            side_effect=[100.0, 101.0, 107.0],
        ), mock.patch.object(build.time, "sleep") as sleep:
            _, rows = build.discover_github_candidates(config, ["FXX.us", "CNN.us"])

        sleep.assert_called_once_with(6.0)
        self.assertEqual(rows[0]["min_query_interval_seconds"], 7.0)
        self.assertEqual(rows[0]["paced_wait_seconds"], 6.0)

    def test_github_search_retries_bounded_rate_limit(self):
        config = minimal_config()
        config["discovery"]["github_candidate_search"] = {
            "enabled": True,
            "max_targets_per_build": 1,
            "max_queries_per_build": 1,
            "min_query_interval_seconds": 0,
            "rate_limit_retries": 1,
            "max_rate_limit_wait_seconds": 10,
        }
        error = build.urllib.error.HTTPError(
            "https://api.github.test/search",
            429,
            "Too Many Requests",
            {"Retry-After": "1"},
            None,
        )
        with mock.patch.object(
            build,
            "_fetch_public_text",
            side_effect=[error, (json.dumps({"items": []}), "https://api.github.test/search")],
        ), mock.patch.object(build.time, "sleep") as sleep:
            _, rows = build.discover_github_candidates(config, ["FXX.us"])

        sleep.assert_called_once_with(1.25)
        self.assertEqual(rows[0]["rate_limit_retries"], 1)
        self.assertEqual(rows[1]["status"], "ok")

    def test_github_search_fetches_real_repository_freshness(self):
        config = minimal_config()
        config["curation"]["approved_unverified_families"].append("github-candidate")
        config["discovery"]["github_candidate_search"] = {
            "enabled": True,
            "max_targets_per_build": 1,
            "max_queries_per_build": 1,
            "min_query_interval_seconds": 0,
            "min_freshness_score": 55,
        }
        search_payload = {
            "items": [{
                "path": "channels.m3u",
                "html_url": "https://github.com/example/tv/blob/abc123/channels.m3u",
                "repository": {
                    "full_name": "example/tv",
                    "url": "https://api.github.com/repos/example/tv",
                },
            }]
        }
        playlist = "\n".join([
            "#EXTM3U",
            '#EXTINF:-1 tvg-id="FXX.us",FXX',
            "https://stream.test/fxx.m3u8",
        ])

        def fetch(url, **kwargs):
            if "search/code" in url:
                return json.dumps(search_payload), url
            if url == "https://api.github.com/repos/example/tv":
                return json.dumps({"pushed_at": "2026-09-20T00:00:00Z"}), url
            return playlist, url

        with mock.patch.object(build, "_fetch_public_text", side_effect=fetch):
            entries, rows = build.discover_github_candidates(config, ["FXX.us"])

        self.assertEqual(len(entries), 1)
        file_row = next(row for row in rows if row["kind"] == "github-candidate-search")["files"][0]
        self.assertEqual(file_row["freshness"]["label"], "fresh")
        self.assertEqual(file_row["freshness"]["updated_at"], "2026-09-20T00:00:00Z")

    def test_github_search_rejects_embedded_provider_credentials(self):
        config = minimal_config()
        config["discovery"]["github_candidate_search"] = {
            "enabled": True,
            "max_targets_per_build": 1,
            "max_queries_per_build": 1,
            "min_freshness_score": 55,
            "max_candidates_per_file": 5,
        }
        search_payload = {
            "items": [{
                "path": "channels.m3u",
                "html_url": "https://github.com/example/tv/blob/abc123/channels.m3u",
                "repository": {
                    "full_name": "example/tv",
                    "pushed_at": "2026-09-20T00:00:00Z",
                },
            }]
        }
        playlist = "\n".join([
            "#EXTM3U",
            '#EXTINF:-1 tvg-id="FXX.us",FXX public',
            "https://cdn.example.test/fxx/master.m3u8",
            '#EXTINF:-1 tvg-id="FXX.us",FXX credential path',
            "http://provider.example:8080/live/account-name/secret-value/1234.ts",
            '#EXTINF:-1 tvg-id="FXX.us",FXX email path',
            "https://provider.example/api/stream/person@example.com/1234/fxx.m3u8",
            '#EXTINF:-1 tvg-id="FXX.us",FXX expiring token',
            "https://cdn.example.test/fxx/master.m3u8?token=short-lived",
        ])

        def fetch(url, **kwargs):
            if "api.github.com/search/code" in url:
                return json.dumps(search_payload), url
            return playlist, url

        with mock.patch.object(build, "_fetch_public_text", side_effect=fetch):
            entries, rows = build.discover_github_candidates(config, ["FXX.us"])

        self.assertEqual([entry["url"] for entry in entries], ["https://cdn.example.test/fxx/master.m3u8"])
        file_row = next(row for row in rows if row["kind"] == "github-candidate-search")["files"][0]
        self.assertEqual(file_row["credential_urls_rejected"], 3)

    def test_public_signed_urls_can_be_enabled_without_allowing_credentials(self):
        self.assertTrue(build._is_clean_github_media_url(
            "https://cdn.example.test/live.m3u8?token=public-page-value&expires=9999999999",
            allow_public_signed_urls=True,
        ))
        self.assertFalse(build._is_clean_github_media_url(
            "https://provider.example/live/account-name/secret-value/1234.ts",
            allow_public_signed_urls=True,
        ))
        self.assertFalse(build._is_clean_github_media_url(
            "https://cdn.example.test/live.m3u8?username=account&password=secret",
            allow_public_signed_urls=True,
        ))

    def test_targeted_scanner_accepts_public_signed_url_but_rejects_account_path(self):
        config = minimal_config()
        config["discovery"]["public_search_policy"] = {"allow_public_signed_urls": True}
        config["discovery"]["targeted_source_families"] = {
            "enabled": True,
            "sources": [{
                "name": "Public signed list", "family": "public-signed", "format": "m3u",
                "url": "https://example.test/list.m3u",
            }],
        }
        playlist = "\n".join([
            "#EXTM3U",
            '#EXTINF:-1 tvg-id="FXX.us",FXX signed',
            "https://cdn.example.test/fxx.m3u8?token=published&expires=9999999999",
            '#EXTINF:-1 tvg-id="FXX.us",FXX account path',
            "https://provider.example/live/account-name/secret-value/1234.ts",
        ])
        with mock.patch.object(build, "_load_previous_channel_state", return_value={}), mock.patch.object(
            build, "_fetch_public_text", return_value=(playlist, "https://example.test/list.m3u")
        ):
            entries, rows, _targets = build.discover_targeted_source_families(config, [])

        self.assertEqual(len(entries), 1)
        self.assertIn("token=published", entries[0]["url"])
        family_row = next(row for row in rows if row.get("kind") == "targeted-source-family")
        self.assertEqual(family_row["credential_urls_rejected"], 1)


if __name__ == "__main__":
    unittest.main()
