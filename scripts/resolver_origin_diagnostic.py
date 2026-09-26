#!/usr/bin/env python3
import json, re, subprocess, time, urllib.parse, urllib.request

BASE="http://127.0.0.1:3000"
TARGETS=[
    ("CBS Sports Network",308),
    ("HGTV",382),
    ("TLC",337),
    ("Discovery Channel",313),
]

def resolve(channel):
    url=f"{BASE}/api/resolve?"+urllib.parse.urlencode({"channel":channel,"server":"stream"})
    req=urllib.request.Request(url,headers={"User-Agent":"Stremio-TV resolver diagnostic","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=20) as r:
        return json.loads(r.read(1000000))

def parse_vlc(vlc):
    out={}
    m=re.search(r":http-user-agent='([^']+)'",vlc or "")
    if m: out["User-Agent"]=m.group(1)
    m=re.search(r":http-referrer='([^']+)'",vlc or "")
    if m: out["Referer"]=m.group(1)
    return out

def run_ffmpeg(url,headers,label):
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-rw_timeout","10000000"]
    ua=headers.get("User-Agent")
    if ua: cmd += ["-user_agent",ua]
    extra={k:v for k,v in headers.items() if k.lower()!="user-agent"}
    if extra:
        cmd += ["-headers","".join(f"{k}: {v}\\r\\n" for k,v in extra.items())]
    cmd += ["-i",url,"-t","12","-map","0:v:0","-vf","fps=2,scale=160:-2","-an","-f","framemd5","-"]
    started=time.time()
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=22)
        frames=0
        for line in p.stdout.splitlines():
            line=line.strip()
            if line and not line.startswith("#") and "," in line:
                frames+=1
        return {
            "label":label,
            "frames":frames,
            "decoded_seconds":round(frames/2,1),
            "passed":frames>=20,
            "exit":p.returncode,
            "elapsed":round(time.time()-started,2),
            "stderr":p.stderr[-700:],
        }
    except subprocess.TimeoutExpired:
        return {"label":label,"frames":0,"decoded_seconds":0.0,"passed":False,"exit":None,"elapsed":22,"stderr":"timeout"}

rows=[]
for name,channel in TARGETS:
    payload=resolve(channel)
    direct=str(payload.get("direct") or "")
    live=str(payload.get("live") or "")
    headers=parse_vlc(str(payload.get("vlc") or ""))
    origin_headers=dict(headers)
    ref=headers.get("Referer")
    if ref:
        parts=urllib.parse.urlsplit(ref)
        if parts.scheme and parts.netloc:
            origin_headers["Origin"]=f"{parts.scheme}://{parts.netloc}"
    tests=[
        run_ffmpeg(direct,headers,"direct-current"),
        run_ffmpeg(direct,origin_headers,"direct-plus-origin"),
        run_ffmpeg(live,{},"resolver-live"),
    ]
    row={
        "channel":name,
        "channel_id":channel,
        "direct":direct,
        "live":live,
        "headers_current":headers,
        "headers_with_origin":origin_headers,
        "tests":tests,
    }
    rows.append(row)
    print(name,flush=True)
    for t in tests:
        print(f"  {t['label']}: frames={t['frames']} decoded={t['decoded_seconds']}s passed={t['passed']} exit={t['exit']}",flush=True)
        if t["stderr"]:
            print("   ",t["stderr"].replace(direct,"<direct>").replace(live,"<live>")[-400:],flush=True)

with open("resolver-origin-diagnostic.json","w") as f:
    json.dump(rows,f,indent=2)
