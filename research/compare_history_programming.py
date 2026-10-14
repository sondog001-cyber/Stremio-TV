#!/usr/bin/env python3
"""Read-only History East programme parity experiment; no source promotion.

Two live feeds are decoded simultaneously for ~96 seconds. Frames sampled
every two seconds are reduced to perceptual hashes and compared across
time shifts. Identical advertisements alone are not sufficient to establish
full East-channel identity.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

FEEDS = {
    "history_current_east": "http://212.5.144.156:8080/history/index.m3u8",
    "history_aynascope_english": "https://tvsen5.aynascope.net/historyen/index.m3u8",
}
WIDTH, HEIGHT, PERIOD, DURATION = 96, 54, 2, 96
FRAME_SIZE = WIDTH * HEIGHT
OUT = Path("research/diagnostics/history-programme-parity.json")


def dhash(gray):
    # 9x8 block-mean perceptual hash ignoring small logo overlays.
    row_width, col_height = WIDTH // 9, HEIGHT // 8
    brightness = []
    for r in range(8):
        for c in range(9):
            left, top = c * row_width, r * col_height
            values = []
            for y in range(top, min(top + col_height, HEIGHT)):
                offset = y * WIDTH + left
                values.extend(gray[offset:offset + row_width])
            brightness.append(sum(values) / max(1, len(values)))
    fingerprint = 0
    for row in range(8):
        for col in range(8):
            a = brightness[9 * row + col]
            b = brightness[9 * row + col + 1]
            fingerprint = (fingerprint << 1) | int(a > b)
    return fingerprint


def decode(item):
    name, url = item
    cmd = [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
        "-rw_timeout", "10000000", "-i", url,
        "-map", "0:v:0", "-an", "-t", str(DURATION),
        "-vf", f"fps=1/{PERIOD},scale={WIDTH}:{HEIGHT},format=gray",
        "-f", "rawvideo", "pipe:1",
    ]
    begin = time.monotonic()
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=135)
        frames = [p.stdout[i:i+FRAME_SIZE] for i in range(0, len(p.stdout) - FRAME_SIZE + 1, FRAME_SIZE)]
        return {
            "name": name, "exit_code": p.returncode, "frames": len(frames),
            "hashes": [dhash(f) for f in frames],
            "duration_seconds": round(time.monotonic() - begin, 1),
            "error": p.stderr.decode("utf-8", "replace")[-550:],
        }
    except subprocess.TimeoutExpired:
        return {"name": name, "frames": 0, "hashes": [], "error": "FFmpeg exceeded 135 seconds"}


def main():
    with ThreadPoolExecutor(max_workers=2) as executor:
        current, alternate = executor.map(decode, FEEDS.items())
    a, b = current["hashes"], alternate["hashes"]
    matches = []
    for x, ha in enumerate(a):
        for y, hb in enumerate(b):
            # two streams can be delayed by up to 40 seconds
            if abs(x - y) > 20:
                continue
            distance = (ha ^ hb).bit_count()
            if distance <= 10:
                matches.append({
                    "current_second": x * PERIOD,
                    "alternative_second": y * PERIOD,
                    "offset_seconds": (x-y) * PERIOD,
                    "hamming": distance,
                })
    # Consider at most one match per current-frame index, preferring lowest distance.
    best = {}
    for m in matches:
        t = m["current_second"]
        if t not in best or m["hamming"] < best[t]["hamming"]:
            best[t] = m
    unique = sorted(best.values(), key=lambda m: m["current_second"])
    spans = [m["current_second"] for m in unique]
    spread = max(spans) - min(spans) if spans else 0
    same_feed_evidence = len(unique) >= 5 and spread >= 30
    result = {
        "version": 1,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "description": "Concurrent low-resolution History US East / AynaScope comparison",
        "frames_current": current["frames"],
        "frames_alternative": alternate["frames"],
        "decoder_current": {k:v for k,v in current.items() if k != "hashes"},
        "decoder_alternative": {k:v for k,v in alternate.items() if k != "hashes"},
        "matches_below_hamming_10": len(unique),
        "matching_timespan_seconds": spread,
        "best_matches": unique[:50],
        "possible_same_programming": same_feed_evidence,
        "verified_exact_us_east": False,
        "limitations": (
            "Sampled 2-second frames may miss sync or shared ads may falsely "
            "suggest identical programming. This does not independently "
            "establish the regional schedule or provider rights."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "frames_current": current["frames"],
        "frames_alternative": alternate["frames"],
        "matches": len(unique),
        "matching_span_seconds": spread,
        "possible_same_programming": same_feed_evidence,
        "errors": [current["error"], alternate["error"]],
    }, indent=2))
    print("Report:", OUT)


if __name__ == "__main__":
    main()
