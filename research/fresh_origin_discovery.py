#!/usr/bin/env python3
"""Research-only exact-channel *discovery*; never changes production or approves a feed.

Run four six-channel groups separately. Use the last successful production stream-health
artifact for host-level deduplication, not only the repo's few hand-curated streams.
A playlist entry's hostname is not proof of an independent *original video* origin.
"""
import argparse
import datetime as dt
import ipaddress
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

BATCHES = {
    "A": ["Bravo.us", "KYW.us", "WCAU.us", "WPVI.us", "CinemaxClassics.us", "HBOMovies.us"],
    "B": ["BET.us", "CBSSportsNetwork.us", "CNBC.us", "ESPNews.us", "MSNOW.us", "Nicktoons.us"],
    "C": ["HallmarkFamily.us", "HallmarkMystery.us", "StarzCinema.us", "StarzComedy.us", "StarzEdge.us", "StarzEncoreSpanish.us"],
    "D": ["RFDTV.us", "SmithsonianChannel.us", "SundanceTV.us", "WPHL.us", "NBCSportsPhiladelphiaPlus.us", "WPSG.us"],
}
PRIVATE_IDS = {"NBCSportsPhiladelphiaPlus.us", "WPSG.us"}
# Each is a specific recently active SMALL research source; no giant IPTV-org mirrors.
SEEDS = [
    {"name": "FSTV24", "url": "https://raw.githubusercontent.com/abusaeeidx/IPTV-Scraper-Zilla/main/FSTV24.m3u8",
     "repo": "abusaeeidx/IPTV-Scraper-Zilla", "source_type": "third-party-scraped-unverified"},
    {"name": "SOFAST", "url": "https://raw.githubusercontent.com/abusaeeidx/IPTV-Scraper-Zilla/main/SOFAST.m3u",
     "repo": "abusaeeidx/IPTV-Scraper-Zilla", "source_type": "third-party-scraped-unverified"},
    {"name": "MoreScreens", "url": "https://raw.githubusercontent.com/abusaeeidx/IPTV-Scraper-Zilla/main/MoreScreens.m3u",
     "repo": "abusaeeidx/IPTV-Scraper-Zilla", "source_type": "third-party-scraped-unverified"},
    {"name": "Pixelsports", "url": "https://raw.githubusercontent.com/abusaeeidx/IPTV-Scraper-Zilla/main/Pixelsports.m3u",
     "repo": "abusaeeidx/IPTV-Scraper-Zilla", "source_type": "third-party-scraped-unverified"},
    {"name": "CricHD", "url": "https://raw.githubusercontent.com/abusaeeidx/IPTV-Scraper-Zilla/main/CricHD.m3u",
     "repo": "abusaeeidx/IPTV-Scraper-Zilla", "source_type": "third-party-scraped-unverified"},
    {"name": "BD", "url": "https://raw.githubusercontent.com/abusaeeidx/IPTV-Scraper-Zilla/main/BD.m3u",
     "repo": "abusaeeidx/IPTV-Scraper-Zilla", "source_type": "third-party-scraped-unverified"},
    {"name": "chyz-US", "url": "https://raw.githubusercontent.com/cihan53/chyz-iptv/master/US/index.m3u",
     "repo": "cihan53/chyz-iptv", "source_type": "community-playlist"},
    {"name": "Insolence-go", "url": "https://raw.githubusercontent.com/InsolenceWillow/insolencetvgo/main/playlist%20(2).m3u8",
     "repo": "InsolenceWillow/insolencetvgo", "source_type": "community-playlist"},
    {"name": "CeresLabX", "url": "https://raw.githubusercontent.com/CeresLabX/us-tv/main/playlist.m3u",
     "repo": "CeresLabX/us-tv", "source_type": "iptv-org-derivative-dedup-comparison"},
]
# The source has NO tvg-id; these are explicitly evaluated NAME hints, never automatic
# proof of exact network identity. Keep MS NOW/MSNBC especially marked provisional.
SOURCE_NAME_HINTS = {
    "ori2usacbssport": "CBSSportsNetwork.us",
    "ori2usespnnews": "ESPNews.us",
    "ori2usacnbc": "CNBC.us",
    "ori2usmsnbc": "MSNOW.us",
}
DEFAULT_AGENT = "Stremio-TV-Research-Fresh-Origin-Discovery/1.0"
MAX_PLAYLIST = 600000
MAX_MEDIA_MANIFEST = 100000

def canonical(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower().split("@")[0])

def host(url):
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower()
    except Exception:
        return ""

def host_family(h):
    # Family grouping is intentionally conservative; not a legal registrable-domain checker.
    if not h:
        return ""
    try:
        ipaddress.ip_address(h)
        return h
    except ValueError:
        pass
    parts = h.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else h

