#!/usr/bin/env python3
"""Read-only repeated FFmpeg Nicktoons research, not a production source test.

Decode three 60-second windows separated by a bounded idle interval.
Match the published EPG ID only as metadata; on-screen identity stays unverified.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import time
from pathlib import Path
from research import bravo_nicktoons_decoder_research as decoder

TARGET = "Nicktoons.us"

def summarize(samples, epg_rows=None, channel_rows=None):
    epg = [x for x in (epg_rows or []) if str(x.get("tvg_id","")).split("@")[0] == TARGET]
    channels = [x for x in (channel_rows or []) if str(x.get("tvg_id","")).split("@")[0] == TARGET]
    passes = sum(bool(x.get("ffmpeg_decoded") and x.get("decoder_continuity_pass")
                     and (x.get("sampled_frames") or 0) >= 50
                     and not x.get("possible_short_loops")) for x in samples)
    return {
        "channel": TARGET, "test_windows":len(samples),"continuity_passes":passes,
        "sustained_continuity_across_all_windows":len(samples)>=3 and passes==len(samples),
        "individual_windows":[{
            "tested_at": x.get("tested_at"),"decoded":bool(x.get("ffmpeg_decoded")),
            "sampled_frames":x.get("sampled_frames",0),
            "unique_frame_hashes":x.get("distinct_frame_hashes",0),
            "short_loops":x.get("possible_short_loops",[]),
            "longest_freeze_seconds":x.get("longest_identical_frame_run_seconds"),
            "ffmpeg_return_code":x.get("ffmpeg_return_code"),
            "ffmpeg_error_types":x.get("ffmpeg_error_types",[])} for x in samples],
        "published_identity": [x.get("tvg_id") for x in channels],
        "epg_matches": [{"channel_tvg_id":x.get("tvg_id"),"epg_id":x.get("epg_id"),
                         "method":x.get("method")} for x in epg],
        "epg_mapping_exists":bool(epg),
        "on_screen_nicktoons_schedule_verified":False,
        "upstream_rights_verified":False,
        "broadcaster_owned_origin_verified":False,
        "local_test_or_production_promotion":False,
        "warning":"Matching EPG labels is not verification of actual video identity."
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--rounds",type=int,default=3)
    parser.add_argument("--pause-seconds",type=int,default=15)
    parser.add_argument("--epg-matches",type=Path)
    parser.add_argument("--channels",type=Path)
    parser.add_argument("--out",type=Path,default=Path("research-results/nicktoons-repeat.json"))
    args=parser.parse_args()
    if args.rounds!=3 or not 5<=args.pause_seconds<=45:
        parser.error("Use exactly three windows and a 5..45 second interval")
    samples=[]
    for n in range(args.rounds):
        samples.append(decoder.run(TARGET))
        print(json.dumps({"window":n+1,"decoded":samples[-1].get("ffmpeg_decoded",False),
                          "samples":samples[-1].get("sampled_frames",0)}))
        if n < args.rounds-1:
            time.sleep(args.pause_seconds)
    epg=json.loads(args.epg_matches.read_text()) if args.epg_matches and args.epg_matches.exists() else []
    channels=json.loads(args.channels.read_text()) if args.channels and args.channels.exists() else []
    result=summarize(samples,epg,channels)
    result["generated_at"]=dt.datetime.now(dt.timezone.utc).isoformat()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
