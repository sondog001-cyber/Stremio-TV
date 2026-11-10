#!/usr/bin/env python3
"""Read-only Disney Channel stream and independent-fallback diagnostic.

Reads existing published-run artifacts; probes only explicitly configured public
candidate URLs with small HLS preflight. Never changes channel selection.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from research import fresh_origin_discovery as hls

TARGET = "DisneyChannel.us"

def canonical_id(value):
    return str(value or "").split("@")[0]

def redact_url(value):
    # Host and nonreversible fingerprint identify duplicate URL without exposing credentials.
    return {"host": hls.host(value), "url_sha256_12": hashlib.sha256(value.encode()).hexdigest()[:12]}

def assess(rows, config, published=None):
    matched = [r for r in rows if canonical_id(r.get("tvg_id")) == TARGET]
    by_url = {}
    for row in matched:
        url = row.get("url") or ""
        if not url or not hls.valid_public_url(url):
            continue
        state = by_url.setdefault(url, {"sources": set(), "statuses": set(), "families": set()})
        state["sources"].add(str(row.get("source") or "unknown"))
        state["families"].add(str(row.get("family") or "unknown"))
        state["statuses"].add(str((row.get("health") or {}).get("status") or "unknown"))
    uniques = []
    for url, data in sorted(by_url.items()):
        uniques.append({**redact_url(url), "source_labels": sorted(data["sources"]),
                        "families": sorted(data["families"]), "health_statuses": sorted(data["statuses"]),
                        "is_genuine_independent_fallback": False})
    seeds = []
    for candidate in (config.get("discovery") or {}).get("seed_candidates", []):
        if canonical_id(candidate.get("tvg_id")) != TARGET:
            continue
        url = candidate.get("url") or ""
        allowed = hls.valid_public_url(url) and "encr" not in url.lower()
        seeds.append({"host": hls.host(url) if allowed else None,
                      "candidate_allowed_in_research": allowed,
                      "not_yet_verified_alternative": True,
                      "reason": "encrypted-path-suspected" if "encr" in url.lower() else
                                "eligible-for-limited-research-only" if allowed else "unsafe-source"})
    published_ids = {canonical_id(p.get("tvg_id")) for p in (published or [])}
    return {
        "tvg_id": TARGET, "matched_inventory_records": len(matched),
        "distinct_tested_playback_urls": len(by_url),
        "duplicate_source_labels": len(matched) - len(by_url),
        "source_lineage": uniques, "configured_unverified_fallback_seeds": seeds,
        "is_published": TARGET in published_ids if published is not None else None,
        "independent_passing_fallbacks": 0,
        "fallback_is_single_point_of_failure": len(by_url) <= 1,
        "production_config_changed": False,
        "warning": "Independent source cannot be inferred from different playlists or labels."
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--stream-health",type=Path,required=True)
    p.add_argument("--channels",type=Path)
    p.add_argument("--config",type=Path,default=Path("config.json"))
    p.add_argument("--out",type=Path,default=Path("research-results/disney-fallback-diagnostic.json"))
    p.add_argument("--probe",action="store_true",help="Research-only small HLS preflight of configured nonencrypted seed URLs")
    args=p.parse_args()
    config=json.loads(args.config.read_text())
    health=json.loads(args.stream_health.read_text())
    channels=json.loads(args.channels.read_text()) if args.channels and args.channels.exists() else None
    report=assess(health,config,channels)
    if args.probe:
        probes=[]
        seen=set()
        for source in (config.get("discovery") or {}).get("seed_candidates", []):
            url=source.get("url") or ""
            if canonical_id(source.get("tvg_id"))!=TARGET or url in seen:
                continue
            seen.add(url)
            if not hls.valid_public_url(url) or "encr" in url.lower():
                probes.append({**redact_url(url),"stage":"not-probed-encrypted-or-unsafe"})
                continue
            result=hls.probe_manifest(url)
            probes.append({**redact_url(url),"stage":result.get("stage"),
                           "http_status":result.get("http_status"),"hls_kind":result.get("hls_kind"),
                           "media_host":result.get("media_host"),
                           "origin_permission_or_identity_verified":False})
        report["seed_manifest_probes"]=probes
    report["generated_at"]=dt.datetime.now(dt.timezone.utc).isoformat()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
