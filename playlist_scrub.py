#!/usr/bin/env python3
"""Read-only playlist change inventory and bounded media triage; never promotes feeds."""
from __future__ import annotations

import argparse
from collections import Counter
import concurrent.futures
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import re
import urllib.parse
import zipfile

import build
from release_readiness import GitHub, WORKFLOW, channel_key
from research.fresh_origin_discovery import valid_public_url

ROOT = Path(__file__).resolve().parent
ARTIFACT = "playlist-scrub"
STATE_FILE = "playlist-scrub-state.json"


def identity(entry, config, roster):
    """Use explicit ID aliases only; never turn a West or foreign feed into East."""
    value = str(entry.get("tvg_id") or "").strip()
    if not value or re.search(r"@(?:west|westhd|hdwest|west4k)$", value, re.I):
        return None
    aliases = (config.get("curation") or {}).get("canonical_id_aliases") or {}
    value = aliases.get(value, value)
    return roster.get(channel_key(value))


def fingerprint(channel, url, headers):
    data = [channel, url, sorted((str(k).lower(), str(v)) for k, v in headers.items())]
    return hashlib.sha256(json.dumps(data, separators=(",", ":")).encode()).hexdigest()


def safe_entry(entry, config, now):
    try:
        url = str(entry.get("url") or "")
        parts = urllib.parse.urlsplit(url)
        path = [p for p in parts.path.split("/") if p]
        query = {k.lower(): v for k, v in urllib.parse.parse_qsl(parts.query)}
        if any(k in query for k in ("mac", "stb_mac", "serial", "serial_number", "sessionid")):
            return False
        if len(path) == 3 and path[0].isdigit() and path[1].isdigit() and path[-1].split(".")[0].isdigit():
            return False
        for key in ("e", "exp", "expires", "expiry"):
            value = str(query.get(key, ""))
            if value.isdigit() and len(value) in (10, 13):
                expires = int(value) / (1000 if len(value) == 13 else 1)
                if expires < now.timestamp() + 900:
                    return False
        if not valid_public_url(url):
            return False
        if not build._is_clean_github_media_url(url, allow_public_signed_urls=True):
            return False
        if build._coverage_local_test_rejection(entry, {401, 404, 410}, now):
            return False
        kept, _ = build.apply_safety_controls([entry], config)
        kept, _ = build.enforce_exact_identity(kept, config)
        kept, _ = build.apply_stream_quarantine(kept, config)
        return bool(kept)
    except (ValueError, TypeError):
        return False


def configured_sources(config):
    discovery = config.get("discovery") or {}
    sources = [*(config.get("sources") or {}).get("playlists", []),
               *(discovery.get("targeted_source_families") or {}).get("sources", []),
               *(discovery.get("philly_local_sources") or {}).get("playlists", [])]
    unique = {}
    for source in sources:
        url = source.get("url", "")
        if url and source.get("format", "m3u") == "m3u":
            unique.setdefault(url, source)
    return list(unique.values())[:64]


def scan_source(source):
    # Do not pass the GitHub API bearer token to any playlist/media host.
    row = {"name": source.get("name"), "url": source["url"], "status": "failed"}
    try:
        text, final = build._fetch_public_text(source["url"], timeout=8, byte_limit=2_000_000)
        entries = build.parse_m3u(text, source)
        row.update(status="ok", final_url=final, records=len(entries))
        return row, entries
    except Exception as exc:
        row["error_type"] = type(exc).__name__
        return row, []


