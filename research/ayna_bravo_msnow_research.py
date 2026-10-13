#!/usr/bin/env python3
"""Research-only probe of two GitHub-documented unsigned Ayna-family streams.

No credentials, token generation, DRM, proxy, restream or production changes.
An exact channel label does not establish the actual US linear feed identity.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
from research import fresh_origin_discovery as hls

SOURCES = {
    "Bravo.us": {
        "url": "http://tvsen7.aynascope.net/bravo/index.m3u8",
        "source": "https://github.com/Enkinuri666/enktel/blob/main/data/rosters/enktel-line-public.txt",
        "label": "Bravo US in independent playlist",
    },
    "MSNOW.us": {
        "url": "https://tvsen6.aynaott.com/msnbc/index.m3u8",
        "source": "https://github.com/Enkinuri666/enktel/blob/main/data/playlists/enktel-core.txt",
        "label": "MS NOW (formerly MSNBC); require linear identity validation",
    },
}
MD5_RE = re.compile(r"^\s*0,\s*[-\d]+,\s*[-\d]+,\s*\d+,\s*\d+,\s*([a-fA-F0-9]{32})\s*$")


def analyze_hashes(hashes):
    freeze = streak = 0
    previous = None
    for frame in hashes:
        streak = streak + 1 if frame == previous else 1
        freeze = max(freeze, streak)
        previous = frame
    repeated = []
    for size in (2, 3, 4):
        for i in range(len(hashes) - 2*size + 1):
            if hashes[i:i+size] == hashes[i+size:i+2*size] and len(set(hashes[i:i+size])) > 1:
                repeated.append(size)
                break
    return {
        "frames": len(hashes),
        "unique_frames": len(set(hashes)),
        "max_static_seconds": freeze,
        "short_loops_detected": sorted(set(repeated)),
        "decoder_continuity_pass": len(hashes) >= 50 and freeze < 10 and not repeated,
    }


def decode_direct(url):
    # No raw FFmpeg stdout, stderr, or URL is placed into the diagnostic artifact.
    args = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", url, "-t", "60", "-map", "0:v:0", "-an",
        "-vf", "fps=1,scale=160:90,format=gray",
        "-f", "framemd5", "pipe:1",
    ]
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=135, check=False)
        hashes = [m.group(1).lower() for line in done.stdout.splitlines()
                  if (m := MD5_RE.match(line))]
        metrics = analyze_hashes(hashes)
        return {"decoder_return_code": done.returncode,
                **metrics,
                "passed": done.returncode == 0 and metrics["decoder_continuity_pass"]}
    except (OSError, subprocess.TimeoutExpired) as err:
        return {"passed": False, "error_type": type(err).__name__}


def check(channel, do_decode=True):
    if channel not in SOURCES:
        raise ValueError("Unreviewed target")
    source = SOURCES[channel]
    url = source["url"]
    if not hls.valid_public_url(url) or "?" in url or "@" in url:
        raise ValueError("Credentialed or unsafe source")
    # Only two audited, exact paths are tested; no guessed channel slugs.
    p = hls.probe_manifest(url)
    result = {
        "channel": channel,
        "entry_host": hls.host(url),
        "entry_family": hls.host_family(hls.host(url)),
        "url_fingerprint_12": hashlib.sha256(url.encode()).hexdigest()[:12],
        "github_source": source["source"],
        "source_label": source["label"],
        "preflight_stage": p.get("stage"),
        "preflight_http_status": p.get("http_status"),
        "manifest_host": p.get("final_host"),
        "media_host": p.get("media_host"),
        "sequence_before": p.get("sequence_before"),
        "sequence_after": p.get("sequence_after"),
        "decoder": {"skipped": "manifest/segment preflight did not pass"},
        "exact_us_linear_programming_verified": False,
        "production_promotion": False,
        "local_test_promotion": False,
    }
    if do_decode and p.get("stage") == "progressing-hls-readable-not-decoded":
        result["decoder"] = decode_direct(url)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True, choices=sorted(SOURCES))
    ap.add_argument("--output", default="research-results/ayna-hosts")
    args = ap.parse_args()
    result = check(args.channel)
    result["checked_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    dest = pathlib.Path(args.output)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / (args.channel.replace(".", "-") + ".json")).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
