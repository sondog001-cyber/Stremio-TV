#!/usr/bin/env python3
"""Block publishing degraded curated lineups while preserving build diagnostics.

This checks only build outputs; it never changes streams, QA decisions or
existing Pages deployments. Set the floor/pinned IDs in deployment_guard.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


def evaluate_deployment_guard(
    config: dict[str, Any],
    status: dict[str, Any],
    published: list[dict[str, Any]],
) -> list[str]:
    settings = config.get("deployment_guard") or {}
    if not settings.get("enabled", True):
        return []

    errors: list[str] = []
    floor = int(settings.get("minimum_channels", 65))
    count = int(status.get("channels") or 0)
    if count <= 0:
        errors.append("build published zero channels")
    previous = status.get("_previous_deployed_channels")
    if previous is not None:
        try:
            previous_count = int(previous)
            if previous_count > 0 and count * 10 <= previous_count * 7:
                errors.append(f"channel regression >=30%: {count} versus previously deployed {previous_count}")
        except (ValueError, TypeError):
            errors.append("invalid previous deployed channel count")
    if count < floor:
        errors.append(f"published channels {count} below established floor {floor}")
    if count != len(published):
        errors.append(
            f"status reports {count} channels but diagnostics list {len(published)}"
        )

    # Normalize feed-variant metadata only for a deployment *presence check*:
    # History.us@East and History.us represent the same requested linear feed.
    canonical = {
        str(channel.get("tvg_id") or "").partition("@")[0].lower()
        for channel in published
    }
    pinned = list(settings.get("required_channel_ids") or [])
    absent = sorted(
        cid for cid in pinned
        if str(cid).partition("@")[0].lower() not in canonical
    )
    if absent:
        errors.append("previously-published essential channels absent: " +
                      ", ".join(absent))
    return errors


def main() -> int:
    config = json.loads(Path("config.json").read_text(encoding="utf-8"))
    status = json.loads(Path("site/status.json").read_text(encoding="utf-8"))
    channels = json.loads(Path("site/diagnostics/channels.json").read_text(encoding="utf-8"))
    baseline = Path(".previous-deployed-status.json")
    history = {"status": "unavailable", "warning": "Previous deployed status could not be fetched; 30% comparison unavailable; absolute floor and required-channel checks remain active."}
    if baseline.exists():
        try:
            previous = json.loads(baseline.read_text(encoding="utf-8"))
            previous_count = int(previous["channels"])
            if previous_count <= 0:
                raise ValueError("invalid deployed channel count")
            status["_previous_deployed_channels"] = previous_count
            history = {"status": "available", "previous_channels": previous_count, "current_channels": status.get("channels"), "threshold_percent": 30}
        except (OSError, ValueError, KeyError, TypeError):
            history["warning"] = "Previous deployed status invalid; 30% comparison unavailable; absolute floor and required-channel checks remain active."
    if history["status"] == "unavailable":
        print("WARNING: " + history["warning"], file=sys.stderr)
    diagnostics = Path("site/diagnostics/deployment-baseline.json")
    diagnostics.parent.mkdir(parents=True, exist_ok=True)
    diagnostics.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    status["deployment_baseline"] = history
    Path("site/status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    errors = evaluate_deployment_guard(config, status, channels)
    settings = config.get("deployment_guard") or {}
    print(
        "Deployment guard: published=%d, minimum=%s, critical IDs=%d, failures=%d"
        % (
            status.get("channels", 0), settings.get("minimum_channels", 65),
            len(settings.get("required_channel_ids") or []), len(errors)
        )
    )
    for problem in errors:
        print("ERROR: blocking Pages update: " + problem, file=sys.stderr)
    if errors:
        print("Previous Pages deployment remains in place. Inspect uploadable diagnostics.",
              file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
