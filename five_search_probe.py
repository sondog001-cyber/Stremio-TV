#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
import json
import time
from pathlib import Path

import build

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "five-search-results"
CANDIDATES = json.loads((ROOT / "five-search-candidates.json").read_text(encoding="utf-8"))["candidates"]

def probe_one(entry):
    stream = {
        **entry,
        "headers": entry.get("headers") or {},
        "family": "five-search",
        "priority": 1,
    }
    return build._probe_stream(stream, timeout=8, verify_segment=True)

def stalled(first, second):
    if first.get("status") != "ok" or second.get("status") != "ok":
        return None
    if first.get("hls_is_live") and second.get("hls_is_live"):
        a=first.get("hls_tail_sha256"); b=second.get("hls_tail_sha256")
        sa=first.get("hls_media_sequence"); sb=second.get("hls_media_sequence")
        if a and b and a == b and (sa is None or sb is None or sa == sb):
            return "stalled-live-hls-window"
    a=first.get("media_sample_sha256"); b=second.get("media_sample_sha256")
    if a and b and a == b and int(first.get("media_sample_bytes") or 0) >= 32768 and int(second.get("media_sample_bytes") or 0) >= 32768:
        return "identical-direct-media-sample"
    return None

def run_batch():
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        return list(pool.map(probe_one, CANDIDATES))

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    first=run_batch()
    print(f"first pass ok={sum(x.get('status')=='ok' for x in first)}/{len(first)}")
    time.sleep(15)
    second=run_batch()

    rows=[]
    for entry,a,b in zip(CANDIDATES,first,second):
        continuity=stalled(a,b)
        passed=a.get("status")=="ok" and b.get("status")=="ok" and not continuity
        rows.append({
            **entry,
            "passed": passed,
            "continuity_failure": continuity,
            "probe_1": a,
            "probe_2": b,
        })
    summary={
        "candidates":len(rows),
        "passed":sum(r["passed"] for r in rows),
        "failed":sum(not r["passed"] for r in rows),
        "passing_by_channel":{},
    }
    for r in rows:
        if r["passed"]:
            summary["passing_by_channel"].setdefault(r["tvg_id"],0)
            summary["passing_by_channel"][r["tvg_id"]]+=1
    (OUT/"results.json").write_text(json.dumps(rows,indent=2)+"\n",encoding="utf-8")
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))
    for r in rows:
        print(("PASS" if r["passed"] else "FAIL"), r["tvg_id"], r["source"], r["url"], r["continuity_failure"] or r["probe_2"].get("detail"))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
