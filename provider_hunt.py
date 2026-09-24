#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

import build

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "provider-hunt-output"


def write_json(name: str, payload) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def host_of(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower()
    except Exception:
        return ""


def main() -> int:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    hunt = json.loads((ROOT / "provider-hunt-sources.json").read_text(encoding="utf-8"))
    providers = list(hunt.get("providers") or [])

    scan_config = copy.deepcopy(config)
    scan_config.setdefault("stream_stability", {})["enabled"] = False
    health = scan_config.setdefault("stream_health", {})
    health["enabled"] = True
    health["require_passed_only"] = True
    health["verify_segment_for_all_candidates"] = True
    health["double_probe"] = True
    health["second_probe_delay_seconds"] = 15
    health["timeout_seconds"] = 7
    health["max_workers"] = 30
    health["priority_recovery"] = {"enabled": False}

    allow_signed = bool(
        ((scan_config.get("discovery") or {}).get("public_search_policy") or {}).get(
            "allow_public_signed_urls", False
        )
    )

    rows = []
    candidates = []
    seen = set()

    for item in providers:
        expected_host = str(item.get("provider_host") or "").lower()
        target = str(item.get("target_evidence") or "")
        row = {
            "index": item.get("index"),
            "family": item.get("family"),
            "provider_host": expected_host,
            "target": target,
            "repository": item.get("repository"),
            "path": item.get("path"),
            "source_url": item.get("source_url"),
            "evidence_url": item.get("candidate_url"),
            "status": "pending",
            "records_scanned": 0,
            "target_matches": 0,
            "host_matches": 0,
            "credential_urls_rejected": 0,
            "candidates_retained": 0,
        }
        try:
            text, final_url = build._fetch_public_text(
                str(item.get("source_url") or ""),
                timeout=15,
                byte_limit=10_000_000,
            )
            source_info = {
                "name": f"Provider Hunt — {expected_host}",
                "family": item.get("family"),
                "priority": 60 + int(item.get("index") or 0),
                "philly": target in {"WPVI.us", "WCAU.us", "KYW.us", "WPHL.us", "WPSG.us"},
            }
            parsed = build.parse_m3u(text, source_info)
            matched = build._filter_entries_to_exact_targets(parsed, [target], scan_config)
            host_matched = [
                entry for entry in matched
                if host_of(str(entry.get("url") or "")) == expected_host
            ]
            row["status"] = "ok"
            row["final_url"] = final_url
            row["records_scanned"] = len(parsed)
            row["target_matches"] = len(matched)
            row["host_matches"] = len(host_matched)

            for entry in host_matched[:3]:
                url = str(entry.get("url") or "")
                if not build._is_clean_github_media_url(
                    url,
                    allow_public_signed_urls=allow_signed,
                ):
                    row["credential_urls_rejected"] += 1
                    continue
                key = (url, tuple(sorted((entry.get("headers") or {}).items())))
                if key in seen:
                    continue
                seen.add(key)
                entry["provider_hunt"] = True
                entry["source_type"] = "provider-hunt-public"
                candidates.append(entry)
                row["candidates_retained"] += 1
        except Exception as exc:
            row["status"] = "failed"
            row["error"] = str(exc)[:300]
        rows.append(row)
        print(
            f"[provider-hunt] {int(item.get('index') or 0):02d}/50 "
            f"{expected_host} -> {target}: {row['status']} "
            f"target={row['target_matches']} host={row['host_matches']} "
            f"retained={row['candidates_retained']}"
        )

    candidates, quarantined = build.apply_stream_quarantine(candidates, scan_config)
    print(f"[provider-hunt] probing {len(candidates)} clean exact candidates")
    healthy, health_rows, _ = build.probe_candidate_entries(
        candidates,
        scan_config,
        enabled=True,
    )

    passing_by_host = defaultdict(list)
    passing_by_target = defaultdict(list)
    for entry in healthy:
        provider = build.stream_provider_host(entry) or host_of(str(entry.get("url") or ""))
        item = {
            "name": entry.get("name"),
            "tvg_id": entry.get("tvg_id"),
            "source": entry.get("source"),
            "family": entry.get("family"),
            "provider_host": provider,
            "quality": build.quality_label(entry),
            "measured_quality": entry.get("measured_quality"),
            "effective_url": build.stream_effective_url(entry),
            "url": entry.get("url"),
            "headers": entry.get("headers") or {},
            "health": entry.get("health"),
        }
        passing_by_host[provider].append(item)
        passing_by_target[build.canonical_tvg_id(str(entry.get("tvg_id") or ""))].append(item)

    for row in rows:
        passed = passing_by_host.get(row["provider_host"], [])
        row["passing_candidates"] = len(passed)
        row["passing"] = passed

    target_summary = []
    for target in hunt.get("targets") or []:
        canonical = build.canonical_tvg_id(target)
        passed = passing_by_target.get(canonical, [])
        target_summary.append({
            "target": target,
            "canonical_target": canonical,
            "passing_candidates": len(passed),
            "independent_provider_count": len(
                {item.get("provider_host") for item in passed if item.get("provider_host")}
            ),
            "candidates": passed,
        })

    failure_counts = Counter()
    for row in health_rows:
        h = row.get("health") or {}
        failure_counts[(h.get("status", "unknown"), h.get("detail", ""))] += 1

    summary = {
        "provider_families_requested": len(providers),
        "provider_source_files_fetched": sum(1 for row in rows if row["status"] == "ok"),
        "provider_source_files_failed": sum(1 for row in rows if row["status"] != "ok"),
        "providers_with_exact_target_entry": sum(1 for row in rows if row["host_matches"] > 0),
        "providers_with_clean_candidate": sum(1 for row in rows if row["candidates_retained"] > 0),
        "clean_candidates_probed": len(candidates),
        "passing_candidates": len(healthy),
        "passing_provider_families": len(passing_by_host),
        "targets_with_passing_candidate": sum(1 for row in target_summary if row["passing_candidates"] > 0),
        "playback_quarantined": len(quarantined),
        "top_failure_reasons": [
            {"status": status, "detail": detail, "count": count}
            for (status, detail), count in failure_counts.most_common(20)
        ],
    }

    write_json("summary.json", summary)
    write_json("provider-results.json", rows)
    write_json("target-results.json", target_summary)
    write_json("health-results.json", health_rows)
    write_json("passing-candidates.json", healthy)
    write_json("quarantined.json", quarantined)

    print("[provider-hunt] COMPLETE")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
