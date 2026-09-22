#!/usr/bin/env python3
"""Record or clear a time-limited Stremio client playback observation."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


UTC = dt.timezone.utc


def canonical(value: str) -> str:
    return "".join(ch.lower() for ch in value.strip() if ch.isalnum())


def update_config(
    config: dict[str, Any],
    channel_id: str,
    status: str,
    tested_at: str | None = None,
    note: str | None = None,
    ttl_hours: int | None = None,
) -> str:
    targets = (((config.get("discovery") or {}).get("philly_local_sources") or {}).get("target_ids") or [])
    matched = next((item for item in targets if canonical(item) == canonical(channel_id)), None)
    if not matched:
        raise ValueError(f"Unknown client-verification channel: {channel_id}")

    results = config.setdefault("stremio_client_results", {})
    if status == "clear":
        results.pop(matched, None)
        return matched

    when = tested_at or dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    try:
        parsed = dt.datetime.fromisoformat(when.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("tested-at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("tested-at must include a timezone")

    record: dict[str, Any] = {"status": status, "tested_at": when}
    if note:
        record["note"] = note
    if ttl_hours is not None:
        if ttl_hours < 1:
            raise ValueError("ttl-hours must be at least 1")
        record["ttl_hours"] = ttl_hours
    results[matched] = record
    return matched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("channel_id", help="Exact configured channel ID, for example WPVI.us")
    parser.add_argument("status", choices=("passed", "failed", "clear"))
    parser.add_argument("--tested-at", help="ISO-8601 time; defaults to now in UTC")
    parser.add_argument("--note")
    parser.add_argument("--ttl-hours", type=int)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    try:
        matched = update_config(
            config,
            args.channel_id,
            args.status,
            args.tested_at,
            args.note,
            args.ttl_hours,
        )
    except ValueError as exc:
        parser.error(str(exc))
    args.config.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    action = "Cleared" if args.status == "clear" else f"Recorded {args.status} for"
    print(f"{action} {matched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
