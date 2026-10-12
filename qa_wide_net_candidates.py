#!/usr/bin/env python3
"""Research-only HLS probes for explicitly pinned public candidate URLs.

No source writes, token minting, proxied playback, DRM/key requests, or login.
Any result is an isolated sample, NOT a production FFmpeg/identity QA pass.
All endpoints and child HLS URIs must resolve to PUBLIC IP addresses.
"""
import concurrent.futures
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "Stremio-TV-readonly-QA/0.8 (public HLS investigation)"
MAX_MANIFEST = 400000
MAX_SEGMENT = 2500000
TIMEOUT = 9
MAX_PER_HOST = 30  # safety guard: small isolated candidate set
REPORT = Path("qa-results/qa-wide-net-20261012.json")


class UnsafeTarget(Exception):
    pass


def public_url(url):
    u = urllib.parse.urlsplit(str(url))
    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password:
        raise UnsafeTarget("invalid scheme, host, or embedded credentials")
    if u.port and u.port not in (80, 443, 9443):
        raise UnsafeTarget("nonstandard port not permitted in research runner")
    try:
        addresses = socket.getaddrinfo(u.hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeTarget("DNS lookup failed: " + str(exc)[:100])
    if not addresses:
        raise UnsafeTarget("hostname resolved to no addresses")
    for result in addresses:
        ip = ipaddress.ip_address(result[4][0])
        if not ip.is_global:
            raise UnsafeTarget("target or redirect is not a global IP")
    return url


class CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


opener = urllib.request.build_opener(CheckedRedirect())


def grab(url, limit=MAX_MANIFEST):
    public_url(url)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "*/*", "Cache-Control": "no-cache",
    })
    with opener.open(req, timeout=TIMEOUT) as response:
        effective = response.geturl()
        public_url(effective)
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError("response exceeds byte limit")
        return data, effective, response.headers.get("Content-Type", ""), response.status


def parse_m3u(text, base):
    if not text.lstrip("\ufeff\n\r ").startswith("#EXTM3U"):
        raise ValueError("not an M3U manifest (possibly HTML or a gateway)")
    lines = [v.strip() for v in text.splitlines() if v.strip()]
    if any(x.startswith("#EXT-X-KEY:") and "METHOD=NONE" not in x for x in lines):
        raise ValueError("encrypted HLS / keys are excluded from this isolated probe")
    if "#EXT-X-STREAM-INF" in text:
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines):
                return {"kind": "master", "next": urllib.parse.urljoin(base, lines[i+1])}
    if any(line.startswith("#EXTINF:") for line in lines):
        segments = [urllib.parse.urljoin(base, line) for line in lines if not line.startswith("#")]
        seq = next((line.partition(":")[2] for line in lines
                    if line.startswith("#EXT-X-MEDIA-SEQUENCE:")), "")
        return {"kind": "media", "segments": segments, "sequence": seq,
                "endlist": "#EXT-X-ENDLIST" in text}
    raise ValueError("not a recognized HLS master or media manifest")


def media_manifest(url):
    seen = set()
    for hop in range(3):
        if url in seen:
            raise ValueError("cyclic variant playlist")
        seen.add(url)
        content, final, mime, status = grab(url)
        text = content.decode("utf-8", "replace")
        parsed = parse_m3u(text, final)
        if parsed["kind"] == "media":
            return parsed, final, mime
        url = parsed["next"]
    raise ValueError("too many nested variant playlists")


def decode_segments(path):
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostdin", "-v", "info", "-i", str(path),
             "-t", "15", "-f", "null", "-"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=18)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, str(e)[:120]
    log = proc.stderr or ""
    frames = [int(v) for v in re.findall(r"frame=\s*(\d+)", log)]
    return proc.returncode == 0 and max(frames or [0]) > 0, (
        f"exit={proc.returncode} frames={max(frames or [0])}")


