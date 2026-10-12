"""v0.8.0 read-only provider-host failure exposure and backup prioritization.

Consumes already produced builder diagnostics. A distinct DNS hostname is NOT
proof of different upstream ownership; a source-family label can describe an
index/aggregator, not the broadcaster or actual media origin.
"""
import json
import os
from collections import Counter, defaultdict
from pathlib import Path


SPORTS = ("espn", "foxsports", "sports", "mlb", "nfl", "nba", "nhl",
          "golf", "tennis", "bigten", "accn", "secnetwork")
PHILLY = ("WPVI.us", "WCAU.us", "KYW.us", "WTXF.us", "WHYY.us",
          "WPHL.us", "Fox.us@WTXFTV", "Telemundo.us@WCAU")


def count(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def normal_host(value):
    return str(value or "").strip().lower().rstrip(".")


def analyze(status, redundancy, reliability, hunt):
    """Generate advisory rankings without altering candidate or channel selection."""
    status = status if isinstance(status, dict) else {}
    redundancy = redundancy if isinstance(redundancy, dict) else {}
    reliability = reliability if isinstance(reliability, dict) else {}
    hunt = hunt if isinstance(hunt, dict) else {}

    channels = [
        row for row in redundancy.get("channels", [])
        if isinstance(row, dict) and str(row.get("tvg_id") or "")
    ]
    host_channels = defaultdict(set)
    host_families = defaultdict(set)
    channel_hosts = {}
    for row in channels:
        tvg_id = str(row["tvg_id"])
        hosts = sorted({normal_host(h) for h in (row.get("provider_hosts") or [])
                        if normal_host(h)})
        channel_hosts[tvg_id] = hosts
        for host in hosts:
            host_channels[host].add(tvg_id)
        # Only assign families to hosts from explicit per-stream pairs.
        # Aggregate provider_families on a multi-host channel is insufficient.
        for pair in row.get("host_family_pairs") or []:
            if not isinstance(pair, dict):
                continue
            host = normal_host(pair.get("host"))
            if host and host in hosts:
                host_families[host].add(str(pair.get("family") or "unknown"))

    historical_losses = Counter()
    co_losses = []
    seen_builds = set()
    for snapshot in reliability.get("history") or []:
        if not isinstance(snapshot, dict):
            continue
        build_id = str(snapshot.get("build_id") or "")
        if not build_id or build_id in seen_builds:
            continue
        seen_builds.add(build_id)
        lost = sorted(set(str(c) for c in snapshot.get("lost_ids") or [] if c))
        historical_losses.update(lost)
        if len(lost) > 1:
            co_losses.append({"build_id": build_id, "lost_ids": lost,
                              "attribution": "unknown; concurrent losses do not establish a shared cause"})

    sources = []
    for row in channels:
        tvg_id = str(row["tvg_id"])
        hosts = channel_hosts[tvg_id]
        stream_count = count(row.get("stream_count"))
        one_host = len(hosts) == 1
        same_host_mirror = stream_count > 1 and one_host
        # A channel with no stream, or multiple host alternatives, has a different investigation path.
        if stream_count == 1:
            exposure = "single_stream"
        elif same_host_mirror:
            exposure = "same_host_multi_stream"
        elif len(hosts) > 1:
            exposure = "multi_host_independence_unverified"
        else:
            exposure = "missing_or_unknown_host"
        largest_shared_host = max((len(host_channels[h]) for h in hosts), default=0)
        recent_losses = historical_losses[tvg_id]
        locally_overridden = count(row.get("locally_verified_count"))
        normal_qa = count(row.get("normal_qa_stream_count"))
        sports = any(word in tvg_id.lower() for word in SPORTS)
        philly = tvg_id in PHILLY or bool(row.get("philly"))
        vulnerable = len(hosts) < 2 or stream_count < 2
        risk = (
            (50 if stream_count == 1 else 35 if same_host_mirror else 10 if len(hosts) > 1 else 45)
            + min(50, max(0, largest_shared_host - 1) * 2)
            + min(45, recent_losses * 15)
            + (18 if locally_overridden else 0)
            + (14 if sports else 0)
            + (14 if philly else 0)
            + (8 if normal_qa == 0 else 0)
        )
        sources.append({
            "tvg_id": tvg_id,
            "name": row.get("name"),
            "risk_score": risk,
            "exposure": exposure,
            "priority": "urgent" if risk >= 110 else "high" if risk >= 80 else "normal",
            "stream_count": stream_count,
            "provider_hosts": hosts,
            "source_families": sorted(set(map(str, row.get("provider_families") or []))),
            "host_blast_radius_channels": largest_shared_host,
            "locally_verified_streams": locally_overridden,
            "normal_qa_streams": normal_qa,
            "recent_loss_events": recent_losses,
            "sports": sports,
            "philadelphia": philly,
            "backup_search_needed": vulnerable,
            "suggested_action": (
                "Find an authorized, exact-ID upstream on a VERIFIED different origin; keep the present working source"
                if vulnerable else
                "Verify alternate host ownership/origin and failure independence; do not assume hostnames imply redundancy"
            ),
        })
    sources.sort(key=lambda x: (-x["risk_score"], x["tvg_id"]))
    vulnerable = [row for row in sources if row["backup_search_needed"]]

    hosts = []
    for host, dependent_ids in host_channels.items():
        unprotected = sorted(tvg_id for tvg_id in dependent_ids
                             if len(channel_hosts[tvg_id]) <= 1)
        host_row = {
            "host": host,
            "published_channels_exposed": len(dependent_ids),
            "channels_without_distinct_host_alternative": len(unprotected),
            "no_alternative_tvg_ids": unprotected,
            "all_exposed_tvg_ids": sorted(dependent_ids),
            "explicit_source_families": sorted(host_families[host]),
            "multiple_family_labels_same_host": len(host_families[host]) > 1,
            "verified_distinct_upstream_ownership": False,
        }
        hosts.append(host_row)
    hosts.sort(key=lambda x: (-x["channels_without_distinct_host_alternative"],
                               -x["published_channels_exposed"], x["host"]))

    mirrors = [row for row in sources if row["exposure"] == "same_host_multi_stream"]
    multi_host = [row for row in sources
                  if row["exposure"] == "multi_host_independence_unverified"]
    cross_family = [h for h in hosts if h["multiple_family_labels_same_host"]]
    return {
        "version": 1,
        "milestone": "v0.8.0",
        "build_id": str(status.get("build_id") or ""),
        "built_at": status.get("built_at"),
        "advisory_only": True,
        "no_source_publication_or_ranking_change": True,
        "source_family_is_not_a_provider_identity": True,
        "distinct_hostname_does_not_prove_independence": True,
        "summary": {
            "published_channels_analyzed": len(sources),
            "single_stream_channels": sum(x["exposure"] == "single_stream" for x in sources),
            "same_host_multi_stream_channels": len(mirrors),
            "multi_host_channels_unverified_independence": len(multi_host),
            "single_or_same_host_backup_targets": len(vulnerable),
            "distinct_media_hosts_observed": len(host_channels),
            "hosts_with_multiple_source_family_labels": len(cross_family),
            "simultaneous_loss_events": len(co_losses),
        },
        "top_10_backup_targets": vulnerable[:10],
        "all_backup_targets": vulnerable,
        "top_10_host_failure_risks": hosts[:10],
        "all_host_failure_risks": hosts,
        "same_host_mirror_channels": mirrors,
        "multi_host_independence_not_established": multi_host,
        "cross_family_same_host_evidence": cross_family,
        "coincident_channel_losses": co_losses,
        "existing_hunt_queue_top_10": (hunt.get("top_10") or [])[:10],
    }


def summary_markdown(report):
    s = report["summary"]
    lines = [
        "## v0.8.0: Independent Backup and Shared-Host Exposure (read-only)",
        "",
        f"- Channels analyzed: **{s['published_channels_analyzed']}**",
        f"- Single-stream: **{s['single_stream_channels']}**; multi-stream same-host mirrors: **{s['same_host_multi_stream_channels']}**",
        f"- Channels with multiple hostnames but **unverified provider independence**: **{s['multi_host_channels_unverified_independence']}**",
        f"- Hostnames appearing under more than one source-family label (per-stream evidence): **{s['hosts_with_multiple_source_family_labels']}**",
        "",
        "### Top backup priorities",
        "",
        "| Exact ID | Risk | Streams | Worst shared-host exposure |",
        "|---|---:|---:|---:|",
    ]
    for row in report["top_10_backup_targets"]:
        lines.append(f"| \`{row['tvg_id']}\` | {row['risk_score']} | {row['stream_count']} | {row['host_blast_radius_channels']} |")
    lines += ["", "### Largest host failure impact", "",
              "| Host | Affected published channels | No distinct-host alternative |",
              "|---|---:|---:|"]
    for row in report["top_10_host_failure_risks"][:5]:
        lines.append(f"| \`{row['host']}\` | {row['published_channels_exposed']} | {row['channels_without_distinct_host_alternative']} |")
    lines += [
        "",
        "**Interpretation:** Different DNS hosts or source-family names do not prove independent origins.",
        "No sources have been promoted or removed by this analysis. Prefer authorized, exact-identity feeds.",
        "",
    ]
    return "\n".join(lines)


def main():
    directory = Path(os.environ.get("STREMIO_TV_SITE", "site"))
    def load(relative):
        try:
            data = json.loads((directory / relative).read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}
    result = analyze(
        load("status.json"),
        load("diagnostics/host-redundancy.json"),
        load("diagnostics/five-build-reliability.json"),
        load("diagnostics/resilience-hunt-queue.json"),
    )
    target = directory / "diagnostics" / "upstream-exposure.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = summary_markdown(result)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text)
    print(f"Analysis saved at {target}")


if __name__ == "__main__":
    main()
