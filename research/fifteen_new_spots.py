#!/usr/bin/env python3
"""Review new source projects without running their code or changing production."""
from __future__ import annotations

import argparse
import concurrent.futures
from collections import defaultdict
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build
from release_readiness import channel_key
from research.fresh_origin_discovery import valid_public_url


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def permitted(entry, config, now):
    """Reject credential paths, device/account identifiers and expired public tokens."""
    url = entry.get("url", "")
    try:
        p = urllib.parse.urlsplit(url)
        q = dict(urllib.parse.parse_qsl(p.query))
        parts = [x for x in p.path.split("/") if x]
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit() and parts[-1].split(".")[0].isdigit():
            return False
        if any(k.lower() in {"mac", "stb_mac", "serial", "serial_number", "sessionid"} for k in q):
            return False
        for k in ("e", "exp", "expires", "expiry"):
            value = str(q.get(k, ""))
            if value.isdigit() and len(value) in (10, 13):
                timestamp = int(value) / (1000 if len(value) == 13 else 1)
                if timestamp < now.timestamp() + 900:
                    return False
        if not valid_public_url(url) or not build._is_clean_github_media_url(url, allow_public_signed_urls=True):
            return False
        if build._coverage_local_test_rejection(entry, {401, 404, 410}, now):
            return False
        kept, _ = build.apply_safety_controls([entry], config)
        kept, _ = build.enforce_exact_identity(kept, config)
        kept, _ = build.apply_stream_quarantine(kept, config)
        return bool(kept)
    except (ValueError, TypeError):
        return False


def fetch_document(document):
    result = dict(document)
    try:
        request = urllib.request.Request(document["url"], headers={"User-Agent": build.USER_AGENT})
        with urllib.request.urlopen(request, timeout=18) as response:
            body = response.read(8_000_001)
        if len(body) > 8_000_000:
            raise ValueError("document exceeds limit")
        result.update(status="ok", bytes=len(body), observed_sha256=hashlib.sha256(body).hexdigest(),
                      captured_content_unchanged=hashlib.sha256(body).hexdigest() == document["sha256"])
        return result, body.decode("utf-8", errors="replace")
    except Exception as exc:
        result.update(status="failed", error_type=type(exc).__name__)
        return result, ""


def parse_document(document, text):
    if document["path"] == "catalog/tv/all.json":
        rows = []
        for meta in json.loads(text).get("metas", []):
            for stream in meta.get("streams", []):
                rows.append({"name": meta.get("name"), "name_raw": meta.get("name"),
                             "tvg_id": meta.get("tvgId") or "", "url": stream.get("url", ""),
                             "headers": ((stream.get("behaviorHints") or {}).get("proxyHeaders") or {}).get("request", {}),
                             "source": document["repo"], "family": "research-new-spot"})
        return rows
    return build.parse_m3u(text, {"name": document["repo"], "family": "research-new-spot"})