def valid_public_url(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    if p.username is not None or p.password is not None:
        return False
    # Third-party lists may place subscriber IDs/emails and secret account numbers in
    # plain path segments rather than RFC userinfo. Reject before requesting/logging.
    if "@" in urllib.parse.unquote(p.path):
        return False
    if re.search(r"/(?:api/)?(?:stream|streams|play|live)/[^/]+/[^/]+/", p.path, re.I):
        return False
    qs = urllib.parse.parse_qs(p.query, keep_blank_values=True)
    if any(k.lower() in {"un", "user", "username", "pass", "password", "pwd"} for k in qs):
        return False
    if re.search(r"/(?:live|movie|series)/[^/]+/[^/]+/[0-9]+(?:\.[a-z0-9]+)?$", p.path, re.I):
        return False
    if p.hostname.lower() in {"localhost"} or p.hostname.endswith((".local", ".internal")):
        return False
    try:
        if not ipaddress.ip_address(p.hostname).is_global:
            return False
    except ValueError:
        pass
    return True

class PublicRedirectOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not valid_public_url(newurl):
            raise ValueError("redirect-not-public-or-credentialed")
        return super().redirect_request(req, fp, code, msg, headers, newurl)

OPENER = urllib.request.build_opener(PublicRedirectOnly)

def fetch(url, limit, timeout=9):
    if not valid_public_url(url):
        raise ValueError("unsafe-input-URL")
    request = urllib.request.Request(url, headers={"User-Agent": DEFAULT_AGENT})
    with OPENER.open(request, timeout=timeout) as response:
        final = response.geturl()
        if not valid_public_url(final):
            raise ValueError("unsafe-final-URL")
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError("response-byte-limit")
        return {"status": response.status, "final": final, "data": data}

def parse_m3u(text):
    inf = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF"):
            inf = line
        elif inf and line and not line.startswith("#"):
            meta = inf.split(",", 1)
            name = meta[1].strip() if len(meta) > 1 else ""
            match = re.search(r'tvg-id\s*=\s*["\x27]([^"\x27]*)', inf, re.I)
            yield {"tvg_id": match.group(1).strip() if match else "", "name": name, "url": line}
            inf = None

def exact_target(entry, targets):
    channel_id = entry["tvg_id"]
    if channel_id:
        for target in targets:
            if canonical(channel_id) == canonical(target):
                return target, "tvg-id-provisional-identity"
        return None, "different-tvg-id"
    hint = SOURCE_NAME_HINTS.get(canonical(entry["name"]))
    return (hint, "name-hint-unverified-identity") if hint in targets else (None, "no-exact-id-or-allowlisted-hint")

def load_known_paths():
    known_hosts, blocked_urls = set(), set()
    known_families = set()
    try:
        conf = json.loads(pathlib.Path("config.json").read_text(encoding="utf-8"))
        blocked_urls.update((conf.get("safety_controls") or {}).get("disabled_urls") or [])
        for seed in ((conf.get("discovery") or {}).get("seed_candidates") or []):
            if isinstance(seed, dict) and seed.get("url"):
                known_hosts.add(host(seed["url"]))
    except (OSError, ValueError, TypeError):
        pass
    try:
        manual = json.loads(pathlib.Path("manual_sources.json").read_text(encoding="utf-8"))
        for item in manual.get("streams", []):
            if isinstance(item, dict) and item.get("url"):
                known_hosts.add(host(item["url"]))
    except (OSError, ValueError, TypeError):
        pass
    return known_hosts, blocked_urls, known_families

def enrich_known_from_artifact(path, known_hosts, known_families):
    try:
        rows = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(rows, list):
        return False
    for row in rows:
        u = row.get("effective_url") or row.get("url") or ""
        if u:
            known_hosts.add(host(u))
        f = row.get("family")
        if f:
            known_families.add(str(f))
    return True

def parse_hls_snapshot(text):
    """Inspect public HLS syntax without mistaking a master, VOD or HTML for live media."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or lines[0].lstrip("\ufeff") != "#EXTM3U":
        return {"kind": "invalid"}
    if any(x.startswith(("#EXT-X-KEY:", "#EXT-X-SESSION-KEY:")) for x in lines):
        return {"kind": "encrypted-or-keyed"}
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF:"):
            variant = next((x for x in lines[i+1:] if not x.startswith("#")), "")
            return {"kind": "master", "variant": variant}
    if "#EXT-X-ENDLIST" in lines:
        return {"kind": "on-demand-not-live"}
    if not any(x.startswith("#EXTINF:") for x in lines):
        return {"kind": "not-standard-media"}
    segments = [x for x in lines if not x.startswith("#")]
    if len(segments) < 2:
        return {"kind": "not-enough-segments"}
    match = re.search(r"(?m)^#EXT-X-MEDIA-SEQUENCE:(\d+)", text)
    duration = re.search(r"(?m)^#EXT-X-TARGETDURATION:(\d+)", text)
    return {"kind": "media", "sequence": int(match.group(1)) if match else None,
            "segments": segments, "target_duration": int(duration.group(1)) if duration else 6}


def media_snapshot(url):
    """Follow only validated public HLS variant references (maximum two levels)."""
    current = url
    for _ in range(3):
        p = fetch(current, MAX_MEDIA_MANIFEST, timeout=10)
        parsed = parse_hls_snapshot(p["data"].decode("utf-8-sig", "replace"))
        if parsed["kind"] != "master":
            return p, parsed
        current = urllib.parse.urljoin(p["final"], parsed["variant"])
        if not parsed["variant"] or not valid_public_url(current):
            raise ValueError("unsafe-or-empty-variant")
    raise ValueError("excessive-master-indirection")


def fetch_media_sample(url):
    """Read at most 2KB from a direct segment; never save, proxy or retransmit video."""
    if not valid_public_url(url):
        raise ValueError("unsafe-media-segment-url")
    req = urllib.request.Request(
        url, headers={"User-Agent": DEFAULT_AGENT, "Range": "bytes=0-2047"})
    with OPENER.open(req, timeout=10) as response:
        final_url = response.geturl()
        if response.status not in (200, 206) or not valid_public_url(final_url):
            raise ValueError("bad-or-unsafe-media-segment-response")
        prefix = response.read(2048)
        if len(prefix) < 188 or prefix.lstrip().lower().startswith(
                (b"<html", b"<!doctype html", b"#extm3u")):
            raise ValueError("media-segment-unreadable")
        return {"readable": True, "final_media_host": host(final_url)}


def probe_manifest(url):
    """Isolated *preflight*, not authorization, exact-ID verification or decoder QA.

    Require two readable live media manifests showing actual segment-window movement
    plus nonempty segment bytes. Never mark production eligible based on this alone.
    """
    try:
        first, before = media_snapshot(url)
        base = {"http_status": first["status"], "final_host": host(first["final"]),
                "final_family": host_family(host(first["final"])),
                "redirected": first["final"] != url,
                "hls_header": before["kind"] != "invalid",
                "hls_kind": before["kind"]}
        if before["kind"] != "media":
            return dict(base, stage="not-live-readable-hls")
        delay = min(15, max(6, before["target_duration"] * 1.5))
        time.sleep(delay)
        second, after = media_snapshot(url)
        if after["kind"] != "media":
            return dict(base, stage="second-media-manifest-unreadable")
        seq_advanced = before["sequence"] is not None and after["sequence"] is not None and (
            after["sequence"] > before["sequence"])
        segment_advanced = after["segments"][-1] != before["segments"][-1]
        if not (seq_advanced or segment_advanced):
            return dict(base, stage="hls-window-not-progressing",
                        sequence_before=before["sequence"], sequence_after=after["sequence"])
        segment_url = urllib.parse.urljoin(second["final"], after["segments"][-1])
        sample = fetch_media_sample(segment_url)
        return dict(base, stage="progressing-hls-readable-not-decoded",
                    sequence_before=before["sequence"], sequence_after=after["sequence"],
                    media_host=sample["final_media_host"], media_bytes_readable=True,
                    original_video_origin_verified=False, authorized_origin_confirmed=False)
    except Exception as exc:
        code = getattr(exc, "code", None)
        return {"http_status": code, "stage": "manifest-or-segment-unavailable",
                "error": type(exc).__name__ + ": " + str(exc)[:160]}

def run(batch, artifact):
    targets = BATCHES[batch]
    known_hosts, disabled, known_families = load_known_paths()
    baseline_loaded = enrich_known_from_artifact(artifact, known_hosts, known_families)
    results = []
    read_sources = []
    for seed in SEEDS:
        try:
            fetched = fetch(seed["url"], MAX_PLAYLIST)
            text = fetched["data"].decode("utf-8-sig", "replace")
            entries = list(parse_m3u(text))
            read_sources.append({"name": seed["name"], "entries": len(entries), "status": "ok"})
        except Exception as exc:
            read_sources.append({"name": seed["name"], "status": type(exc).__name__,
                                 "error": str(exc)[:120]})
            continue
        for entry in entries:
            tvg_id, evidence = exact_target(entry, targets)
            if not tvg_id or tvg_id in PRIVATE_IDS:
                continue
            url = entry["url"]
            h = host(url)
            if not valid_public_url(url):
                state = "reject-credentials-private-or-unsupported"
            elif url in disabled:
                state = "reject-exact-disabled-url"
            elif h in known_hosts:
                state = "existing-host-not-new-origin"
            else:
                state = "new-entry-host-unknown-video-origin"
            results.append({
                "channel": tvg_id, "batch": batch,
                "name": entry["name"], "tvg_id_from_playlist": entry["tvg_id"],
                "identity_evidence": evidence, "source": seed["name"],
                "source_repo": seed["repo"],
                "url": url if "reject-credentials" not in state else "[excluded: credentialed/private]",
                "entry_host": h, "entry_host_family": host_family(h),
                "host_known_in_deployed_diagnostics": h in known_hosts,
                "discovery_class": state, "authorized_origin_confirmed": False,
                "verified_channel_identity": False, "production_eligible": False,
            })
    # Same URL in multiple discovery repos is one lead, not independent origins.
    uniq = {}
    for row in results:
        key = (row["channel"], row["url"])
        uniq.setdefault(key, row)
    results = list(uniq.values())
    # Probe at most two distinct new-host families per channel per run:
    # never repeatedly hit duplicate mirrors, and never mass-probe a provider.
    probed_groups = set()
    probed_by_channel = Counter()
    for row in results:
        if row["discovery_class"] == "new-entry-host-unknown-video-origin":
            group = (row["channel"], row["entry_host_family"])
            if group in probed_groups or probed_by_channel[row["channel"]] >= 2:
                row["manifest_probe"] = {"stage": "not-probed-limit-or-duplicate-family"}
                row["discovery_class"] = "new-host-awaiting-research-probe"
                continue
            probed_groups.add(group)
            probed_by_channel[row["channel"]] += 1
            row["manifest_probe"] = probe_manifest(row["url"])
            final = row["manifest_probe"].get("final_host")
            if final and final in known_hosts:
                row["discovery_class"] = "redirects-to-known-host"
            elif final and final != row["entry_host"]:
                row["discovery_class"] = "redirects-to-different-unverified-host"
            elif row["manifest_probe"]["stage"] != "progressing-hls-readable-not-decoded":
                row["discovery_class"] = "new-host-manifest-unavailable"
    channel_rows = []
    for tvg_id in targets:
        matches = [r for r in results if r["channel"] == tvg_id]
        channel_rows.append({
            "tvg_id": tvg_id, "seed_matches": len(matches),
            "fresh_host_leads": sum(r["discovery_class"] in
                                   ("new-entry-host-unknown-video-origin",
                                    "redirects-to-different-unverified-host",
                                    "new-host-manifest-unavailable",
                                    "new-host-awaiting-research-probe") for r in matches),
            "state": "private-connector-only" if tvg_id in PRIVATE_IDS else
                     ("new-host-found-manifest-inaccessible" if any(
                         r["discovery_class"] == "new-host-manifest-unavailable"
                         for r in matches) else
                     ("new-entry-host-lead-unverified" if any(
                         r["discovery_class"] == "new-entry-host-unknown-video-origin"
                         for r in matches) else "no-proven-fresh-origin")),
        })
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "batch": batch, "target_ids": targets,
        "production_baseline": "last successful run #38316450648 (87/111)",
        "baseline_artifact_loaded": baseline_loaded,
        "known_media_hosts_count": len(known_hosts),
        "sources": read_sources,
        "channels": channel_rows,
        "candidates": results,
        "summary": {
            "channels": len(targets), "seed_matches": len(results),
            "novel_entry_hosts_found": sorted({r["entry_host"] for r in results
                 if r["discovery_class"] in ("new-entry-host-unknown-video-origin",
                     "redirects-to-different-unverified-host", "new-host-manifest-unavailable",
                     "new-host-awaiting-research-probe")}),
            "manifest_observed_hosts": sorted({r["entry_host"] for r in results
                 if (r.get("manifest_probe") or {}).get("stage") ==
                 "manifest-observed-not-decoded"}),
            "unreachable_new_hosts": sorted({r["entry_host"] for r in results
                 if r["discovery_class"] == "new-host-manifest-unavailable"}),
            "streams_full_QA_passed": 0, "streams_promoted": 0,
        },
        "rule": "Unverified discovery only. No DRM/login/credential bypass, no restreaming. "
                "Manifest headers do not prove video decode, linear identity, rights, or final video origin.",
    }
    print(json.dumps({"batch": batch, "summary": report["summary"],
                      "probes": [{"channel": x["channel"], "host": x["entry_host"],
                                  "stage": (x.get("manifest_probe") or {}).get("stage")}
                                 for x in results]}, indent=2))
    return report

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--batch", choices=list(BATCHES), required=True)
    p.add_argument("--baseline", default=".research-baseline/diagnostics/stream-health.json")
    p.add_argument("--out", default="research-results")
    args = p.parse_args()
    pathlib.Path(args.out).mkdir(parents=True, exist_ok=True)
    doc = run(args.batch, args.baseline)
    pathlib.Path(args.out, f"fresh-origin-batch-{args.batch}.json").write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
