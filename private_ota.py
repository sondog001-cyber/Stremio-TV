#!/usr/bin/env python3
"""Build a LOCAL-ONLY Stremio source overlay for direct HDHomeRun OTA streams.

This adapter never downloads, proxies, decrypts, or restreams video.
It reads an HDHomeRun lineup and emits only direct HTTP MPEG-TS URLs.
Run on a machine on the same LAN as the tuner; never deploy output publicly.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import stat
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_MAPPING = ROOT / "private_ota.json"
DEFAULT_OVERLAY = ROOT / "private_sources.generated.json"
ALLOWED_IDS = frozenset({"KYW.us", "WCAU.us", "WPVI.us", "WPHL.us", "WPSG.us"})
VIRTUAL_CHANNEL = re.compile(r"^/auto/v([0-9]+(?:\.[0-9]+)?)$")
RFC1918 = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)


def _private_address(host: str) -> bool:
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False  # require numeric IPv4, not DNS, to avoid rebinding
    return isinstance(addr, ipaddress.IPv4Address) and any(addr in net for net in RFC1918)


def validate_base_url(base_url: str) -> str:
    parsed = urllib.parse.urlsplit(base_url.strip())
    if (
        parsed.scheme != "http"
        or not parsed.hostname
        or not _private_address(parsed.hostname)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 80)
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Tuner base URL must be http://<RFC1918-private-IPv4> with no credentials/path")
    return f"http://{parsed.hostname}"


def validate_stream_url(url: str, base_url: str, guide_number: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    base = urllib.parse.urlsplit(validate_base_url(base_url))
    match = VIRTUAL_CHANNEL.fullmatch(parsed.path)
    if (
        parsed.scheme != "http"
        or parsed.hostname != base.hostname
        or parsed.port != 5004
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not match
        or match.group(1) != guide_number
    ):
        raise ValueError("Lineup stream must be direct /auto/v<GuideNumber> on the same private tuner, port 5004")
    return url


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text).casefold())


def _secure_local_only() -> None:
    if os.getenv("GITHUB_ACTIONS", "").strip().lower() == "true":
        raise RuntimeError("The private OTA prototype must never run in GitHub Actions")


def compile_overlay(lineup: object, mapping: object, base_url: str) -> dict:
    """Pure local mapping step; no media requests. Unknown/ambiguous stations fail closed."""
    base_url = validate_base_url(base_url)
    if not isinstance(lineup, list):
        raise ValueError("HDHomeRun lineup.json must contain an array")
    if not isinstance(mapping, dict) or not isinstance(mapping.get("channels"), list):
        raise ValueError("OTA mapping must have a channels array")
    streams, status, seen = [], [], set()
    for target in mapping["channels"]:
        if not isinstance(target, dict):
            raise ValueError("Each mapping channel must be an object")
        tid = str(target.get("tvg_id", ""))
        if tid not in ALLOWED_IDS or tid in seen:
            raise ValueError("Only five distinct approved Philadelphia tvg-ids are permitted")
        seen.add(tid)
        numbers = {str(x).strip() for x in target.get("guide_numbers", []) if str(x).strip()}
        names = {_norm(x) for x in target.get("guide_names", []) if _norm(x)}
        if not numbers or not names:
            raise ValueError(f"{tid}: set at least one explicit guide number and exact lineup name")
        candidates = [
            row for row in lineup
            if isinstance(row, dict)
            and str(row.get("GuideNumber") or "").strip() in numbers
            and _norm(row.get("GuideName", "")) in names
        ]
        if len(candidates) != 1:
            status.append({"tvg_id": tid, "status": "ambiguous" if candidates else "not_found", "matches": len(candidates)})
            continue
        found = candidates[0]
        number = str(found["GuideNumber"]).strip()
        tags = {tag.strip().casefold() for tag in str(found.get("Tags", "")).split(",")}
        if "drm" in tags:
            status.append({"tvg_id": tid, "status": "drm_protected"})
            continue
        try:
            url = validate_stream_url(str(found.get("URL") or ""), base_url, number)
        except (ValueError, TypeError):
            status.append({"tvg_id": tid, "status": "invalid_or_external_stream_url"})
            continue
        streams.append({
            "tvg_id": tid,
            "name": str(target.get("name") or tid),
            "url": url,
            "quality": None,
            "source": "Local HDHomeRun OTA",
            "family": "private-connector",
            "priority": -30,
            "philly": True,
            "group": "Local",
            "headers": {},
            "content_kind": "full-linear",
        })
        status.append({"tvg_id": tid, "status": "mapped", "guide_number": number})
    return {
        "version": 1,
        "streams": streams,
        "connectors": [{"name": "Private Philadelphia OTA", "type": "hdhomerun", "status": "ok", "streams": len(streams)}],
        "ota_mapping_status": status,
    }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_lineup(base_url: str, timeout: float = 7.0) -> list:
    """Only GET direct private tuner lineup, never follow redirects off-LAN."""
    url = validate_base_url(base_url) + "/lineup.json"
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=timeout) as res:
        payload = res.read(250_001)
    if len(payload) > 250_000:
        raise ValueError("Tuner lineup exceeds size limit")
    result = json.loads(payload.decode("utf-8"))
    if not isinstance(result, list):
        raise ValueError("Tuner returned invalid lineup data")
    return result


def write_overlay(overlay: dict, output: Path) -> None:
    """Only permit the known gitignored output basename, with restrictive permissions."""
    _secure_local_only()
    if output.name != "private_sources.generated.json" or output.resolve().parent != ROOT.resolve():
        raise ValueError("OTA overlay may only be written to root/private_sources.generated.json")
    fd, name = tempfile.mkstemp(prefix=".private-ota-", dir=ROOT)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(json.dumps(overlay, indent=2) + "\n")
        os.chmod(name, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(name, output)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--lineup-file", type=Path, help="Offline fixture, no tuner call; never commit actual lineup")
    parser.add_argument("--write-overlay", action="store_true", help="Explicitly write gitignored private overlay")
    args = parser.parse_args()
    _secure_local_only()
    base_url = os.environ.get("STREMIO_TV_HDHR_BASE_URL", "")
    base_url = validate_base_url(base_url)
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    lineup = json.loads(args.lineup_file.read_text(encoding="utf-8")) if args.lineup_file else fetch_lineup(base_url)
    overlay = compile_overlay(lineup, mapping, base_url)
    # Intentionally omit IP addresses, video URLs, headers, and device identifiers.
    print(json.dumps({"mapped": len(overlay["streams"]), "status": overlay["ota_mapping_status"]}, indent=2))
    if args.write_overlay:
        write_overlay(overlay, DEFAULT_OVERLAY)
        print("Private overlay written to gitignored private_sources.generated.json (mode 0600)")
    return 0 if overlay["streams"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
