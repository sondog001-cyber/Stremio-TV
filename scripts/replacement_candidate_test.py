#!/usr/bin/env python3
import base64
import json
import subprocess
import time
import urllib.parse

ORIGIN = "https://epicplayplay.cfd"
REFERER = "https://epicplayplay.cfd/"

channels = [
    ("Bravo", "nfs", 307),
    ("CBS Sports Network", "zeko", 308),
    ("Discovery Channel", "zeko", 313),
    ("FXX", "ddy6", 298),
    ("Fox Sports 2", "zeko", 758),
    ("HGTV", "zeko", 382),
    ("Investigation Discovery", "wind", 324),
    ("MLB Network", "wind", 399),
    ("NBC Sports Philadelphia", "zeko", 777),
    ("Nicktoons", "dokko1", 649),
    ("OWN", "wind", 331),
    ("Reelz", "zeko", 293),
    ("Smithsonian Channel", "dokko1", 603),
    ("SundanceTV", "dokko1", 658),
    ("TLC", "wind", 337),
    ("Weather Channel", "zeko", 394),
    ("Travel Channel", "wind", 340),
    ("FX Movie Channel", "zeko", 381),
    ("Magnolia Network", "ddy6", 299),
]

def b64(text):
    return base64.b64encode(text.encode()).decode()

def proxy_url(provider, channel_id):
    inner_data = b64(f"Origin={ORIGIN}")
    inner = f"https://chevy.soyspace.cyou/proxy/{provider}/premium{channel_id}/mono.m3u8&data={inner_data}"
    outer_url = b64(urllib.parse.quote(inner, safe=""))
    headers = b64(json.dumps({"Referer": REFERER}, separators=(",", ":")))
    return f"https://playlist.freecdnllm.sbs/?url={outer_url}&headers={headers}"

rows=[]
for name, provider, channel_id in channels:
    item={
        "channel":name,
        "label":"Metroid current Daddy proxy",
        "channel_id":channel_id,
        "provider":provider,
        "url":proxy_url(provider, channel_id),
    }
    started=time.time()
    cmd=[
        "ffmpeg","-hide_banner","-loglevel","error","-nostdin",
        "-rw_timeout","10000000","-i",item["url"],
        "-t","12","-map","0:v:0","-vf","fps=2,scale=160:-2",
        "-an","-f","framemd5","-"
    ]
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=24)
        hashes=[]
        for line in p.stdout.splitlines():
            if not line or line.startswith("#") or "," not in line:
                continue
            hashes.append(line.split(",")[-1].strip())
        frames=len(hashes)
        repeat=False
        repeat_seconds=None
        for width in range(4,min(8,frames//2)+1):
            for start in range(0,frames-2*width+1):
                clip=hashes[start:start+width]
                if len(set(clip)) >= 3 and clip == hashes[start+width:start+2*width]:
                    repeat=True
                    repeat_seconds=round(width/2,1)
                    break
            if repeat:
                break
        row={
            **item,
            "frames":frames,
            "decoded_seconds":round(frames/2,1),
            "repeat_detected":repeat,
            "repeat_seconds":repeat_seconds,
            "exit":p.returncode,
            "elapsed":round(time.time()-started,2),
            "stderr":p.stderr[-700:],
            "passed":frames>=20 and not repeat,
        }
    except subprocess.TimeoutExpired:
        row={**item,"frames":0,"decoded_seconds":0.0,"repeat_detected":False,"exit":None,"elapsed":round(time.time()-started,2),"stderr":"timeout","passed":False}
    rows.append(row)
    print(json.dumps(row,indent=2),flush=True)

with open("replacement-candidates.json","w") as f:
    json.dump(rows,f,indent=2)
print(json.dumps({
    "tested":len(rows),
    "passed":sum(1 for r in rows if r["passed"]),
    "passing_channels":[r["channel"] for r in rows if r["passed"]],
},indent=2))
