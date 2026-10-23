#!/usr/bin/env python3
"""Capture programme identity snapshots from currently viable missing-channel leads.

Research only. One JPG every ~38s; official EPG programme parity must be checked
manually before treating a feed as the named US channel.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import subprocess
import time

FEEDS=[
 ("DisneyChannel.us@East","disney-us-east","http://212.5.144.156/disney/index.m3u8"),
 ("NationalGeographic.us@East","natgeo-us-east","http://212.5.144.156:8080/natgeo/index.m3u8"),
 ("NationalGeographic.us@HDEast","natgeo-hd-east-alt","http://198.58.104.90:8989/natgeo/index.m3u8"),
 ("FoodNetwork.us","food-network-us","http://212.5.144.156:8080/foodnetwork/index.m3u8"),
 ("CookingChannel.us@SD","aynascope-cooking-unverified","https://tvsen7.aynascope.net/cooking/index.m3u8"),
]
BASE=Path("research/diagnostics/priority-identity-frames")
BASE.mkdir(parents=True,exist_ok=True)
def collect(row):
    identity,label,url=row
    results=[]
    for n in range(5):
        filename=BASE/f"{label}-{n}.jpg"
        started=time.monotonic()
        try:
            cmd=["ffmpeg","-hide_banner","-nostdin","-loglevel","error",
                "-rw_timeout","15000000","-i",url,"-map","0:v:0",
                "-frames:v","1","-vf","scale=960:-2","-y",str(filename)]
            p=subprocess.run(cmd,text=True,capture_output=True,timeout=30)
            exists=p.returncode==0 and filename.exists() and filename.stat().st_size>1000
            results.append({"step":n,"timestamp_utc":datetime.now(timezone.utc).isoformat(),
                "frame":str(filename) if exists else None,
                "sha256":hashlib.sha256(filename.read_bytes()).hexdigest() if exists else None,
                "exit":p.returncode,"error":p.stderr[-230:] if p.returncode else ""})
        except subprocess.TimeoutExpired:
            results.append({"step":n,"timestamp_utc":datetime.now(timezone.utc).isoformat(),
               "frame":None,"error":"FFmpeg capture timeout"})
        if n<4:time.sleep(max(0,38-(time.monotonic()-started)))
    print(identity,label,"captured",sum(bool(r["frame"]) for r in results),"/5",flush=True)
    return {"tvg_id":identity,"candidate":label,"frames":results,
        "identity_confirmed":False,"epg_parity_confirmed":False}
with ThreadPoolExecutor(max_workers=5) as pool:
    items=list(pool.map(collect,FEEDS))
report={"captured_at_utc":datetime.now(timezone.utc).isoformat(),
    "notes":"Captures are for reviewer comparison with 2026-10-14 US/Eastern network schedule. Media decode or network logo alone is insufficient.",
    "status":"IDENTITY_REVIEW_REQUIRED","promotable":False,"results":items}
(BASE/"report.json").write_text(json.dumps(report,indent=2)+"\n")