def load_previous(api, current_run, branch):
    """Latest trusted main-workflow artifact, including guarded deployment failures."""
    artifacts = api.get("actions/artifacts?name=playlist-scrub&per_page=30")["artifacts"]
    candidates = sorted(artifacts, key=lambda x: x.get("created_at", ""), reverse=True)
    for artifact in candidates[:8]:
        run = artifact.get("workflow_run") or {}
        if artifact.get("expired") or str(run.get("id")) == str(current_run):
            continue
        if run.get("head_branch") != branch:
            continue
        metadata = api.get(f"actions/runs/{run['id']}")
        if (metadata.get("event") not in {"schedule", "push", "workflow_dispatch"}
                or metadata.get("head_branch") != branch
                or str(metadata.get("path", "")).split("@")[0] != WORKFLOW):
            continue
        raw = api.get(f"actions/artifacts/{artifact['id']}/zip", binary=True)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            member = archive.getinfo(STATE_FILE)
            if member.file_size > 8_000_000:
                raise ValueError("scrub state exceeds limit")
            state = json.loads(archive.read(member))
        if (state.get("version") != 1 or str(state.get("run_id")) != str(run["id"])
                or state.get("repository") != api.repository):
            continue
        return state, {"status": "loaded", "artifact_id": artifact["id"], "run_id": run["id"]}
    return {}, {"status": "initial-inventory", "reason": "No retained trusted prior scrub artifact"}


def inventory(config, roster_ids, previous, baseline, source_results, now):
    roster = {channel_key(x): x for x in roster_ids}
    known = {(channel_key(r.get("tvg_id")), r.get("url")) for r in baseline}
    hosts = {urllib.parse.urlsplit(r.get("effective_url") or r.get("url") or "").hostname
             for r in baseline}
    old = previous.get("seen") or {}
    hosts.update(row.get("provider_host") for row in old.values())
    current = {}
    rejected = 0
    stamp = now.isoformat().replace("+00:00", "Z")
    for source, entries in source_results:
        for entry in entries:
            target = identity(entry, config, roster)
            if not target:
                continue
            # Apply channel kill-switch/quarantine to the mapped exact identity too.
            entry = {**entry, "source_tvg_id": entry.get("source_tvg_id") or entry.get("tvg_id"),
                     "tvg_id": target}
            if not safe_entry(entry, config, now):
                rejected += 1
                continue
            url = entry["url"]
            headers = entry.get("headers") or {}
            key = fingerprint(target, url, headers)
            if key in current:
                provenance = {"source": source.get("name"), "playlist_url": source["url"]}
                if provenance not in current[key]["provenance"]:
                    current[key]["provenance"].append(provenance)
                continue
            host = urllib.parse.urlsplit(url).hostname
            was_known = key in old or (channel_key(target), url) in known
            row = {"key": key, "tvg_id": target, "url": url, "headers": headers,
                   "provider_host": host, "family": entry.get("family"),
                   "first_seen": old.get(key, {}).get("first_seen", stamp), "last_seen": stamp,
                   "newness": ("known" if was_known else "new" if previous else "initial-inventory"),
                   "new_provider_host": bool(host and host not in hosts),
                   "identity_status": "playlist-ID only; programming/schedule unverified",
                   "provenance": [{"source": source.get("name"), "playlist_url": source["url"]}],
                   "needs_probe": (old[key].get("needs_probe", False) if key in old
                                   else (channel_key(target), url) not in known),
                   "probe": old.get(key, {}).get("probe")}
            current[key] = row
    # Missing URLs stay in history; failed/truncated source reads are not removals.
    seen = {**old, **current}
    seen = dict(sorted(seen.items(), key=lambda x: x[1].get("last_seen", ""), reverse=True)[:5000])
    rows = sorted(current.values(), key=lambda x: (x["tvg_id"], x["url"]))
    return rows, seen, rejected


