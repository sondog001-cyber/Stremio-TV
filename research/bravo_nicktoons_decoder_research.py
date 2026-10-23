#!/usr/bin/env python3
"""Isolated, bounded FFmpeg decoder QA for two research-only HLS leads.

Samples one 60s direct HLS decode to framemd5; does not store, proxy, restream,
publish, authenticate, decrypt, or add candidates to the public addon.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = {
    "Bravo.us": "http://41.205.93.154/BRAVO/index.m3u8",
    "Nicktoons.us": "http://41.205.93.154/NICKTOONS/index.m3u8",
}
MD5_RE = re.compile(r"^\s*0,\s*[-\d]+,\s*[-\d]+,\s*\d+,\s*\d+,\s*([a-fA-F0-9]{32})\s*$")


def collect_hashes(text):
    """Every one-second frame from standard FFmpeg framemd5 output."""
    return [m.group(1).lower() for line in text.splitlines() if (m := MD5_RE.match(line))]


def inspect_hashes(hashes):
    loops = []
    for width in (2, 3, 4):
        consecutive = 0
        for i in range(len(hashes) - 2 * width + 1):
            if hashes[i:i + width] == hashes[i + width:i + 2 * width]:
                consecutive += 1
                if consecutive >= 2:
                    loops.append({"seconds_per_loop": width, "at_sample": i})
                    break
            else:
                consecutive = 0
    longest_freeze = 0
    run = 0
    previous = None
    for hash_value in hashes:
        run = run + 1 if hash_value == previous else 1
        longest_freeze = max(longest_freeze, run)
        previous = hash_value
    return {
        "sampled_frames": len(hashes), "distinct_frame_hashes": len(set(hashes)),
        "possible_short_loops": loops, "longest_identical_frame_run_seconds": longest_freeze,
        "decoder_continuity_pass": len(hashes) >= 50 and not loops and longest_freeze < 15,
    }


def run(channel, ffmpeg="ffmpeg"):
    if channel not in SOURCE:
        raise ValueError("Only two reviewed read-only research origins are allowed")
    args = [
        ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", SOURCE[channel],
        "-t", "60", "-map", "0:v:0", "-an",
        "-vf", "fps=1,scale=160:90,format=gray",
        "-f", "framemd5", "pipe:1",
    ]
    result = {
        "tvg_id": channel, "tested_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_host": "41.205.93.154",
        "source_family": "historical-41-205-93-154-relay",
        "request_headers": {}, "sample_seconds_requested": 60,
        "ffmpeg_decoded": False, "content_identity_confirmed": False,
        "original_broadcaster_origin_confirmed": False,
        "broadcast_rights_or_permission_confirmed": False,
        "public_addon_eligible": False, "promotions": 0,
    }
    try:
        complete = subprocess.run(args, capture_output=True, text=True, timeout=135, check=False)
        hashes = collect_hashes(complete.stdout)
        inspect = inspect_hashes(hashes)
        result.update(inspect)
        result["ffmpeg_return_code"] = complete.returncode
        result["ffmpeg_decoded"] = bool(complete.returncode == 0 and inspect["decoder_continuity_pass"])
        # No ffmpeg URLs or stdout copied to logs/artifacts; stderr may contain upstream secrets.
        result["ffmpeg_error_types"] = list(sorted(set(
            m.lower() for m in re.findall(
                r"(?i)(?:404|403|timed? out|connection refused|invalid data|server returned|not found|input/output error)",
                complete.stderr or ""
            )
        )))[:8]
    except subprocess.TimeoutExpired:
        result.update({"ffmpeg_return_code": None, "decoder_continuity_pass": False,
                       "error_type": "decoder-timeout"})
    except (OSError, ValueError) as exc:
        result.update({"ffmpeg_return_code": None, "decoder_continuity_pass": False,
                       "error_type": type(exc).__name__})
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--channel", choices=sorted(SOURCE), required=True)
    p.add_argument("--out", default="research-results/decoder")
    args = p.parse_args()
    dest = pathlib.Path(args.out)
    dest.mkdir(parents=True, exist_ok=True)
    report = run(args.channel)
    (dest / (args.channel.replace(".", "-") + ".json")).write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
