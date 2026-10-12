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
