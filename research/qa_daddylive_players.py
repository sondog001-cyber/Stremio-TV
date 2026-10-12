#!/usr/bin/env python3
"""Read-only six-player DaddyLive experiment (no changes to live addon).

Resolves through the project's *existing pinned local resolver* and samples only
direct upstream HLS. Never uses /api/live or /api/proxy, changes source lists,
unwraps PNG/WebP, downloads keys, or claims ownership/authorized redistribution.
"""
import concurrent.futures
import datetime as dt
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

CONFIG_PATH = Path("config.json")
OUTPUT = Path("qa-results/daddylive-six-player-research.json")
SERVERS = ("stream", "cast", "watch", "plus", "casting", "player")
RESOLVER = "http://127.0.0.1:3000"
TIMEOUT = 10
BUDGET_SECONDS = 660
MANIFEST_BYTES = 500000
SEGMENT_BYTES = 2200000
MAX_PER_PROVIDER = 3
USER_AGENT = "Mozilla/5.0 (Stremio-TV research-only playback QA)"
stop = threading.Event()
start = time.monotonic()
gate = threading.BoundedSemaphore(MAX_PER_PROVIDER)
stats_lock = threading.Lock()
transport_blocks = Counter()


def safe_public_url(url):
    split = urllib.parse.urlsplit(str(url))
    if split.scheme not in ("http", "https") or not split.hostname or split.username or split.password:
        raise ValueError("invalid or credential-bearing media URL")
    if split.port and split.port not in (80, 443, 8080, 8443, 9443):
        raise ValueError("nonstandard media port excluded")
    if split.hostname in ("localhost", "localhost.localdomain"):
        raise ValueError("non-public host")
    try:
        addresses = socket.getaddrinfo(split.hostname, None, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError):
        raise ValueError("media DNS resolution failed")
    if not addresses or any(not ipaddress.ip_address(rec[4][0]).is_global for rec in addresses):
        raise ValueError("non-public media IP address")
    return url


class CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


opener = urllib.request.build_opener(CheckedRedirect())


def get_media(url, *, referer=None, limit=MANIFEST_BYTES):
    safe_public_url(url)
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if referer and referer.startswith(("http://", "https://")):
        try:
            safe_public_url(referer)
        except ValueError:
            referer = None
        if referer:
            headers["Referer"] = referer
    with opener.open(urllib.request.Request(url, headers=headers), timeout=TIMEOUT) as resp:
        safe_public_url(resp.geturl())
        data = resp.read(limit + 1)
        if len(data) > limit:
            raise ValueError("media response exceeded size limit")
        return data, resp.geturl(), resp.status


def get_resolver(target, server):
    qs = urllib.parse.urlencode({"channel": target["channel_id"], "server": server})
    url = RESOLVER + "/api/resolve?" + qs
    with urllib.request.urlopen(url, timeout=14) as response:
        payload = json.loads(response.read(180000).decode("utf-8", "replace"))
    if not isinstance(payload, dict):
        raise ValueError("resolver response is not JSON object")
    return payload


def referer_from_vlc(command):
    value = re.search(r":http-referrer=['\"]([^'\"]+)['\"]", str(command or ""))
    return value.group(1) if value else None


def manifest_info(url, referer):
    seen = set()
    for _ in range(3):
        if url in seen:
            raise ValueError("cyclic HLS manifest")
        seen.add(url)
        data, final, code = get_media(url, referer=referer)
        body = data.decode("utf-8", "replace")
        lines = [x.strip() for x in body.splitlines() if x.strip()]
        if not lines or not lines[0].lstrip("\ufeff").startswith("#EXTM3U"):
            raise ValueError("not HLS manifest (HTML/error/unsupported)")
        if any(x.startswith("#EXT-X-KEY:") and "METHOD=NONE" not in x
               for x in lines) or any(x.startswith("#EXT-X-SESSION-KEY:") for x in lines):
            raise ValueError("encrypted HLS; no key fetching")
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF:") and i + 1 < len(lines):
                url = urllib.parse.urljoin(final, lines[i + 1])
                break
        else:
            segs = [urllib.parse.urljoin(final, x) for x in lines if not x.startswith("#")]
            if not any(line.startswith("#EXTINF:") for line in lines) or not segs:
                raise ValueError("not recognizable live media HLS")
            seq = next((x.partition(":")[2] for x in lines if x.startswith("#EXT-X-MEDIA-SEQUENCE:")), "")
            return {"final_host": urllib.parse.urlsplit(final).hostname, "segments": segs,
                    "sequence": seq, "endlist": "#EXT-X-ENDLIST" in lines}
    raise ValueError("too many nested variants")


def sample_decode(segment_urls, referer):
    samples = []
    hosts = set()
    for u in segment_urls[-2:]:
        pathname = urllib.parse.urlsplit(u).path.lower()
        if pathname.endswith((".png", ".webp", ".jpg", ".jpeg")):
            raise ValueError("image-wrapped segment requires proxy; excluded")
        if not pathname.endswith((".ts", ".m2ts", ".mpegts", ".m4s", ".mp4")):
            raise ValueError("nonstandard segment path/format needs unwrap; excluded")
        data, final, code = get_media(u, referer=referer, limit=SEGMENT_BYTES)
        hosts.add(urllib.parse.urlsplit(final).hostname)
        if data.startswith((b"\x89PNG\r\n\x1a\n", b"RIFF")) or data.lstrip().lower().startswith((b"<html", b"<!doctype")):
            raise ValueError("image wrapper or HTML segment; excluded")
        samples.append(data)
    if not samples:
        raise ValueError("no transport stream segments")
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "sample.ts"
        p.write_bytes(b"".join(samples))
        try:
            run = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin",
                 "-loglevel", "info", "-i", str(p), "-t", "15",
                 "-f", "null", "-"], capture_output=True, text=True, timeout=16)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            raise ValueError("FFmpeg timed out or missing")
    frames = [int(x) for x in re.findall(r"frame=\s*(\d+)", run.stderr or "")]
    good = run.returncode == 0 and max(frames or [0]) > 0
    return good, {"segment_hosts": sorted(hosts), "sample_segments": len(samples),
                  "ffmpeg_exit": run.returncode, "frames": max(frames or [0])}


