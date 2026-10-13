#!/usr/bin/env python3
"""Research-only Github-source Philly HLS preflight. Does not publish streams."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from research import fresh_origin_discovery as checks

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES = ROOT / "research" / "philly-github-candidates-2026-10-12.json"
CHANNEL_IDS = ("KYW.us", "WPVI.us", "WCAU.us", "WPHL.us", "WPSG.us")


def validate_registry(data: dict) -> None:
    channels = data.get("channels", {})
    if set(channels) != set(CHANNEL_IDS):
        raise ValueError("Registry must explicitly cover exactly the five missing Philadelphia tvg-ids")
    seen = set()
    for tvg_id, info in channels.items():
        for candidate in info.get("candidates", []):
            url = candidate.get("url", "")
            if not checks.valid_public_url(url):
                raise ValueError("Unsafe, credentialed or private stream candidate URL")
            if not candidate.get("source_url", "").startswith("https://github.com/"):
                raise ValueError("Each candidate requires public GitHub source evidence")
            if not candidate.get("family") or not candidate.get("source"):
                raise ValueError("Every candidate needs family and source attribution")
            key = (tvg_id, url)
            if key in seen:
                raise ValueError("Duplicate identical channel+URL candidate")
            seen.add(key)


def analyze_station(tvg_id: str, data: dict, baseline: str = "") -> dict:
    if tvg_id not in CHANNEL_IDS:
        raise ValueError("Station must be one of five exact curated TVG IDs")
    validate_registry(data)
    known_hosts, disabled, known_families = checks.load_known_paths()
    baseline_read = checks.enrich_known_from_artifact(baseline, known_hosts, known_families) if baseline else False
    source = data["channels"][tvg_id]
    outcomes = []
    for c in source["candidates"]:
        url = c["url"]
        entry_host = checks.host(url)
        if url in disabled:
            outcome = {"stage": "rejected-by-existing-kill-switch"}
        else:
            outcome = checks.probe_manifest(url)
        outcomes.append({
            "tvg_id": tvg_id,
            "source": c["source"],
            "source_url": c["source_url"],
            "entry_url": url,
            "entry_host": entry_host,
            "family": c["family"],
            "host_in_known_inventory": entry_host in known_hosts,
            "nominal_family_is_not_proof_of_independence": True,
            "probe": outcome,
            "exact_full_linear_identity_verified": False,
            "broadcast_rights_verified": False,
            "decoded_video_verified": False,
            "production_eligible": False,
            "local_test_eligible": False
        })
    return {
        "tested_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "tvg_id": tvg_id,
        "station": source["station"],
        "known_host_inventory_loaded": baseline_read,
        "candidate_count": len(outcomes),
        "candidates": outcomes,
        "no_link_reason": source.get("no_link_reason"),
        "progressing_readable_count": sum(
            item["probe"]["stage"] == "progressing-hls-readable-not-decoded" for item in outcomes
        ),
        "decoded_or_approved_count": 0,
        "promotion_count": 0,
        "caution": "No relay/proxy/restream and no private credentials. Current scan is manifest + progression + 2KB segment only, NOT full video decode, station identity or permission."
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--station", choices=CHANNEL_IDS, required=True)
    ap.add_argument("--registry", type=Path, default=CANDIDATES)
    ap.add_argument("--baseline", default=".research-baseline/diagnostics/stream-health.json")
    ap.add_argument("--output", type=Path, default=Path("research-results/philly"))
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    data = json.loads(args.registry.read_text(encoding="utf-8"))
    results = analyze_station(args.station, data, args.baseline)
    destination = args.output / (args.station.replace(".", "-") + ".json")
    destination.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "target": results["tvg_id"], "probed": results["candidate_count"],
        "live_hls_progressing_readable": results["progressing_readable_count"],
        "production_promotions": results["promotion_count"],
        "by_family": [{"family": c["family"], "entry_host": c["entry_host"],
                       "known_host": c["host_in_known_inventory"],
                       "stage": c["probe"]["stage"]}
                      for c in results["candidates"]]
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
