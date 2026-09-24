#!/usr/bin/env python3
"""One-time 50-family public stream hunt.

This intentionally does not deploy anything. It scans research sources only,
keeps exact curated channel identities, rejects credential-bearing URLs, runs
the normal playback/continuity validator, and emits an artifact for review.
"""

from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict
from pathlib import Path

import build


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "mega-hunt-output"


def write_json(name: str, payload) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    hunt = json.loads((ROOT / "mega-hunt-sources.json").read_text(encoding="utf-8"))
    target_ids = list(hunt.get("targets") or [])
    sources = list(hunt.get("sources") or [])

    scan_config = copy.deepcopy(config)
    health = scan_config.setdefault("stream_health", {})
    health["enabled"] = True
    health["require_passed_only"] = True
    health["verify_segment_for_all_candidates"] = True
    health["double_probe"] = True
    health["second_probe_delay_seconds"] = 15
    health["timeout_seconds"] = min(8, int(health.get("timeout_seconds", 6)))
    health["max_workers"] = max(24, int(health.get("max_workers", 16)))

    allow_signed = bool(
        ((scan_config.get("discovery") or {}).get("public_search_policy") or {}).get(
            "allow_public_signed_urls", False
        )
    )

    candidates = []
    source_rows = []
    seen = set()

    for index, source in enumerate(sources, 1):
        row = {
            "index": index,
            "name": source.get("name"),
            "family": source.get("family"),
            "repository": source.get("repository"),
            "path": source.get("path"),
            "url": source.get("url"),
            "status": "pending",
            "records_scanned": 0,
            "matches_before_filter": 0,
            "credential_urls_rejected": 0,
            "duplicate_urls_rejected": 0,
            "candidates_retained": 0,
            "matched_ids": [],
        }
        try:
            text, final_url = build._fetch_public_text(
                str(source.get("url") or ""),
                timeout=15,
                byte_limit=10_000_000,
            )
            parsed = build.parse_m3u(text, dict(source))
            matched = build._filter_entries_to_exact_targets(parsed, target_ids, scan_config)
            row["status"] = "ok"
            row["final_url"] = final_url
            row["records_scanned"] = len(parsed)
            row["matches_before_filter"] = len(matched)

            per_target = defaultdict(int)
            retained = []
            source_cap = max(1, int(source.get("max_candidates_per_target", 2)))
            for entry in matched:
                url = str(entry.get("url") or "").strip()
                if not build._is_clean_github_media_url(
                    url,
                    allow_public_signed_urls=allow_signed,
                ):
                    row["credential_urls_rejected"] += 1
                    continue
                target = build.canonical_tvg_id(str(entry.get("tvg_id") or ""))
                if per_target[target] >= source_cap:
                    continue
                headers_key = tuple(sorted((entry.get("headers") or {}).items()))
                marker = (url, headers_key)
                if marker in seen:
                    row["duplicate_urls_rejected"] += 1
                    continue
                seen.add(marker)
                per_target[target] += 1
                entry["mega_hunt"] = True
                entry["source_type"] = "mega-hunt-public"
                retained.append(entry)
                candidates.append(entry)

            row["candidates_retained"] = len(retained)
            row["matched_ids"] = sorted(
                {build.canonical_tvg_id(str(entry.get("tvg_id") or "")) for entry in retained}
            )
        except Exception as exc:
            row["status"] = "failed"
            row["error"] = str(exc)[:300]
        source_rows.append(row)
        print(
            f"[mega-hunt] {index:02d}/{len(sources):02d} "
            f"{row.get('repository')}: {row['status']} "
            f"records={row['records_scanned']} candidates={row['candidates_retained']}"
        )

    # Respect permanent playback-defect quarantines before probing.
    candidates, quarantined = build.apply_stream_quarantine(candidates, scan_config)

    print(
        f"[mega-hunt] probing {len(candidates)} unique exact-ID candidates "
        f"from {len(sources)} source families"
    )
    healthy, health_rows, stability = build.probe_candidate_entries(
        candidates,
        scan_config,
        enabled=True,
    )

    provider_counts = Counter()
    target_passing = defaultdict(list)
    family_passing = defaultdict(list)
    for entry in healthy:
        provider = build.stream_provider_host(entry) or "unknown"
        provider_counts[provider] += 1
        target = build.canonical_tvg_id(str(entry.get("tvg_id") or ""))
        item = {
            "name": entry.get("name"),
            "tvg_id": entry.get("tvg_id"),
            "source": entry.get("source"),
            "family": entry.get("family"),
            "repository": next(
                (
                    source.get("repository")
                    for source in sources
                    if source.get("family") == entry.get("family")
                ),
                None,
            ),
            "quality": build.quality_label(entry),
            "measured_quality": entry.get("measured_quality"),
            "provider_host": provider,
            "effective_url": build.stream_effective_url(entry),
            "url": entry.get("url"),
            "headers": entry.get("headers") or {},
            "health": entry.get("health"),
        }
        target_passing[target].append(item)
        family_passing[str(entry.get("family") or "unknown")].append(item)

    source_by_family = {str(source.get("family")): source for source in sources}
    family_results = []
    for row in source_rows:
        family = str(row.get("family") or "")
        passed = family_passing.get(family, [])
        family_results.append({
            **row,
            "passing_candidates": len(passed),
            "passing_ids": sorted(
                {
                    build.canonical_tvg_id(str(item.get("tvg_id") or ""))
                    for item in passed
                }
            ),
            "provider_hosts": sorted(
                {str(item.get("provider_host") or "") for item in passed if item.get("provider_host")}
            ),
        })

    target_results = []
    wanted = {build.canonical_tvg_id(target): target for target in target_ids}
    for canonical, original in sorted(wanted.items()):
        passed = target_passing.get(canonical, [])
        target_results.append({
            "target": original,
            "canonical_target": canonical,
            "passing_candidates": len(passed),
            "independent_provider_count": len(
                {item.get("provider_host") for item in passed if item.get("provider_host")}
            ),
            "candidates": passed,
        })

    summary = {
        "source_families_requested": len(sources),
        "source_families_fetched": sum(1 for row in source_rows if row["status"] == "ok"),
        "source_families_failed_fetch": sum(1 for row in source_rows if row["status"] != "ok"),
        "families_with_exact_candidates": sum(1 for row in source_rows if row["candidates_retained"] > 0),
        "families_with_passing_candidates": sum(1 for row in family_results if row["passing_candidates"] > 0),
        "exact_candidates_before_probe": len(candidates),
        "playback_quarantined": len(quarantined),
        "passing_candidates": len(healthy),
        "distinct_passing_provider_hosts": len(provider_counts),
        "targets_requested": len(target_ids),
        "targets_with_passing_candidate": sum(1 for row in target_results if row["passing_candidates"] > 0),
        "provider_hosts": [
            {"host": host, "passing_candidates": count}
            for host, count in provider_counts.most_common()
        ],
    }

    write_json("summary.json", summary)
    write_json("source-results.json", family_results)
    write_json("target-results.json", target_results)
    write_json("health-results.json", health_rows)
    write_json("stream-stability.json", stability)
    write_json("quarantined.json", quarantined)
    write_json(
        "passing-candidates.json",
        [item for row in target_results for item in row["candidates"]],
    )

    print("[mega-hunt] COMPLETE")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
