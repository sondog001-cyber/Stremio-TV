"""WTXF brand-only fix: transparent white official wordmark on dark cards."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw
import build


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = (
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/05/"
    "Fts-philadelphia-a.svg/960px-Fts-philadelphia-a.svg.png"
)


class WTXFLogoWordmarkTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

    def test_exact_philly_fox_id_uses_current_station_wordmark(self):
        metadata = self.config["channel_metadata"]
        self.assertEqual(metadata["Fox.us@WTXFTV"]["logo"], EXPECTED)
        self.assertEqual(metadata["WTXF.us"]["logo"], EXPECTED)
        styled = self.config["logo_normalization"]["monochrome_light_tvg_ids"]
        self.assertEqual(set(styled), {"Fox.us@WTXFTV", "WTXF.us"})
        self.assertNotEqual(metadata["Fox.us"]["logo"], EXPECTED)

    def _sample_png(self, *, opaque_white_background=False):
        image = Image.new(
            "RGBA", (420, 160),
            (255, 255, 255, 255) if opaque_white_background else (0, 0, 0, 0),
        )
        draw = ImageDraw.Draw(image)
        # Geometric synthetic black mark, not a recreation of station artwork.
        draw.rectangle((25, 22, 394, 62), fill=(0, 0, 0, 255))
        draw.rectangle((25, 90, 190, 134), fill=(0, 0, 0, 255))
        buf = io.BytesIO()
        image.save(buf, "PNG")
        return buf.getvalue()

    def test_black_png_logo_becomes_white_mark_without_colored_box(self):
        for opaque_white_background in (False, True):
            with self.subTest(opaque=opaque_white_background):
                channel = {
                    "id": "test_fox29", "tvg_id": "Fox.us@WTXFTV",
                    "name": "FOX 29 Philadelphia", "logo": EXPECTED,
                }
                payload = self._sample_png(opaque_white_background=opaque_white_background)
                with tempfile.TemporaryDirectory() as folder:
                    with mock.patch.object(
                        build.urllib.request, "urlopen",
                        return_value=io.BytesIO(payload),
                    ) as urlopen:
                        report = build.normalize_channel_logos(
                            Path(folder), [channel], "https://example.test",
                            self.config,
                        )
                    self.assertEqual(report["summary"]["normalized"], 1)
                    self.assertEqual(report["summary"]["fallback"], 0)
                    self.assertEqual(
                        report["channels"][0]["color_treatment"], "light-monochrome"
                    )
                    urlopen.assert_called_once()
                    request = urlopen.call_args.args[0]
                    self.assertEqual(request.full_url, EXPECTED)
                    with Image.open(
                        Path(folder) / "assets/channel-logos/test_fox29.png"
                    ) as out:
                        rgba = out.convert("RGBA")
                        self.assertEqual(rgba.size, (512, 512))
                        alpha = rgba.getchannel("A")
                        bbox = alpha.getbbox()
                        self.assertIsNotNone(bbox)
                        self.assertEqual(rgba.getpixel((0, 0))[3], 0)
                        self.assertLess(bbox[0], 128)
                        self.assertGreater(bbox[2], 380)
                        self.assertGreaterEqual(max(
                            rgba.getpixel((x, y))[0]
                            for x in range(bbox[0], bbox[2])
                            for y in range(bbox[1], bbox[3])
                            if rgba.getpixel((x, y))[3] >= 250
                        ), 245)
                        self.assertEqual(rgba.getpixel((256, 256))[3], 0)

    def test_unrelated_channel_keeps_original_black_artwork(self):
        data = self._sample_png()
        channel = {
            "id": "test_cnn", "tvg_id": "CNN.us",
            "name": "CNN", "logo": EXPECTED,
        }
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(
                build.urllib.request, "urlopen",
                return_value=io.BytesIO(data),
            ):
                report = build.normalize_channel_logos(
                    Path(folder), [channel], "https://example.test", self.config
                )
            self.assertEqual(report["channels"][0]["color_treatment"], "original")
            with Image.open(
                Path(folder) / "assets/channel-logos/test_cnn.png"
            ) as img:
                opaque_pixels = [
                    rgba
                    for rgba in img.convert("RGBA").getdata()
                    if rgba[3] == 255
                ]
                self.assertTrue(opaque_pixels)
                self.assertTrue(all(pixel[:3] == (0, 0, 0) for pixel in opaque_pixels))


if __name__ == "__main__":
    unittest.main()