def check_one(item):
    target, server = item
    row = {"tvg_id": target["tvg_id"], "channel_id": int(target["channel_id"]),
           "player": server, "status": "unattempted",
           "direct_manifest": False, "decoded_video": False, "manifest_progressed": False,
           "authorized_proven": False, "exact_content_proven": False,
           "independent_upstream_proven": False, "production_eligible": False}
    if stop.is_set() or time.monotonic() - start > BUDGET_SECONDS:
        row["status"] = "budget_or_global_breaker_skipped"
        return row
    with gate:
        if stop.is_set() or time.monotonic() - start > BUDGET_SECONDS:
            row["status"] = "budget_or_global_breaker_skipped"
            return row
        t0 = time.monotonic()
        try:
            result = get_resolver(target, server)
            direct = str(result.get("direct") or "")
            row["resolver_seconds"] = round(time.monotonic() - t0, 2)
            row["returned_direct"] = direct.startswith(("http://", "https://"))
            row["resolver_hls"] = bool(result.get("isHls"))
            row["media_host"] = urllib.parse.urlsplit(direct).hostname if direct else None
            row["expires_at_provided"] = bool(result.get("expiresAt"))
            if not row["returned_direct"]:
                row["status"] = "resolver_no_direct_url"
                return row
            if not row["resolver_hls"]:
                row["status"] = "resolver_non_hls"
                return row
            if "/api/live" in direct or "/api/proxy" in direct:
                row["status"] = "resolver_proxy_only"
                return row
            ref = referer_from_vlc(result.get("vlc"))
            row["referer_provided"] = bool(ref)
            first = manifest_info(direct, ref)
            row["direct_manifest"] = True
            row["effective_media_host"] = first["final_host"]
            row["media_sequence"] = first["sequence"]
            if first["endlist"]:
                row["status"] = "vod_not_live"
                return row
            decoded, details = sample_decode(first["segments"], ref)
            row.update(details)
            row["decoded_video"] = decoded
            if not decoded:
                row["status"] = "ffmpeg_no_video_frames"
                return row
            time.sleep(5)
            second = manifest_info(direct, ref)
            row["manifest_progressed"] = (
                second["sequence"] != first["sequence"] or second["segments"] != first["segments"]
            )
            row["status"] = ("direct_sample_decoded_progressed" if row["manifest_progressed"]
                             else "direct_sample_decoded_no_progress_observed")
        except urllib.error.HTTPError as e:
            row["status"] = "http_error"
            row["http_status"] = e.code
            if e.code == 429:
                stop.set()
                row["global_breaker_opened"] = True
        except (urllib.error.URLError, TimeoutError) as exc:
            row["status"] = "network_failure"
            row["detail"] = type(exc).__name__
        except Exception as exc:
            row["status"] = "rejected_or_unavailable"
            row["detail"] = str(exc)[:180]  # no signed URLs retained
        return row


def main():
    cfg = json.loads(CONFIG_PATH.read_text())
    targets = cfg["discovery"]["daddylive_resolver"]["targets"]
    order = ["FoxSports2.us", "MLBNetwork.us", "NBCSportsPhiladelphia.us",
             "HGTV.us", "FXX.us", "Nicktoons.us", "CBSSportsNetwork.us",
             "InvestigationDiscovery.us", "TLC.us", "DiscoveryChannel.us",
             "SmithsonianChannel.us", "MagnoliaNetwork.us"]
    by_id = {r["tvg_id"]: r for r in targets}
    priority = [by_id[x] for x in order if x in by_id]
    remaining = [r for r in targets if r["tvg_id"] not in set(order)]
    rows = []
    # Go channel-by-channel, not 114 concurrent requests against a shared mirror.
    # For each channel all six server types are considered, but access refusals
    # are not bypassed/retried and the global 429 breaker stops the test.
    for target in priority + remaining:
        if stop.is_set() or time.monotonic() - start > BUDGET_SECONDS:
            break
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            rows.extend(pool.map(check_one, [(target, x) for x in SERVERS]))
        print(target["tvg_id"] + ": " + ", ".join(
            x["player"] + "=" + x["status"] for x in rows[-6:]), flush=True)
        time.sleep(0.5)
    counts = Counter(row["status"] for row in rows)
    report = {
        "scope": "Read-only, isolated resolver/direct-HLS probes. Not production QA.",
        "resolver_flavor": "existing pinned sharoon7171/daddylive-stream-resolver",
        "targets_configured": len(targets),
        "channels_attempted": len({r["tvg_id"] for r in rows}),
        "player_slots_possible": len(targets) * len(SERVERS),
        "attempted_or_skipped_slots": len(rows),
        "global_rate_limit_breaker": stop.is_set(),
        "seconds": round(time.monotonic() - start, 2),
        "counts": dict(counts),
        "results": rows,
        "warning": "Samples do not prove rights, content identity, independent provider, or sustained player behavior. Never copy transient tokens to production; image-wrapped media is excluded.",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print("SUMMARY " + json.dumps({k: report[k] for k in (
        "targets_configured","channels_attempted","player_slots_possible","attempted_or_skipped_slots","global_rate_limit_breaker","counts")}), flush=True)


if __name__ == "__main__":
    main()