def inspect(documents, config, roster_ids, known, now):
    ids = {channel_key(x): x for x in roster_ids}
    aliases = config["curation"].get("canonical_id_aliases") or {}
    names = defaultdict(set)
    for tid, meta in config.get("channel_metadata", {}).items():
        if channel_key(tid) in ids:
            names[build._logical_channel_key(meta.get("name", ""))].add(ids[channel_key(tid)])
    for tid in roster_ids:
        names[build._logical_channel_key(tid)].add(tid)
    known_hashes = set(known["known_url_sha256"])
    known_hosts = set(known["provider_hosts"])
    spots, candidates = {}, {}
    for doc, text in documents:
        repo = doc["repo"]
        spot = spots.setdefault(repo, {"repo": repo, "documents": [], "playlist_records": 0,
                                      "exact_matches": 0, "name_hints": 0, "rejected": 0,
                                      "known_urls": 0, "new_urls": 0})
        spot["documents"].append(doc)
        if doc["status"] != "ok":
            continue
        try:
            entries = parse_document(doc, text)
        except (ValueError, TypeError):
            doc["parse_error"] = True
            continue
        spot["playlist_records"] += len(entries)
        for entry in entries:
            raw = entry.get("tvg_id") or ""
            if re.search(r"@(?:west|westhd|hdwest|west4k)$", raw, re.I):
                continue
            target, basis = ids.get(channel_key(aliases.get(raw, raw))), "exact-tvg-id"
            if not target and not raw:
                hint = names.get(build._logical_channel_key(entry.get("name", "")), set())
                if len(hint) == 1:
                    target, basis = next(iter(hint)), "name-only-unverified"
            if not target:
                continue
            spot["exact_matches" if basis == "exact-tvg-id" else "name_hints"] += 1
            entry = {**entry, "tvg_id": target, "source_tvg_id": raw}
            if not permitted(entry, config, now):
                spot["rejected"] += 1
                continue
            if digest(entry["url"]) in known_hashes:
                spot["known_urls"] += 1
                continue
            spot["new_urls"] += 1
            host = urllib.parse.urlsplit(entry["url"]).hostname
            marker = (target, entry["url"], json.dumps(entry.get("headers") or {}, sort_keys=True))
            # FAST services with a matching label are not recovered cable channels.
            fast = (target not in {"BloombergTV.us", "NewsmaxTV.us", "PBSKids.us", "WeatherChannel.us"}
                    and any(host.endswith(x) for x in ("pluto.tv", "tubi.video", "wurl.tv", "amagi.tv")))
            row = candidates.setdefault(marker, {"tvg_id": target, "url": entry["url"],
                                                 "headers": entry.get("headers") or {},
                                                 "provider_host": host, "new_provider_host": host not in known_hosts,
                                                 "identity_basis": basis, "known_fast_standin": fast,
                                                 "provenance": []})
            row["provenance"].append({"repo": repo, "document_url": doc["url"],
                                      "observed_sha256": doc["observed_sha256"]})
    eligible = [r for r in candidates.values() if r["identity_basis"] == "exact-tvg-id" and not r["known_fast_standin"]]
    return {"advisory_only": True, "spots": list(spots.values()), "eligible_candidates": eligible,
            "summary": {"projects": len(spots), "actual_channel_catalogs": sum(s["playlist_records"] > 0 for s in spots.values()),
                        "records_read": sum(s["playlist_records"] for s in spots.values()),
                        "novel_safe_candidate_combinations": len(candidates),
                        "name_only_candidates": sum(r["identity_basis"] == "name-only-unverified" for r in candidates.values()),
                        "fast_standins_not_probed": sum(r["known_fast_standin"] for r in candidates.values()),
                        "exact_non_fast_candidates": len(eligible), "promotions": 0}}


def probe_candidate(entry, settings):
    row = {**entry, "identity_verified": False, "production_approved": False}
    initial = build._probe_stream(entry, timeout=6, verify_segment=True)
    row.update(health=initial, burn_in=[], decoder={"status": "not-tested"})
    if initial.get("status") != "ok":
        return row
    samples = [initial]
    for _ in range(4):
        time.sleep(15)
        sample = build._probe_stream(entry, timeout=6, verify_segment=True)
        samples.append(sample)
        if sample.get("status") != "ok":
            break
    row["burn_in"] = samples
    row["burn_in_passed"] = len(samples) == 5 and all(s.get("status") == "ok" for s in samples)
    if row["burn_in_passed"]:
        row["live_window_advanced"] = bool(initial.get("hls_media_sequence") != samples[-1].get("hls_media_sequence")
                                           or initial.get("hls_tail_sha256") != samples[-1].get("hls_tail_sha256"))
        if valid_public_url(initial.get("final_url") or entry["url"]):
            row["decoder"] = build._validate_direct_media_survival(entry, settings)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("spot-results"))
    parser.add_argument("--probe-limit", type=int, default=24)
    args = parser.parse_args()
    config = json.loads((ROOT / "config.json").read_text())
    specs = json.loads((ROOT / "research/fifteen-new-spots-inputs.json").read_text())["documents"]
    known = json.loads((ROOT / "research/fifteen-new-spots-known.json").read_text())
    roster = json.loads((ROOT / "research/v0.9.0-original-lineup.json").read_text())["channel_ids"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        documents = list(pool.map(fetch_document, specs))
    report = inspect(documents, config, roster, known, dt.datetime.now(dt.timezone.utc))
    report.update(environment="GitHub runner" if os.environ.get("GITHUB_ACTIONS") else "local runtime",
                  known_inventory= {k: v for k, v in known.items() if k not in {"known_url_sha256", "provider_hosts"}})
    # Same-host probes serialize; a positive standalone result cannot approve a feed.
    locks = defaultdict(threading.Lock)
    def check(entry):
        with locks[entry["provider_host"]]:
            return probe_candidate(entry, config["stream_health"]["direct_media_survival"])
    selected = report["eligible_candidates"][:max(0, min(args.probe_limit, 24))]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        report["media_results"] = list(pool.map(check, selected))
    report["summary"]["media_probes"] = len(selected)
    report["summary"]["normal_decoder_passes"] = sum(r["decoder"].get("status") == "ok" for r in report["media_results"])
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "fifteen-new-spots.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
