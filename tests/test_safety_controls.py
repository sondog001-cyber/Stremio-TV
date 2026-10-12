import unittest

import build


class SafetyControlsTests(unittest.TestCase):
    def test_exact_url_kill_switch_only_removes_that_source(self):
        entries = [
            {
                "name": "HGTV Primary",
                "tvg_id": "HGTV.us",
                "source": "Provider A",
                "family": "a",
                "url": "https://a.example/hgtv.m3u8",
                "headers": {},
            },
            {
                "name": "HGTV Backup",
                "tvg_id": "HGTV.us",
                "source": "Provider B",
                "family": "b",
                "url": "https://b.example/hgtv.m3u8",
                "headers": {},
            },
        ]
        config = {
            "safety_controls": {
                "disabled_urls": ["https://a.example/hgtv.m3u8"],
                "disabled_channels": [],
            }
        }

        kept, rejected = build.apply_safety_controls(entries, config)

        self.assertEqual([row["url"] for row in kept], ["https://b.example/hgtv.m3u8"])
        self.assertEqual(rejected[0]["reason"], "url-kill-switch")
        self.assertEqual(rejected[0]["source"], "Provider A")

    def test_confirmed_failed_cbssn_local_source_excluded_exactly(self):
        import json
        from pathlib import Path

        config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())
        rejected_url = "http://89.187.175.143:80/4073/index.m3u8"
        self.assertIn(rejected_url, config["safety_controls"]["disabled_urls"])
        candidates = [
            {"tvg_id": "CBSSportsNetwork.us", "url": rejected_url, "headers": {}},
            {"tvg_id": "CBSSportsNetwork.us", "url": "https://allowed.example/cbs.m3u8", "headers": {}},
            {"tvg_id": "SmithsonianChannel.us", "url": "http://89.187.175.143:80/603/index.m3u8", "headers": {}},
        ]
        kept, rejected = build.apply_safety_controls(candidates, config)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["reason"], "url-kill-switch")
        self.assertEqual(
            {(c["tvg_id"], c["url"]) for c in kept},
            {("CBSSportsNetwork.us", "https://allowed.example/cbs.m3u8"),
             ("SmithsonianChannel.us", "http://89.187.175.143:80/603/index.m3u8")},
        )

    def test_three_failed_smithsonian_local_sources_are_exact_url_disabled(self):
        import json
        from pathlib import Path

        config = json.loads(
            (Path(__file__).resolve().parents[1] / "config.json").read_text()
        )
        failed = [
            "http://89.187.175.143:80/4093/index.m3u8",
            "http://206.212.244.63/148/index.m3u8",
            "http://74.48.44.156:1234/stream/asd/391/master.m3u8",
        ]
        for url in failed:
            self.assertIn(url, config["safety_controls"]["disabled_urls"])

        entries = [
            *[
                {"tvg_id": "SmithsonianChannel.us", "url": url, "headers": {}}
                for url in failed
            ],
            {
                "tvg_id": "SmithsonianChannel.us",
                "url": "https://new-origin.example/smithsonian.m3u8",
                "headers": {},
            },
            {
                "tvg_id": "UnrelatedChannel.us",
                "url": "http://206.212.244.63/other/index.m3u8",
                "headers": {},
            },
        ]
        kept, rejected = build.apply_safety_controls(entries, config)
        self.assertEqual({item["url"] for item in rejected}, set(failed))
        self.assertTrue(all(item["reason"] == "url-kill-switch" for item in rejected))
        self.assertEqual(
            {item["url"] for item in kept},
            {
                "https://new-origin.example/smithsonian.m3u8",
                "http://206.212.244.63/other/index.m3u8",
            },
        )

    def test_user_failed_current_localtest_batch_retired_exactly(self):
        import json
        from pathlib import Path
        config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())
        failed = [
            "http://206.212.244.63/114/index.m3u8",
            "http://httpstreamer01.dc1.airlinktt.co/hlsnmia02/live/smil:BET.smil/playlist.m3u8",
            "http://74.48.44.156:1234/stream/asd/546/master.m3u8",
            "http://206.212.244.63/151/index.m3u8",
            "http://206.212.244.63/41/index.m3u8",
            "http://206.212.244.63/86/index.m3u8",
            "http://168.228.44.241:9998/play/a0e0/index.m3u8",
        ]
        self.assertTrue(set(failed).issubset(set(config["safety_controls"]["disabled_urls"])))
        entries = [
            {"tvg_id": "BET.us", "url": url, "headers": {}} for url in failed
        ] + [
            {"tvg_id": "BET.us", "url": "https://fresh.example/bet.m3u8", "headers": {}},
            {"tvg_id": "Test.us", "url": "http://206.212.244.63/other.m3u8", "headers": {}},
        ]
        kept, rejected = build.apply_safety_controls(entries, config)
        self.assertEqual({e["url"] for e in rejected}, set(failed))
        self.assertTrue(all(e["reason"] == "url-kill-switch" for e in rejected))
        self.assertEqual(len(kept), 2)

    def test_channel_kill_switch_removes_every_candidate(self):
        entries = [
            {"tvg_id": "FXX.us", "url": "https://a.example/fxx.m3u8", "headers": {}},
            {"tvg_id": "FXX.us@HD", "url": "https://b.example/fxx.m3u8", "headers": {}},
            {"tvg_id": "HGTV.us", "url": "https://c.example/hgtv.m3u8", "headers": {}},
        ]
        config = {"safety_controls": {"disabled_channels": ["FXX.us"]}}

        kept, rejected = build.apply_safety_controls(entries, config)

        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["tvg_id"], "HGTV.us")
        self.assertEqual(len(rejected), 2)
        self.assertTrue(all(row["reason"] == "channel-kill-switch" for row in rejected))

    def test_rejects_auth_credentials_and_drm_markers(self):
        entries = [
            {
                "tvg_id": "A.us",
                "url": "https://user:pass@example.test/a.m3u8",
                "headers": {},
            },
            {
                "tvg_id": "B.us",
                "url": "https://example.test/b.m3u8",
                "headers": {"Authorization": "Bearer private"},
            },
            {
                "tvg_id": "C.us",
                "url": "https://example.test/c.m3u8",
                "headers": {},
                "license_url": "https://license.example.test",
            },
        ]

        kept, rejected = build.apply_safety_controls(entries, {"safety_controls": {}})

        self.assertEqual(kept, [])
        self.assertEqual(
            {row["reason"] for row in rejected},
            {
                "embedded-url-credentials",
                "sensitive-auth-header",
                "drm-or-license-material",
            },
        )

    def test_public_signed_url_is_not_obscured_or_rewritten(self):
        url = "https://cdn.example.test/live.m3u8?token=publicly-published-signature"
        entries = [
            {
                "tvg_id": "Example.us",
                "url": url,
                "headers": {"Referer": "https://example.test/"},
                "source": "Public page",
                "family": "official-page",
            }
        ]

        kept, rejected = build.apply_safety_controls(entries, {"safety_controls": {}})

        self.assertEqual(rejected, [])
        self.assertEqual(kept[0]["url"], url)
        self.assertEqual(kept[0]["source"], "Public page")
        self.assertEqual(kept[0]["family"], "official-page")


if __name__ == "__main__":
    unittest.main()
