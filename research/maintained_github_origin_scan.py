#!/usr/bin/env python3
"""Independent GitHub-source lineage audit across all 24 missing US channels.

Read-only: only fixed GitHub playlist files and a tiny finite public HLS
preflight list. Does not decode, proxy, decrypt, or publish streams.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import re
import urllib.parse

from research import fresh_origin_discovery as hls

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "research" / "maintained-github-origin-registry-2026-10-12.json"
MAX_SOURCE_BYTES = 800_000


def load_registry(path=REGISTRY):
    obj = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    batches = obj["batches"]
    all_ids = [id for name in "ABCD" for id in batches[name]]
    if len(all_ids) != 24 or len(set(all_ids)) != 24 or set(all_ids) != set(obj["channels"]):
        raise ValueError("Exactly 24 disjoint original TVG target IDs are required")
    for tvg_id, metadata in obj["channels"].items():
        # Canonical current TVG ID must match itself, including suffixes like .us@East.
        if tvg_id not in metadata["aliases"]:
            metadata["aliases"].append(tvg_id)
    for source in obj["references"]:
        if not source["url"].startswith("https://raw.githubusercontent.com/"):
            raise ValueError("Only pinned public GitHub raw source files accepted")
    for item in obj["probes"]:
        if item["channel"] not in all_ids or not hls.valid_public_url(item["url"]):
            raise ValueError("Unsafe, embedded-credential, private or out-of-scope media candidate")
    return obj


def canonical(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).split("@", 1)[0].lower())


def identity(entry, channel_info):
    aliases = {canonical(s) for s in channel_info["aliases"]}
    tvgid = canonical(entry["tvg_id"])
    if tvgid in aliases and tvgid:
        return "explicit-tvg-id-or-legacy-alias-unverified"
    # Only exact name labels; do not force-match generic keywords.
    names = {canonical(s) for s in channel_info["names"]}
    if canonical(entry["name"]) in names:
        return "exact-name-only-unverified"
    return None


def family(url):
    if not hls.valid_public_url(url):
        return "reject-credential-or-unsupported-url"
    p = urllib.parse.urlsplit(url)
    hostname = (p.hostname or "").lower()
    path = p.path.lower()
    if hostname in ("tvpass.org", "www.tvpass.org") and path.startswith("/live/"):
        return "tvpass-watch-route-not-hls"
    if not (".m3u8" in path or ".ts" in path):
        return "not-media-manifest"
    if "newkso.ru" in hostname or hostname.endswith("mizhls.ru"):
        return "daddylive-delivery-wrapper-not-original-origin"
    if "moveonjoy" in hostname or "41.205.93.154" in hostname or "40.160.24." in hostname:
        return "known-or-historical-reseller-relay"
    if "23.237.104.106" in hostname:
        return "known-high-concentration-shared-host"
    if hostname.endswith("mybtv.net") or "theus6tv" in hostname:
        return "historical-localbtv"
    return "hls-entry-host-not-independent-origin-proof"


def source_rows(text):
    return list(hls.parse_m3u(text))


def map_source(source, rows, targets):
    out = collections.defaultdict(list)
    for entry in rows:
        for id, meta in targets.items():
            claim = identity(entry, meta)
            if not claim:
                continue
            url = entry["url"]
            clazz = family(url)
            # Never emit actual full URLs, cookies, signed tokens or account paths.
            if clazz.startswith("reject-"):
                host = "[excluded]"
            else:
                host = hls.host(url)
            out[id].append({
                "source": source["name"], "source_repo": source["repo"],
                "identity_claim": claim, "entry_host": host,
                "classification": clazz,
                "media_origin_independent": False,
                "rights_or_exact_video_verified": False,
            })
    return out


def run(batch, cfg, probe=True):
    targets = {id: cfg["channels"][id] for id in cfg["batches"][batch]}
    target_results = collections.defaultdict(list)
    sources = []
    for src in cfg["references"]:
        try:
            res = hls.fetch(src["url"], MAX_SOURCE_BYTES, timeout=12)
            entries = source_rows(res["data"].decode("utf-8-sig", "replace"))
            matched = map_source(src, entries, targets)
            for id, rows in matched.items():
                target_results[id].extend(rows)
            sources.append({"name": src["name"], "source_repo": src["repo"],
                            "status": "read", "entries_parsed": len(entries),
                            "target_hits": sum(len(v) for v in matched.values())})
        except Exception as exc:
            sources.append({"name": src["name"], "source_repo": src["repo"], "status": "failed",
                            "error_type": type(exc).__name__})
    known_hosts, disabled_urls, families = hls.load_known_paths()
    probes = []
    for item in cfg["probes"]:
        if item["channel"] not in targets:
            continue
        url = item["url"]
        outcome = (hls.probe_manifest(url) if probe and url not in disabled_urls
                   else {"stage": "not-probed-or-disabled"})
        probes.append({
            "channel": item["channel"], "entry_host": hls.host(url),
            "source_repo": item["source"], "family": item["family"],
            "known_config_seed_host": hls.host(url) in known_hosts,
            "manifest_probe": outcome,
            "full_linear_identity_verified": False, "authorized_media_origin_verified": False,
            "ffmpeg_decoded_verified": False, "production_eligible": False,
        })
    channels = []
    for id in cfg["batches"][batch]:
        rows = target_results[id]
        categories = collections.Counter(x["classification"] for x in rows)
        channels.append({
            "tvg_id": id, "github_claims": len(rows), "classes": dict(categories),
            "candidate_hosts": sorted({x["entry_host"] for x in rows}),
            "evidence": rows,
            "direct_original_media_verified": False,
            "current_state": "github-claims-only-no-verified-direct-origin" if rows else "no-match-in-source-set",
        })
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "batch": batch, "targets": cfg["batches"][batch], "sources": sources,
        "channels": channels, "preflight": probes,
        "summary": {
            "channels": len(channels), "source_claims": sum(row["github_claims"] for row in channels),
            "distinct_entry_hosts": sorted({h for row in channels for h in row["candidate_hosts"] if h != "[excluded]"}),
            "qualified_original_origins": 0, "verified_decoded_linear_feeds": 0,
            "streams_promoted": 0,
        },
        "rule": "GitHub labels and successful research jobs are not original media feeds. Never publish HLS until lawful original provenance, full-linear schedule/identity and decoder stability are verified.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", choices="ABCD", required=True)
    parser.add_argument("--out", default="research-results/github-active-families")
    args = parser.parse_args()
    cfg = load_registry()
    report = run(args.batch, cfg)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"batch-{args.batch}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "batch": args.batch, "sources": report["sources"], "summary": report["summary"],
        "per_channel": [{"id": c["tvg_id"], "claims": c["github_claims"], "classes": c["classes"]}
                        for c in report["channels"]],
        "preflight": [{"channel": p["channel"], "entry_host": p["entry_host"],
                       "stage": p["manifest_probe"]["stage"],
                       "final_host": p["manifest_probe"].get("final_host", "")}
                      for p in report["preflight"]]
    }, indent=2))


if __name__ == "__main__":
    main()
