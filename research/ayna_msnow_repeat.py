#!/usr/bin/env python3
"""Read-only three-interval MS NOW AynaOTT anti-loop research (no promotion)."""
import argparse
import datetime as dt
import json
import pathlib
import time
from research import ayna_bravo_msnow_research as research
from research import fresh_origin_discovery as hls

def summarize(windows,stage):
    passing=[bool(x.get("passed") and x.get("frames",0)>=50
                  and not x.get("short_loops_detected")
                  and x.get("max_static_seconds",999)<10) for x in windows]
    return {
        "channel":"MSNOW.us","stage":stage,
        "windows_tested":len(windows),
        "windows_passed":sum(passing),
        "all_three_technical_windows_passed":len(windows)==3 and all(passing),
        "window_metrics":windows,
        "exact_msnow_us_east_linear_identity_verified":False,
        "local_test_eligible_after_identity_review":len(windows)==3 and all(passing),
        "production_promotion":False,
        "note":"3x60 FFmpeg continuity is technical only; user local program/identity still required.",
    }

def run(pause_seconds=15):
    url=research.SOURCES["MSNOW.us"]["url"]
    stage=hls.probe_manifest(url).get("stage")
    windows=[]
    if stage=="progressing-hls-readable-not-decoded":
        for i in range(3):
            windows.append(research.decode_direct(url))
            if i<2:
                time.sleep(pause_seconds)
    out=summarize(windows,stage)
    out["checked_at_utc"]=dt.datetime.now(dt.timezone.utc).isoformat()
    return out

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--pause-seconds",type=int,default=15)
    parser.add_argument("--output",type=pathlib.Path,default=pathlib.Path("research-results/ayna-hosts/msnow-3x60.json"))
    args=parser.parse_args()
    if not 5<=args.pause_seconds<=45:
        parser.error("Pause must be 5–45s")
    report=run(args.pause_seconds)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
