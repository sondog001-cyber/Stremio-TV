#!/usr/bin/env python3
"""Research-only HTTP/HLS/FFmpeg QA for the four 6-channel missing-source batches.

This script NEVER writes production configuration and never approves a stream.
No authentication, cookies, DRM, proxying or credentialed links.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import ipaddress
import json
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BATCHES = {
    "A": ["Bravo.us", "KYW.us", "WCAU.us", "WPVI.us", "CinemaxClassics.us", "HBOMovies.us"],
    "B": ["BET.us", "CBSSportsNetwork.us", "CNBC.us", "ESPNews.us", "MSNOW.us", "Nicktoons.us"],
    "C": ["HallmarkFamily.us", "HallmarkMystery.us", "StarzCinema.us", "StarzComedy.us", "StarzEdge.us", "StarzEncoreSpanish.us"],
    "D": ["RFDTV.us", "SmithsonianChannel.us", "SundanceTV.us", "WPHL.us", "NBCSportsPhiladelphiaPlus.us", "WPSG.us"],
}

# All candidates below are independently isolated research probes, not catalog entries.
CANDIDATES = [
    {
        "id": "bravo-historical-170", "batch": "A", "channel": "Bravo.us",
        "url": "http://170.254.18.106/BRAVO/index.m3u8",
        "provenance": "iptv-org historical issue #15891",
        "novelty": "historical-different-host-unverified",
    },
    {
        "id": "nicktoons-gateway", "batch": "B", "channel": "Nicktoons.us",
        "url": "https://sra72yz.s.gy/NICKTOONS_HD.m3u8",
        "provenance": "CeresLabX/us-tv public playlist",
        "novelty": "gateway-origin-unresolved-possible-iptv-org-duplicate",
    },
    {
        "id": "cbssn-known-40", "batch": "B", "channel": "CBSSportsNetwork.us",
        "url": "http://40.160.24.52/CBS_SPORTS_NETWORK/index.m3u8",
        "provenance": "iptv-org issue #44158; already in Stremio TV sources",
        "novelty": "known-existing-for-diagnostic-control",
    },
]
CONNECTION_TIMEOUT = 12
UA = "Stremio-TV-Research-Direct-HLS-QA/0.1"


def safe_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("unsupported-media-url")
    if parts.username or parts.password:
        raise ValueError("embedded-credentials")
    host = parts.hostname
    if host in {"localhost", "metadata.google.internal"} or host.endswith(".local"):
        raise ValueError("private-host")
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise ValueError("private-host")
    except ValueError as exc:
        if str(exc) == "private-host":
            raise
    return url


def origin(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    return (p.hostname or "").lower() + (":" + str(p.port) if p.port else "") + p.path.rstrip("/").lower()


def grab(url: str, max_bytes: int = 262144) -> dict:
    safe_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=CONNECTION_TIMEOUT) as response:
        final = response.geturl()
        safe_url(final)
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("body-too-large")
        return {
            "url": final, "status": response.status,
            "type": response.headers.get("content-type", ""),
            "data": data,
        }


def playlist(url: str) -> dict:
    v = grab(url)
    s = v["data"].decode("utf-8-sig", "replace")
    if not s.lstrip().startswith("#EXTM3U"):
        raise ValueError("not-an-hls-m3u8")
    if "#EXT-X-STREAM-INF" in s:
        lines = s.splitlines()
        variants = []
        for i, line in enumerate(lines):
            if line.strip().startswith("#EXT-X-STREAM-INF"):
                for nextline in lines[i + 1:]:
                    if nextline.strip() and not nextline.startswith("#"):
                        variants.append(urllib.parse.urljoin(v["url"], nextline.strip()))
                        break
        if not variants:
            raise ValueError("no-hls-variant")
        variant = playlist_variant(variants[0])
        variant["master_url"] = v["url"]
        variant["variants"] = len(variants)
        return variant
    return playlist_variant_content(v["url"], s)


def playlist_variant(url: str) -> dict:
    v = grab(url)
    return playlist_variant_content(v["url"], v["data"].decode("utf-8-sig", "replace"))


def playlist_variant_content(url: str, s: str) -> dict:
    if not s.lstrip().startswith("#EXTM3U") or "#EXT-X-MEDIA-SEQUENCE" not in s:
        raise ValueError("no-hls-media-sequence")
    m = re.search(r"(?m)^#EXT-X-MEDIA-SEQUENCE:\\s*(\\d+)", s)
    if not m:
        raise ValueError("invalid-hls-media-sequence")
    entries = [t.strip() for t in s.splitlines() if t.strip() and not t.startswith("#")]
    if not entries:
        raise ValueError("hls-no-segments")
    return {
        "url": url, "sequence": int(m.group(1)), "segments": len(entries),
        "tail": entries[-1], "is_vod": "#EXT-X-ENDLIST" in s,
        "target_duration": re.search(r"(?m)^#EXT-X-TARGETDURATION:(\\d+)", s).group(1) if "#EXT-X-TARGETDURATION:" in s else None,
    }


def video_decode(url: str) -> dict:
    if not shutil.which("ffmpeg"):
        return {"status": "not_run_ffmpeg_unavailable"}
    cmd = [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "info",
        "-rw_timeout", "10000000",
        "-i", url, "-t", "18", "-map", "0:v:0",
        "-an", "-sn", "-f", "null", "-",
    ]
    try:
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=42)
    except subprocess.TimeoutExpired:
        return {"status": "decode_timeout", "decoded_frames": 0}
    output = (process.stderr or "")[-10000:]
    frames = [int(m) for m in re.findall(r"frame=\\s*(\\d+)", output)]
    max_frames = max(frames, default=0)
    status = "video_decoded" if process.returncode == 0 and max_frames >= 45 else "decoder_no_sustained_video"
    return {"status": status, "decoded_frames": max_frames, "exit_code": process.returncode,
            "diagnostic_tail": output[-350:].replace("\\n", " ")}


def check(candidate: dict) -> dict:
    result = {key: candidate[key] for key in ("id", "batch", "channel", "provenance", "novelty")}
    url = candidate["url"]
    result.update({"url": url, "original_origin": origin(url), "qa": "failed_or_inconclusive",
                   "identity_verified": False, "production_promotion": False})
    try:
        v1 = playlist(url)
        result.update({"media_origin": origin(v1["url"]), "redirected_origin": origin(v1["url"]) != origin(url),
                       "initial_seq": v1["sequence"], "segments": v1["segments"],
                       "target_duration": v1["target_duration"], "is_vod": v1["is_vod"]})
        if v1["is_vod"]:
            result["failure"] = "VOD-not-live"; return result
        segment_url = urllib.parse.urljoin(v1["url"], v1["tail"])
        segment = grab(segment_url, max_bytes=3_000_000)
        data = segment["data"]
        if data.startswith((b"\\x89PNG", b"\\xff\\xd8\\xff", b"GIF8")) or b"<html" in data[:120].lower():
            result["failure"] = "segment-image-or-html"; return result
        if not data or len(data) < 256:
            result["failure"] = "empty-or-invalid-segment"; return result
        result.update({"segment_bytes": len(data), "segment_origin": origin(segment["url"]),
                       "segment_sha256_prefix": hashlib.sha256(data).hexdigest()[:14]})
        # Two separated manifest observations, not just HTTP 200.
        wait = max(10, min(15, int(v1["target_duration"] or 10)))
        time.sleep(wait)
        v2 = playlist_variant(v1["url"])
        result["next_seq"] = v2["sequence"]
        result["advanced"] = v2["sequence"] > v1["sequence"] or v2["tail"] != v1["tail"]
        if not result["advanced"]:
            result["failure"] = "playlist-not-advanced"; return result
        result["decoder"] = video_decode(v1["url"])
        if result["decoder"]["status"] == "video_decoded":
            result["qa"] = "preliminary_video_pass_not_full_60s_or_identity"
        else:
            result["failure"] = result["decoder"]["status"]
    except Exception as e:
        result["failure"] = type(e).__name__ + ": " + str(e)[:220]
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", choices=list(BATCHES), required=True)
    ap.add_argument("--output-dir", default="batch-qa-results")
    args = ap.parse_args()
    batch = args.batch
    candidate_rows = [x for x in CANDIDATES if x["batch"] == batch]
    results = []
    for index, row in enumerate(candidate_rows):
        print(f"[{batch}] {index + 1}/{len(candidate_rows)} {row['channel']} research QA", flush=True)
        results.append(check(row))
    channels = [{
        "id": channel, "candidates_tested": sum(r["channel"] == channel for r in results),
        "status": "probe_recorded" if any(r["channel"] == channel for r in results)
        else ("private_connector_required" if channel in
              {"NBCSportsPhiladelphiaPlus.us", "WPSG.us"} else "no_new_eligible_candidate"),
    } for channel in BATCHES[batch]]
    body = {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "batch": batch, "channels": channels, "results": results,
            "policy": "Research only. No origin or playback result alone validates broadcast identity or rights. "
                      "No production source promotion."}
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"missing-batch-{batch}.json").write_text(json.dumps(body, indent=2) + "\n")
    print(json.dumps({"batch": batch, "candidate_count": len(results),
                      "qa": [{"id": r["id"], "status": r["qa"], "failure": r.get("failure")}
                             for r in results]}, indent=2))


if __name__ == "__main__":
    main()
