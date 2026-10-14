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
    args = [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
        "-rw_timeout", "10000000", "-i", url,
        "-map", "0:v:0", "-ss", "8",
        "-frames:v", "1", "-vf", "scale=640:-2",
        "-y", str(destination)
    ]
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=40)
        ok = p.returncode == 0 and destination.exists() and destination.stat().st_size > 4000
        if not ok:
            destination.unlink(missing_ok=True)
        return {"name": name, "captured": ok, "error": p.stderr[-400:],
                "size": destination.stat().st_size if ok else 0}
    except Exception as exc:
        return {"name": name, "captured": False, "error": str(exc)[:300], "size": 0}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(grab, STREAMS.items()))
    report = {"purpose": "visual identity evidence only, not verified East-feed attribution",
              "channels": results}
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
