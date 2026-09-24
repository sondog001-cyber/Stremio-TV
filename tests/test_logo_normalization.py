import tempfile
import unittest
from pathlib import Path

import build


class LogoNormalizationTests(unittest.TestCase):
    def test_missing_logo_gets_local_square_fallback(self):
        channel = {
            "id": "stremiotv_test",
            "tvg_id": "HGTV.us",
            "name": "HGTV",
            "logo": "",
        }
        config = {
            "logo_normalization": {
                "enabled": True,
                "canvas_size": 512,
                "max_logo_size": 384,
                "timeout_seconds": 1,
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = build.normalize_channel_logos(
                root,
                [channel],
                "https://example.test/Stremio-TV",
                config,
            )

            asset = root / "assets" / "channel-logos" / "stremiotv_test.png"
            self.assertTrue(asset.exists())
            self.assertEqual(report["summary"]["channels"], 1)
            self.assertEqual(report["summary"]["fallback"], 1)
            self.assertEqual(
                channel["logo"],
                "https://example.test/Stremio-TV/assets/channel-logos/stremiotv_test.png",
            )

            from PIL import Image
            with Image.open(asset) as image:
                self.assertEqual(image.size, (512, 512))
                self.assertEqual(image.mode, "RGBA")

    def test_github_blob_logo_url_becomes_raw_asset_url(self):
        source = "https://github.com/tv-logo/tv-logos/blob/main/countries/united-states/hgtv-us.png?raw=true"
        self.assertEqual(
            build._canonical_logo_url(source),
            "https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/united-states/hgtv-us.png",
        )


if __name__ == "__main__":
    unittest.main()
