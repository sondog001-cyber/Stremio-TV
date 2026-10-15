import copy
import unittest
from unittest import mock

from research import maintained_github_origin_scan as scan


class GithubMaintainedOriginResearchTests(unittest.TestCase):
    def test_24_exact_targets_four_six_id_batches(self):
        cfg = scan.load_registry()
        self.assertEqual([len(cfg["batches"][b]) for b in "ABCD"], [6, 6, 6, 6])
        self.assertEqual(len(cfg["channels"]), 24)

    def test_watch_pages_not_real_hls(self):
        self.assertEqual(scan.family("https://tvpass.org/live/CBSSportsNetworkUSA/hd"), "tvpass-watch-route-not-hls")
        self.assertEqual(scan.family("https://tvpass.org/live/ESPNews/sd"), "tvpass-watch-route-not-hls")

    def test_proxy_and_legacy_reseller_families_not_original(self):
        self.assertEqual(scan.family("https://zekonew.newkso.ru/zeko/premium308/mono.m3u8"),
                         "daddylive-delivery-wrapper-not-original-origin")
        self.assertEqual(scan.family("http://23.237.104.106:8080/USA_HBO_ZONE/index.m3u8"),
                         "known-high-concentration-shared-host")
        self.assertEqual(scan.family("http://41.205.93.154/NICKTOONS/index.m3u8"),
                         "known-or-historical-reseller-relay")

    def test_forbid_subscriber_urls_and_private_networks(self):
        for url in (
            "http://10.1.2.3/BRAVO/index.m3u8",
            "https://host.example/live/alice/password/307.m3u8",
            "https://user:pass@host.example/channel.m3u8",
            "https://host.example/live/user%40example.com/pass/381.m3u8",
        ):
            with self.subTest(url=url):
                self.assertEqual(scan.family(url), "reject-credential-or-unsupported-url")

    def test_exact_id_and_unambiguous_alias(self):
        cfg = scan.load_registry()["channels"]
        valid = {"tvg_id": "CinemaxClassics.us@East", "name": "Cinemax Classics", "url": "http://x.net/a.m3u8"}
        self.assertIsNotNone(scan.identity(valid, cfg["CinemaxClassics.us"]))
        old = {"tvg_id": "HallmarkDrama", "name": "Hallmark Family", "url": "http://x.net/a.m3u8"}
        self.assertIsNotNone(scan.identity(old, cfg["HallmarkFamily.us"]))
        cross = {"tvg_id": "CBSSportsGolazoNetwork.us", "name": "CBS Sports Golazo Network",
                 "url": "http://x.net/a.m3u8"}
        self.assertIsNone(scan.identity(cross, cfg["CBSSportsNetwork.us"]))
        telemundo = {"tvg_id": "Telemundo.us@WCAU", "name": "WCAU-DT1", "url": "http://x.net/a.m3u8"}
        self.assertIsNone(scan.identity(telemundo, cfg["WCAU.us"]))

    def test_no_unauthorized_production_promotion_on_progressing_hls(self):
        cfg = scan.load_registry()
        playlist = "#EXTM3U\n#EXTINF:-1 tvg-id=\"Bravo.us@East\",Bravo\nhttp://41.205.93.154/BRAVO/index.m3u8\n"
        with mock.patch.object(scan.hls, "fetch", return_value={"data": playlist.encode()}), mock.patch.object(
                scan.hls, "load_known_paths", return_value=(set(), set(), set())), mock.patch.object(
                scan.hls, "probe_manifest", return_value={"stage": "progressing-hls-readable-not-decoded", "final_host":"cdn.test"}):
            output = scan.run("A", cfg)
        self.assertEqual(len(output["channels"]), 6)
        self.assertEqual(output["summary"]["qualified_original_origins"], 0)
        self.assertEqual(output["summary"]["streams_promoted"], 0)
        self.assertTrue(all(not result["authorized_media_origin_verified"] for result in output["preflight"]))
        self.assertTrue(any(r["github_claims"] for r in output["channels"]))

    def test_reject_targets_not_24(self):
        cfg = copy.deepcopy(scan.load_registry())
        cfg["batches"]["D"].remove("WPSG.us")
        with mock.patch.object(scan.pathlib.Path, "read_text", return_value=__import__("json").dumps(cfg)):
            with self.assertRaises(ValueError):
                scan.load_registry()


if __name__ == "__main__":
    unittest.main()
