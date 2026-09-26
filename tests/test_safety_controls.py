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
