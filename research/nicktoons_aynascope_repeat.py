#!/usr/bin/env python3
"""Three separated AynaScope Nicktoons decoder intervals; read-only.

This is distinct from the old 41.205.93.154 feed that exhibited 2/3s loops.
Positive FFmpeg results do NOT establish broadcaster identity or use rights.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import pathlib
import time

from research import disney_nicktoons_replacement_hunt as hunt
from research import fresh_origin_discovery as hls

ROOT=pathlib.Path(__file__).resolve().parents[1]

def read_candidate(registry):
    hunt.validate_registry(registry)
    found=[x for x in registry["candidates"] if x["tvg_id"]=="Nicktoons.us" and x["family"]=="aynascope"]
    if len(found)!=1 or hls.host(found[0]["entry_url"])!="tvsen7.aynascope.net":
        raise ValueError("Expected exactly one fixed vetted Nicktoons AynaScope lead")
    return found[0]

def assess(samples):
    flags=[bool(x.get("ffmpeg_decoded") and x.get("continuity_pass") and
                x.get("decoded_frames",0)>=50 and not x.get("possible_short_loops"))
           for x in samples]
    return {"sample_count":len(samples),"passed_count":sum(flags),
            "all_three_passed":len(samples)==3 and all(flags),
            "windows":[{"decoded":x.get("ffmpeg_decoded"),"decoded_frames":x.get("decoded_frames",0),
                        "unique_hashes":x.get("distinct_frame_hashes",0),
                        "possible_short_loops":x.get("possible_short_loops",[]),
                        "longest_freeze":x.get("longest_freeze"),
                        "decoder_pass":flag} for x,flag in zip(samples,flags)],
            "actual_us_nicktoons_linear_content_confirmed":False,
            "independent_original_broadcaster_cdn_confirmed":False,
            "direct_link_public_reuse_authorized":False,
            "approved_local_test_or_production":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--registry",type=pathlib.Path,default=hunt.CANDIDATES)
    p.add_argument("--output",type=pathlib.Path,default=pathlib.Path("research-results/replacement/nicktoons-ayna-repeat.json"))
    p.add_argument("--pause-seconds",type=int,default=15)
    args=p.parse_args()
    if not 5<=args.pause_seconds<=45:
        p.error("pause-seconds must be 5..45")
    data=json.loads(args.registry.read_text(encoding="utf-8"))
    candidate=read_candidate(data)
    url=candidate["entry_url"]
    preflight=hls.probe_manifest(url)
    samples=[]
    if preflight.get("stage")=="progressing-hls-readable-not-decoded":
        for i in range(3):
            samples.append(hunt.direct_decoder_test(url))
            if i<2: time.sleep(args.pause_seconds)
    report=assess(samples)
    report.update({"tvg_id":"Nicktoons.us","source_family":"aynascope",
                   "candidate_host":hls.host(url),
                   "preflight_stage":preflight.get("stage"),
                   "checked_at":dt.datetime.now(dt.timezone.utc).isoformat(),
                   "automatic_promotions":0,
                   "note":"No DRM or account-session bypass. Three clean samples are not enough to confirm content identity, provenance, or permissions."})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