def test_one(item):
    result = {
        "tvg_id": item["tvg_id"],
        "claimed_tvg_id": item.get("claimed_tvg_id"),
        "family": item.get("playlist_family"),
        "initial_host": urllib.parse.urlsplit(item["url"]).hostname,
        "candidate_url": item["url"],
        "qa_class": "not_tested",
        "manifest_ok": False,
        "segments_tested": 0,
        "decode_sample_ok": False,
        "manifest_progressed": False,
        "proven_authorized": False,
        "proven_exact_content": False,
        "proven_independent_origin": False,
        "production_eligible": False,
    }
    if item.get("policy_skip"):
        result.update(qa_class="excluded_policy",detail="suspected proxy/gateway or unsupported URL")
        return result
    try:
        current, final, mime = media_manifest(item["url"])
        result["manifest_ok"] = True
        result["media_host"] = urllib.parse.urlsplit(final).hostname
        result["manifest_content_type"] = mime
        result["first_media_sequence"] = current.get("sequence")
        if current.get("endlist"):
            result.update(qa_class="on_demand_not_live",detail="HLS VOD endlist")
            return result
        segments = current.get("segments") or []
        if not segments:
            raise ValueError("no segments")
        chosen = segments[-3:]
        blobs = []
        with tempfile.TemporaryDirectory() as temp:
            for i, url in enumerate(chosen):
                # Exclude encrypted, PNG-wrapped, HTML and unsupported non-TS segments.
                suffix = urllib.parse.urlsplit(url).path.lower()
                if not suffix.endswith((".ts", ".mpegts", ".m2ts", ".mp4", ".m4s")):
                    raise ValueError("unsupported/disguised segment type (no proxy/unwrap)")
                data, effective, content_type, status = grab(url, MAX_SEGMENT)
                if data.lstrip().startswith((b"<!DOCTYPE", b"<html")):
                    raise ValueError("segment response is HTML")
                blobs.append(data)
                result["segments_tested"] += 1
            if len(blobs) >= 2:
                hashes = [hashlib.sha256(b).hexdigest() for b in blobs]
                result["distinct_segment_samples"] = len(set(hashes))
                if len(set(hashes)) < len(hashes):
                    result["repeat_warning"] = "identical adjacent/current segment bytes"
            merged = Path(temp) / "sample.ts"
            merged.write_bytes(b"".join(blobs))
            decoded, detail = decode_segments(merged)
            result["decode_sample_ok"] = decoded
            result["decode_detail"] = detail
        time.sleep(9)
        next_manifest, _, _ = media_manifest(item["url"])
        result["second_media_sequence"] = next_manifest.get("sequence")
        current_ids = tuple(current.get("segments") or [])
        next_ids = tuple(next_manifest.get("segments") or [])
        result["manifest_progressed"] = (
            next_ids != current_ids or next_manifest.get("sequence") != current.get("sequence")
        )
        if decoded and result["manifest_progressed"] and not result.get("repeat_warning"):
            result["qa_class"] = "decode_sample_pass_unverified_identity_and_rights"
        elif decoded:
            result["qa_class"] = "decode_sample_pass_progress_or_repeat_warning"
        else:
            result["qa_class"] = "decoder_sample_failed"
    except urllib.error.HTTPError as exc:
        result.update(qa_class="http_error",http_status=exc.code,detail=str(exc)[:200])
    except Exception as exc:
        result.update(qa_class="probe_failed",detail=str(exc)[:230])
    return result


def main():
    data = json.loads(Path("research/qa-20261012-wide-net-candidates.json").read_text())
    items = data["candidates"]
    pairs = {(i["tvg_id"], i["url"]) for i in items}
    if len(pairs) != len(items):
        raise SystemExit("duplicate target URL")
    if len(items) > 40:
        raise SystemExit("too many candidates")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(test_one, items))
    counts = {}
    for result in rows:
        k = result["qa_class"]
        counts[k] = counts.get(k, 0) + 1
        print(f"{result['tvg_id']:<29} {result['initial_host']:<37} {k:<53} {str(result.get('http_status','')):<3}")
    report = {
        "scope": "research-only; never publish or count as production normal QA",
        "all_candidates_count": len(items),
        "tested_candidates": len(items) - sum(i.get("policy_skip", False) for i in items),
        "counts": counts,
        "results": rows,
        "warning": "Manifest/decode sample is NOT proof of content identity, rights, origin independence, or sustained Stremio playback.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print("QA REPORT: " + str(REPORT))
    print("COUNTS: " + json.dumps(counts))


if __name__ == "__main__":
    main()
