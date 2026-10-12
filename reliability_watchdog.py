"""Read-only v0.8 reliability watchdog for a built Stremio TV site.

This report never changes stream selection, local overrides or the deployment gate.
It intentionally distinguishes runner-decoded playback from local-verified overrides.
"""
import json
import math
import os
from pathlib import Path


def _count(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def evaluate(status, reliability, redundancy, hunt):
    """Return actionable advisory diagnostics based only on published build data."""
    status = status if isinstance(status, dict) else {}
    reliability = reliability if isinstance(reliability, dict) else {}
    redundancy = redundancy if isinstance(redundancy, dict) else {}
    hunt = hunt if isinstance(hunt, dict) else {}

    published = _count(status.get("channels"))
    expected = _count((status.get("missing_source_buckets") or {}).get("expected_channels")) or 111
    qa = status.get("primary_playback_qa") or {}
    qa_tested = _count(qa.get("channels_tested"))
    qa_reported_passes = _count(qa.get("primary_passed"))
    rs = reliability.get("summary") or {}
    normal_passes = _count(rs.get("normal_decoder_passes_latest"))
    local_overrides = _count(rs.get("locally_overridden_playback_attempts_latest"))
    redundant = redundancy.get("summary") or {}
    independent_backups = _count(redundant.get("with_independent_backup"))
    single_streams = _count(redundant.get("single_stream"))
    epg_unmatched = _count(status.get("epg_unmatched_channels"))
    epg_unavailable = _count(status.get("epg_unavailable_channels"))

    history = reliability.get("history") or []
    history = [item for item in history if isinstance(item, dict)]
    current_build_id = str(status.get("build_id") or "")
    latest = next((item for item in reversed(history)
                   if current_build_id and item.get("build_id") == current_build_id), None)
    prior = None
    if latest is not None:
        position = next(i for i in range(len(history) - 1, -1, -1)
                        if history[i] is latest)
        prior = next((history[i] for i in range(position - 1, -1, -1)
                      if history[i].get("build_id") != current_build_id), None)

    previous_published = _count(prior.get("published")) if prior else None
    coverage_drop = max(0, previous_published - published) if previous_published is not None else None
    drop_tolerance = max(5, math.ceil(previous_published * 0.08)) if previous_published is not None else None
    previous_ids = set(str(x) for x in (prior.get("published_tvg_ids") or [])) if prior else set()
    current_ids = set(str(x) for x in (latest.get("published_tvg_ids") or [])) if latest else set()
    lost_ids = sorted(previous_ids - current_ids) if prior and latest else []

    top_hosts = (hunt.get("host_concentration") or [])[:5]
    top_hosts = [
        {"host": str(h.get("host") or ""), "published_channels": _count(h.get("published_channels"))}
        for h in top_hosts if isinstance(h, dict)
    ]
    highest_host = max((h["published_channels"] for h in top_hosts), default=0)

    alerts = []
    def warn(code, severity, message, next_action):
        alerts.append({
            "code": code,
            "severity": severity,
            "message": message,
            "next_action": next_action,
        })

    if coverage_drop is not None and coverage_drop > drop_tolerance:
        warn("coverage_regression", "high",
             f"Published coverage dropped {coverage_drop} channels from the previous build.",
             "Inspect changed channel IDs, cooldowns and provider-wide failures before accepting the regression.")
    if single_streams > published / 2:
        warn("single_stream_exposure", "medium",
             f"{single_streams} of {published} published channels have only one stream.",
             "Use the resilience hunt queue to find independent authorized upstream backups.")
    if local_overrides:
        warn("local_override_verification", "info",
             f"{local_overrides} playback QA attempts used local verification, not a normal runner decoder pass.",
             "Keep these streams available; seek user-side confirmation and independent upstream alternatives.")
    if published and highest_host >= max(15, math.ceil(published * 0.2)):
        warn("provider_host_concentration", "medium",
             f"The most represented upstream host appears on {highest_host} published channels.",
             "Validate true upstream independence and prioritize backup coverage on exposed channels.")
    if epg_unmatched:
        warn("epg_unmatched", "info",
             f"{epg_unmatched} published channels have unmatched guide data.",
             "Audit exact-identity guide matches without substituting unrelated schedules.")

    summary = {
        "published": published,
        "expected": expected,
        "missing": max(0, expected - published),
        "previous_published": previous_published,
        "coverage_drop": coverage_drop,
        "coverage_drop_alert_threshold": drop_tolerance,
        "lost_ids_since_prior_build": lost_ids,
        "final_qa_channels_tested": qa_tested,
        "final_qa_reported_passes": qa_reported_passes,
        "normal_decoder_passes": normal_passes,
        "local_override_attempts": local_overrides,
        "independent_host_backups_estimate": independent_backups,
        "single_stream_channels": single_streams,
        "highest_host_channel_exposure": highest_host,
        "epg_unmatched": epg_unmatched,
        "epg_unavailable": epg_unavailable,
        "five_build_history_complete": bool(rs.get("five_build_history_complete")),
    }
    return {
        "version": 1,
        "milestone": "v0.8.0",
        "build_id": current_build_id,
        "built_at": status.get("built_at"),
        "advisory_only": True,
        "does_not_change_qa_or_publication": True,
        "hostnames_are_not_proof_of_independent_providers": True,
        "summary": summary,
        "alerts": alerts,
        "top_exposed_hosts": top_hosts,
        "next_hunt_targets": (hunt.get("top_10") or [])[:10],
    }


def markdown_summary(report):
    s = report["summary"]
    lines = [
        "## v0.8.0 Reliability Watchdog (advisory)",
        "",
        "| Metric | Latest |",
        "|---|---:|",
        f"| Published channels | {s['published']} / {s['expected']} |",
        f"| Change from preceding observed build | {('N/A' if s['previous_published'] is None else str(s['published'] - s['previous_published']))} |",
        f"| Final QA reported passes | {s['final_qa_reported_passes']} / {s['final_qa_channels_tested']} |",
        f"| Normal decoder passes (attempts) | {s['normal_decoder_passes']} |",
        f"| Local verification overrides (attempts) | {s['local_override_attempts']} |",
        f"| Single-stream channels | {s['single_stream_channels']} |",
        f"| Channels with distinct-host alternatives (estimate) | {s['independent_host_backups_estimate']} |",
        f"| Highest host exposure (channels) | {s['highest_host_channel_exposure']} |",
        "",
        "Normal decoder passes and local overrides are deliberately counted separately.",
        "Distinct hosts do not establish independent upstream ownership or distribution rights.",
        "",
    ]
    if report["alerts"]:
        lines += ["### Review alerts", ""]
        for alert in report["alerts"]:
            lines.append(f"- **{alert['severity'].upper()}: {alert['code']}** — {alert['message']} {alert['next_action']}")
    else:
        lines.append("No configured reliability alerts in this build.")
    lines += ["", "This watchdog is read-only: it never removes streams or blocks deployment.", ""]
    return "\n".join(lines)


def main():
    site = Path(os.environ.get("STREMIO_TV_SITE", "site"))
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))
    report = evaluate(
        read(site / "status.json"),
        read(site / "diagnostics" / "five-build-reliability.json"),
        read(site / "diagnostics" / "host-redundancy.json"),
        read(site / "diagnostics" / "resilience-hunt-queue.json"),
    )
    destination = site / "diagnostics" / "v08-reliability-watchdog.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = markdown_summary(report)
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(summary)
    print(f"Read-only diagnostics: {destination}")


if __name__ == "__main__":
    main()
