#!/usr/bin/env python3
"""Generate a gitignored source overlay from authorized OTA/provider connectors."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


UTC = dt.timezone.utc
ATTR_RE = re.compile(r'([A-Za-z0-9_-]+)="([^"]*)"')


def _env(name: str, required: bool = True) -> str:
    value = os.getenv(name, "").strip() if name else ""
    if required and not value:
        raise ValueError(f"Required environment variable is not set: {name}")
    return value


def _request_text(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> str:
    request_headers = {"User-Agent": "StremioTV-PrivateConnector/1.0", "Accept-Encoding": "identity"}
    request_headers.update(headers or {})
    request = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(10_000_000).decode("utf-8", errors="replace")


def _parse_m3u(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    pending: dict[str, str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            info, _, name = line.partition(",")
            attrs = {key.lower(): value for key, value in ATTR_RE.findall(info)}
            pending = {"tvg_id": attrs.get("tvg-id", ""), "name": name.strip()}
        elif pending is not None and line and not line.startswith("#"):
            pending["url"] = line
            entries.append(pending)
            pending = None
    return entries


def _matches_channel(candidate: dict[str, str], channel: dict[str, Any]) -> bool:
    candidate_id = candidate.get("tvg_id", "").casefold()
    candidate_name = candidate.get("name", "").casefold()
    ids = [str(value).casefold() for value in channel.get("match_ids", [])]
    names = [str(value).casefold() for value in channel.get("name_contains", [])]
    return candidate_id in ids or any(name and name in candidate_name for name in names)


def _base_stream(channel: dict[str, Any], connector: dict[str, Any], url: str) -> dict[str, Any]:
    return {
        "tvg_id": channel["tvg_id"],
        "name": channel.get("name") or channel["tvg_id"],
        "url": url,
        "quality": channel.get("quality"),
        "source": connector.get("name") or "Private connector",
        "family": "private-connector",
        "priority": int(channel.get("priority", -30)),
        "philly": bool(channel.get("philly", False)),
        "group": channel.get("group", ""),
        "headers": {},
        "content_kind": channel.get("content_kind", "full-linear"),
    }


def resolve_hdhomerun(
    connector: dict[str, Any],
    fetch_text: Callable[..., str] = _request_text,
) -> list[dict[str, Any]]:
    base_url = _env(str(connector.get("base_url_env") or "")).rstrip("/")
    lineup = json.loads(fetch_text(f"{base_url}/lineup.json"))
    rows = lineup if isinstance(lineup, list) else []
    streams: list[dict[str, Any]] = []
    for channel in connector.get("channels") or []:
        guide_numbers = {str(value).casefold() for value in channel.get("guide_numbers", [])}
        names = [str(value).casefold() for value in channel.get("name_contains", [])]
        match = next((row for row in rows if isinstance(row, dict) and (
            str(row.get("GuideNumber") or "").casefold() in guide_numbers
            or any(name and name in str(row.get("GuideName") or "").casefold() for name in names)
        )), None)
        if match and match.get("URL"):
            streams.append(_base_stream(channel, connector, str(match["URL"])))
    return streams


def resolve_provider_m3u(
    connector: dict[str, Any],
    fetch_text: Callable[..., str] = _request_text,
) -> list[dict[str, Any]]:
    playlist_url = _env(str(connector.get("playlist_url_env") or ""))
    authorization = _env(str(connector.get("authorization_env") or ""), required=False)
    request_headers = {"Authorization": authorization} if authorization else {}
    playlist = _parse_m3u(fetch_text(playlist_url, headers=request_headers))
    streams: list[dict[str, Any]] = []
    for channel in connector.get("channels") or []:
        match = next((candidate for candidate in playlist if _matches_channel(candidate, channel)), None)
        if not match:
            continue
        stream = _base_stream(channel, connector, urllib.parse.urljoin(playlist_url, match["url"]))
        if authorization and connector.get("forward_authorization"):
            stream["headers"] = {"Authorization": authorization}
        streams.append(stream)
    return streams


def generate_overlay(
    config: dict[str, Any],
    fetch_text: Callable[..., str] = _request_text,
) -> dict[str, Any]:
    streams: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    for connector in config.get("connectors") or []:
        connector_type = connector.get("type")
        try:
            if connector_type == "hdhomerun":
                found = resolve_hdhomerun(connector, fetch_text)
            elif connector_type == "provider-m3u":
                found = resolve_provider_m3u(connector, fetch_text)
            else:
                raise ValueError(f"Unsupported connector type: {connector_type}")
            streams.extend(found)
            reports.append({"name": connector.get("name"), "type": connector_type, "status": "ok", "streams": len(found)})
        except Exception as exc:
            reports.append({"name": connector.get("name"), "type": connector_type, "status": "failed", "error": str(exc)})
    return {
        "version": 1,
        "generated_at": dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "streams": streams,
        "connectors": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("private_connectors.json"))
    parser.add_argument("--output", type=Path, default=Path("private_sources.generated.json"))
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    overlay = generate_overlay(config)
    args.output.write_text(json.dumps(overlay, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.output.chmod(0o600)
    print(f"Generated {len(overlay['streams'])} private streams from {len(overlay['connectors'])} connectors")
    return 0 if all(row["status"] == "ok" for row in overlay["connectors"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
