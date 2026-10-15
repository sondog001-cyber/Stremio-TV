#!/usr/bin/env python3
"""Diagnostic-only FFmpeg probe for three fragile US-East linear channels.

Never modifies config, manual_sources, source priority, or production streams.
Playback success != exact feed identity; local programme comparison is required.
"""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib.parse import urlsplit

CANDIDATES = [
    # Existing source, for A/B comparison with potential alternatives.
    ("History.us", "current-iptv-org-east", "http://212.5.144.156:8080/history/index.m3u8", "iptv-org/iptv US playlist"),
    ("DisneyChannel.us", "current-iptv-org-east", "http://212.5.144.156/disney/index.m3u8", "iptv-org/iptv US playlist"),
    ("NationalGeographic.us", "current-iptv-org-east", "http://212.5.144.156:8080/natgeo/index.m3u8", "iptv-org/iptv US playlist"),
    # Separate-host leads only; do not promote merely for a matching label.
    ("History.us", "sorted-iptv-history-east-lead", "http://40.160.24.53/HISTORY_CHANNEL/index.m3u8", "THEROCKSSS/sorted-iptv documentary.m3u"),
    ("History.us", "iptv-org-history-east-2024-lead", "http://livex.pop-app.live/s4n/poplive/ch215/playlist.m3u8", "iptv-org/iptv issue 16051"),
    ("History.us", "iptv-org-history-2024-lead", "http://170.254.18.106/HISTORY/index.m3u8", "iptv-org/iptv issue 15900"),
    ("History.us", "iptv-org-history-east-2022-lead", "http://38.91.57.12:2082/history/tracks-v1a1/mono.m3u8", "iptv-org/iptv issue 6315; historical"),
    ("DisneyChannel.us", "airlink-disney-lead", "http://httpstreamer01.dc1.airlinktt.co/hlsnmia01/live/smil:DISNEY.smil/playlist.m3u8", "existing discovery.seed_candidates"),
    ("DisneyChannel.us", "artmott-disney-lead", "http://ott.artmott.com/DisneyChannel/tracks-v1a1/mono.m3u8", "existing discovery.seed_candidates"),
    ("DisneyChannel.us", "thetvapp-east-2025-lead", "https://e3.thetvapp.to/hls/DisneyChannelEast/tracks-v2a1/mono.m3u8", "iptv-org/iptv issue 27125"),
    ("DisneyChannel.us", "thetvapp-east-alternate-2025-lead", "https://e5.thetvapp.to/hls/DisneyChannelEast/index.m3u8", "iptv-org/iptv issue 28387; historical"),
    ("DisneyChannel.us", "moveonjoy-fl31-disney-2026-lead", "https://fl31.moveonjoy.com/DISNEY/index.m3u8", "pzeepzee March 2026 exact East directory; network identity unconfirmed"),
    ("DisneyChannel.us", "4.30.180.36-disneychannel-2026-lead", "http://4.30.180.36:8420/disneychannel/index.m3u8", "iptv-org/iptv issue 51016 Sep 2026; unsigned URL only; may be inactive"),
    ("NationalGeographic.us", "iptv-org-hd-east-lead", "http://198.58.104.90:8989/natgeo/index.m3u8", "iptv-org/iptv US HDEast variant"),
    ("NationalGeographic.us", "sorted-iptv-east-lead", "http://40.160.24.53/NAT_GEO/index.m3u8", "THEROCKSSS/sorted-iptv documentary.m3u"),
    # Source-family discovery: current directory includes tokenized examples,
    # but test ONLY the public unsigned canonical paths. Do not synthesize
    # credentials or claim feed identity from a descriptive label.
    ("History.us", "aynascope-history-english-lead", "https://tvsen5.aynascope.net/historyen/index.m3u8", "konanda-sg/Mrgify-Tv; History English, US-East identity unconfirmed"),
    ("DisneyChannel.us", "aynascope-disney-ambiguous-lead", "https://tvsen7.aynascope.net/disney/index.m3u8", "konanda-sg/Mrgify-Tv; Disney Channel label conflicts with another directory's Disney Junior label"),
    ("NationalGeographic.us", "aynascope-natgeo-unverified-lead", "https://tvsen6.aynascope.net/natgeo/index.m3u8", "konanda-sg/Mrgify-Tv; Nat Geo TV, US-East identity unconfirmed"),
]

