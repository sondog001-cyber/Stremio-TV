#!/usr/bin/env python3
"""Capture small review frames for all 65-second-qualified recovery feeds.

Does NOT assert broadcast/network identity. Read-only research artifacts.
A green decoder without the correct on-screen network/programming is rejected.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import subprocess
import time

BASE = Path("research/diagnostics")
FRAMES = BASE / "lost-13-identity-frames"


def capture(item):
    channel, label, url, referer = item
    safe = re.sub(r"[^a-z0-9]+", "-", channel.lower() + "-" + label.lower()).strip("-")
    destination = FRAMES / (safe + "-%02d.png")
    args = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
            "-rw_timeout", "15000000", "-user_agent", "Mozilla/5.0"]
    if referer:
        args += ["-headers", "Referer: " + referer + "\r\n"]
    args += ["-i", url, "-map", "0:v:0", "-an",
             "-t", "46", "-vf", "fps=1/15,scale=640:-2",
             "-frames:v", "3", "-y", str(destination)]
    start = time.monotonic()
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=100)
        files = sorted(FRAMES.glob(safe + "-*.png"))
        return {"tvg_id": channel, "candidate": label, "source_url": url,
                "captured_files": [str(x) for x in files], "exit_code": p.returncode,
                "elapsed": round(time.monotonic()-start, 1),
                "error_tail": p.stderr[-230:],
                "programme_identity_verified": False}
    except subprocess.TimeoutExpired:
        return {"tvg_id": channel, "candidate": label, "source_url": url,
                "captured_files": [], "error_tail": "FFmpeg capture timeout",
                "programme_identity_verified": False}


def main():
    report = json.loads((BASE / "lost-13-source-probe.json").read_text())
    passing = [x for x in report["candidates"] if x["extended_media_pass"]]
    FRAMES.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(capture, [
            (x["tvg_id"], x["label"], x["url"], x.get("referer", ""))
            for x in passing
        ]))
    report = {"captured_at": datetime.now(timezone.utc).isoformat(),
              "note": "Identity review required before any channel promotion",
              "sources": rows}
    (FRAMES / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    for x in rows:
        print(f"{x['tvg_id']} / {x['candidate']}: "
              f"{len(x['captured_files'])} files; identity UNVERIFIED")


if __name__ == "__main__":
    main()
