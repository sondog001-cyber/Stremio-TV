#!/usr/bin/env python3
"""Fail build when a published stream lacks normal, successful decoder QA.

This script is intentionally independent of the deployment guard: *both* must
pass before an edited QA policy is eligible for production.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

def canon(value: str) -> str:
    return value.split("@", 1)[0].strip().casefold()

def main():
    config = read("config.json")
    sources = read("manual_sources.json")["streams"]
    published = read("site/diagnostics/channels.json")
    report = read("site/diagnostics/primary-playback-qa.json")
    status = read("site/status.json")
    health = read("site/diagnostics/stream-health.json")

    errors = []
    if not (config.get("stream_health") or {}).get("require_passed_only"):
        errors.append("require_passed_only is disabled")
    if not (config.get("stream_health") or {}).get("primary_playback_qa", {}).get("enabled"):
        errors.append("primary_playback_qa is disabled")
    if (config.get("local_test_catalog") or {}).get("enabled"):
        errors.append("Local Test catalog is enabled")
    local_flags = [x.get("tvg_id") for x in sources if x.get("local_verified_override")]
    if local_flags:
        errors.append("manual sources still contain local pass overrides: " + str(local_flags))
    if not report.get("enabled") or not published:
        errors.append("missing final playback QA report or empty published lineup")

    reports = {canon(row.get("tvg_id", "")): row for row in report.get("channels", [])}
    ok_health_urls = {
        str(h.get("url") or "")
        for h in health if (h.get("health") or {}).get("status") == "ok"
    }
    verified_streams = 0
    for channel in published:
        name = str(channel.get("tvg_id") or "")
        row = reports.get(canon(name))
        if not row:
            errors.append("missing channel QA: " + name)
            continue
        indices = row.get("passing_stream_indexes") or []
        attempts = row.get("attempts") or []
        rescued = row.get("rescued_stream")
        if rescued:
            approved = [rescue for rescue in row.get("rescue_attempts") or []
                        if rescue.get("status") == "ok" and (rescue.get("qa") or {}).get("passed") is True]
            if not approved:
                errors.append("unverified rescue published: " + name)
            else:
                verified_streams += 1
        else:
            if int(channel.get("stream_count") or 0) != len(indices):
                errors.append(
                    f"unverified/extra published streams in {name}: "
                    f"catalog={channel.get('stream_count')} decoded={len(indices)}"
                )
            for i in indices:
                attempt = attempts[i] if isinstance(i, int) and 0 <= i < len(attempts) else {}
                if attempt.get("status") != "ok" or (attempt.get("qa") or {}).get("passed") is not True:
                    errors.append(f"stream was not fully decoded: {name} stream index {i}")
                if attempt.get("url") not in ok_health_urls:
                    errors.append(f"stream lacks passing transport QA: {name} {attempt.get('url')}")
                if (attempt.get("qa") or {}).get("local_verified_override"):
                    errors.append(f"local QA override slipped through: {name}")
                verified_streams += 1
        if row.get("action") == "dropped-channel":
            errors.append("dropped channel listed as published: " + name)

    if status.get("channels") != len(published):
        errors.append("status/catalog count mismatch")
    if status.get("total_streams") != verified_streams:
        errors.append(
            f"stream count mismatch: status={status.get('total_streams')} "
            f"verified={verified_streams}"
        )
    print(
        f"Full QA audit: channels={len(published)}, total_streams={status.get('total_streams')}, "
        f"decoder_verified_streams={verified_streams}, failures={len(errors)}"
    )
    for error in errors:
        print("FAIL: " + error)
    raise SystemExit(1 if errors else 0)

if __name__ == "__main__":
    main()