def probe_once(url: str, attempt: int, duration_seconds: int = 12) -> dict:
    cmd = [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
        "-rw_timeout", "10000000", "-analyzeduration", "6000000",
        "-probesize", "8000000", "-i", url,
        "-map", "0:v:0", "-an", "-t", str(duration_seconds),
        "-vf", "fps=2,scale=160:-2", "-f", "framemd5", "-"
    ]
    begin = time.monotonic()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=max(32, duration_seconds + 35), check=False)
        hashes = []
        for line in p.stdout.splitlines():
            if line.startswith("#"):
                continue
            cells = [part.strip() for part in line.split(",")]
            if len(cells) >= 6 and re.fullmatch("[0-9a-f]{32}", cells[-1]):
                hashes.append(cells[-1])
        # An identical 2-second (4-frame) sequence recurring within one run
        # is a warning of a short repeated segment rather than live progression.
        windows = [tuple(hashes[i:i+4]) for i in range(0, len(hashes)-3, 4)]
        obvious_loop = len(windows) >= 3 and len(set(windows)) < len(windows)
        passed = p.returncode == 0 and len(hashes) >= max(14, int(duration_seconds * 1.2)) and len(set(hashes)) >= 4 and not obvious_loop
        return {
            "attempt": attempt, "duration_requested_seconds": duration_seconds, "passed": passed, "decoded_frames": len(hashes),
            "unique_frame_hashes": len(set(hashes)), "short_repeat_warning": obvious_loop,
            "elapsed_seconds": round(time.monotonic()-begin, 2),
            "exit_code": p.returncode, "error_tail": p.stderr[-850:],
            "sample_fingerprint": hashlib.sha256((",".join(hashes[:12])).encode()).hexdigest()[:14],
        }
    except subprocess.TimeoutExpired:
        return {"attempt": attempt, "passed": False, "error_tail": f"ffmpeg timed out after {max(32, duration_seconds + 35)} seconds"}
    except Exception as exc:
        return {"attempt": attempt, "passed": False, "error_tail": type(exc).__name__ + ": " + str(exc)[:300]}

def check(candidate: tuple[str, str, str, str]) -> dict:
    channel, name, url, origin = candidate
    attempts = [probe_once(url, 1)]
    if attempts[0]["passed"]:
        time.sleep(4)
        attempts.append(probe_once(url, 2))
    passed = len(attempts) == 2 and all(x["passed"] for x in attempts)
    if passed and attempts[0]["sample_fingerprint"] == attempts[1]["sample_fingerprint"]:
        passed = False
        attempts[-1]["identical_restart_warning"] = True
    return {
        "tvg_id": channel, "candidate": name, "host": urlsplit(url).hostname,
        "source_reference": origin, "url": url, "two_probe_media_pass": passed,
        "identity_confirmed": False, "provider_independence_confirmed": False,
        "attempts": attempts,
    }

def main() -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required")
    start = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(check, CANDIDATES))
    # A true continuity test is substantially longer than the initial media
    # sanity probes. Exercise every 2/2 candidate over 65 seconds in parallel.
    eligible = [row for row in results if row["two_probe_media_pass"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        extended = list(executor.map(
            lambda row: probe_once(row["url"], 3, duration_seconds=65), eligible
        ))
    for row, longer in zip(eligible, extended):
        row["extended_continuity"] = longer
        row["extended_65s_media_pass"] = bool(longer["passed"])
    for row in results:
        row.setdefault("extended_65s_media_pass", False)

    by_channel = {}
    for item in results:
        by_channel.setdefault(item["tvg_id"], []).append(item)
    print("=== TARGETED DECODER / SHORT-REPEAT DIAGNOSTIC ===")
    for target, rows in by_channel.items():
        print("\n" + target)
        for row in rows:
            print("  " + row["candidate"] + " [" + row["host"] + "] => "
                  + ("2/2 media PASS" if row["two_probe_media_pass"] else "UNVERIFIED/FAILED"))
            for test in row["attempts"]:
                print("    " + str(test))
    output = {
        "version": 1, "built_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "purpose": "read-only candidate research; not production stream validation",
        "summary": {
            "candidates": len(results),
            "two_probe_media_pass": sum(r["two_probe_media_pass"] for r in results),
            "extended_65s_media_pass": sum(r["extended_65s_media_pass"] for r in results),
            "elapsed_seconds": round(time.monotonic()-start, 1),
            "note": "Two decodes and frame changes only; exact aired feed and independence remain unverified."
        }, "channels": by_channel
    }
    destination = Path("research/diagnostics/three-channel-probe.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print("\nDiagnostic saved:", destination)
    # Report candidate failures as diagnostic results, not a CI infrastructure failure.
    # The PR is not eligible for source promotion until identity/continuity QA passes.

if __name__ == "__main__":
    main()
