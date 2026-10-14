#!/usr/bin/env python3
"""Render current official WTXF mark on a simulated dark Stremio tile.

Logo-only verification; intentionally does not run or modify stream QA.
"""
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

# This file is executed from research/, while assemble_build.py emits build.py
# at repository root. Resolve that location explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build


ROOT = Path("research/diagnostics/wtxf-logo-preview")


def main():
    config = json.loads(Path("config.json").read_text(encoding="utf-8"))
    official_url = config["channel_metadata"]["Fox.us@WTXFTV"]["logo"]
    channel = {
        "id": "wtxf_preview",
        "tvg_id": "Fox.us@WTXFTV",
        "name": "FOX 29 Philadelphia",
        "logo": official_url,
    }
    ROOT.mkdir(parents=True, exist_ok=True)
    report = build.normalize_channel_logos(ROOT, [channel], "", config)
    (ROOT / "normalization.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    logo_path = ROOT / "assets/channel-logos/wtxf_preview.png"
    assert report["summary"]["normalized"] == 1, report
    assert report["summary"]["fallback"] == 0, report
    with Image.open(logo_path) as file:
        logo = file.convert("RGBA")
    assert logo.getpixel((0, 0))[3] == 0, "A solid boxed logo is unacceptable"
    mask = logo.getchannel("A")
    bounds = mask.getbbox()
    assert bounds, "Logo must have visible pixels"
    assert bounds[2] - bounds[0] >= 250, f"Logo too small: {bounds}"
    samples = [
        rgba for rgba in logo.getdata()
        if rgba[3] >= 220
    ]
    assert samples, "Logo failed full-opacity pixel test"
    assert min(sum(rgba[:3]) / 3 for rgba in samples) >= 230, (
        "Dark ink would disappear on Stremio's background"
    )

    card = Image.new("RGB", (660, 390), (15, 14, 29))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((130, 26, 530, 328), 16, fill=(29, 27, 46))
    mark = logo.copy()
    mark.thumbnail((352, 260), Image.Resampling.LANCZOS)
    card.paste(mark, ((660 - mark.width) // 2, 40), mark)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 23)
    except OSError:
        font = ImageFont.load_default()
    label = "Fox (United States) WTXF-TV"
    bbox = draw.textbbox((0, 0), label, font=font)
    draw.text(((660 - (bbox[2]-bbox[0]))/2, 347), label, font=font, fill=(240, 241, 247))
    card.save(ROOT / "stremio-dark-card-preview.png", optimize=True)
    print(json.dumps({
        "status": "PASS",
        "source": official_url,
        "logo_bbox": bounds,
        "normalized": report["summary"]["normalized"],
        "fallbacks": report["summary"]["fallback"],
        "output": str(ROOT / "stremio-dark-card-preview.png"),
    }, indent=2))


if __name__ == "__main__":
    main()
