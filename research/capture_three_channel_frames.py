#!/usr/bin/env python3
"""Capture tiny, read-only frames for exact-feed identity comparison.

Do not promote candidates from thumbnails alone: EPG/programme checks and
local testing may still be necessary.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import subprocess
import time
from datetime import datetime, timezone

STREAMS = {
    "history-current": "http://212.5.144.156:8080/history/index.m3u8",
    "history-aynascope-english": "https://tvsen5.aynascope.net/historyen/index.m3u8",
    "disney-current": "http://212.5.144.156/disney/index.m3u8",
    "disney-aynascope-ambiguous": "https://tvsen7.aynascope.net/disney/index.m3u8",
    "natgeo-current": "http://212.5.144.156:8080/natgeo/index.m3u8",
    "natgeo-hd-east": "http://198.58.104.90:8989/natgeo/index.m3u8",
}
OUT = Path("research/diagnostics/frame-samples")


def grab(pair):
    name, url = pair
    destination = OUT / f"{name}.png"
    is_history = name.startswith("history-")
    # Three spaced History samples aid programme matching against the US
    # Eastern schedule. Other channels retain one quick network-logo frame.
    if is_history:
        destination = OUT / f"{name}-%02d.png"
    args = [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
        "-rw_timeout", "10000000", "-i", url,
        "-map", "0:v:0",
    ] + (
        ["-t", "46", "-vf", "fps=1/15,scale=640:-2", "-frames:v", "3"]
        if is_history else
        ["-ss", "8", "-frames:v", "1", "-vf", "scale=640:-2"]
    ) + ["-y", str(destination)]
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=80)
        samples = sorted(OUT.glob(f"{name}-*.png")) if is_history else [destination]
        ok = p.returncode == 0 and any(file.exists() and file.stat().st_size > 4000 for file in samples)
        if not ok:
            for file in samples:
                file.unlink(missing_ok=True)
        return {"name": name, "captured": ok, "error": p.stderr[-400:],
                "sample_paths": [str(file) for file in samples if file.exists()],
                "size": sum(file.stat().st_size for file in samples if file.exists())}
    except Exception as exc:
        return {"name": name, "captured": False, "error": str(exc)[:300], "size": 0}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(grab, STREAMS.items()))
    report = {"purpose": "visual identity evidence only, not verified East-feed attribution",
              "recorded_utc": datetime.now(timezone.utc).isoformat(),
              "channels": results}
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