def triage(rows, config, limit, published_ids):
    """Bounded research probes, not burn-in, promotion or release-qualified coverage."""
    queue = [r for r in rows if r.get("needs_probe") and not r.get("probe")]
    queue.sort(key=lambda r: (channel_key(r["tvg_id"]) in published_ids,
                              not r["new_provider_host"], r["first_seen"], r["key"]))
    tested = 0
    for row in queue[:max(0, min(limit, 3))]:
        entry = {"url": row["url"], "headers": row["headers"]}
        health = build._probe_stream(entry, timeout=6, verify_segment=True)
        decoder = (build._validate_direct_media_survival(
            entry, config["stream_health"]["direct_media_survival"])
            if health.get("status") == "ok" else {"status": "not-tested"})
        row["probe"] = {"tested_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                        "health": health, "decoder": decoder,
                        "production_approved": False, "burn_in_completed": False,
                        "needs": "programme identity, normal burn-in/stability, Primary and promotion QA"}
        row["needs_probe"] = False
        tested += 1
    return tested


def run(config, roster, previous, baseline, source_results, now, probe_limit=0, published_ids=()):
    rows, seen, rejected = inventory(config, roster, previous, baseline, source_results, now)
    tested = triage(rows, config, probe_limit, {channel_key(x) for x in published_ids})
    # State rows share current row objects so fresh probe evidence survives the next run.
    counts = Counter(r["newness"] for r in rows)
    summary = {"playlists": len(source_results),
               "playlist_errors": sum(s.get("status") != "ok" for s, _ in source_results),
               "safe_exact_candidates": len(rows), "new_candidates": counts["new"],
               "initial_inventory_candidates": counts["initial-inventory"],
               "new_provider_hosts": len({r["provider_host"] for r in rows if r["new_provider_host"]}),
               "unsafe_or_quarantined_rejected": rejected, "media_probes": tested,
               "promotions": 0}
    return {"version": 1, "advisory_only": True, "summary": summary,
            "sources": [s for s, _ in source_results], "candidates": rows}, seen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--baseline-dir", type=Path, default=Path(".scrub-baseline/diagnostics"))
    parser.add_argument("--previous", type=Path, help="Local prior state, for offline replay")
    parser.add_argument("--out", type=Path, default=Path("scrub-results"))
    parser.add_argument("--probe-limit", type=int, default=3)
    args = parser.parse_args()
    config = json.loads((ROOT / "config.json").read_text())
    roster = json.loads((ROOT / "research/v0.9.0-original-lineup.json").read_text())["channel_ids"]
    prior = {"status": "initial-inventory"}
    previous = {}
    if args.previous:
        previous = json.loads(args.previous.read_text())
        prior = {"status": "local-replay"}
    elif args.repository:
        try:
            previous, prior = load_previous(GitHub(args.repository), os.environ.get("GITHUB_RUN_ID"), args.branch)
        except Exception as exc:
            prior = {"status": "unavailable", "error_type": type(exc).__name__}
    def local_json(name):
        try:
            return json.loads((args.baseline_dir / name).read_text())
        except (OSError, ValueError):
            return []
    baseline = local_json("stream-health.json")
    channels = local_json("channels.json")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(scan_source, configured_sources(config)))
    report, seen = run(config, roster, previous, baseline, results, dt.datetime.now(dt.timezone.utc),
                       args.probe_limit, [r.get("tvg_id") for r in channels])
    report.update(previous_state=prior, current_build_baseline_available=bool(baseline))
    args.out.mkdir(parents=True, exist_ok=True)
    state = {"version": 1, "repository": args.repository, "run_id": os.environ.get("GITHUB_RUN_ID"),
             "seen": seen}
    (args.out / STATE_FILE).write_text(json.dumps(state, separators=(",", ":")))
    (args.out / "playlist-scrub.json").write_text(json.dumps(report, indent=2))
    lines = ["## Playlist scrub (advisory)", "", f"Prior inventory: {prior['status']}.", "",
             *[f"- {k.replace('_', ' ')}: **{v}**" for k, v in report["summary"].items()], "",
             "Different hosts do not establish independent origins. Probe success is not promotion.",
             "Full URLs, source provenance and probe evidence are in the playlist-scrub artifact."]
    summary = "\n".join(lines) + "\n"
    (args.out / "playlist-scrub.md").write_text(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
            stream.write(summary)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
