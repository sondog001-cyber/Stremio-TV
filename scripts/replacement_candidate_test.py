#!/usr/bin/env python3
import json, subprocess, time

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"

candidates = [
    {
        "channel":"Bravo",
        "label":"DaddyLive current nfs",
        "url":"https://nfsnew.newkso.ru/nfs/premium307/mono.m3u8",
        "headers":{"Referer":"https://jxoxkplay.xyz/","Origin":"https://jxoxkplay.xyz","User-Agent":UA},
    },
    {
        "channel":"Cinemax Classics",
        "label":"852851 fresh exact candidate",
        "url":"https://iptv.852851.xyz/ch/cd915261c835165cc34aaf4584f626bf/master.m3u8",
    },
    {
        "channel":"Nicktoons",
        "label":"IPTVMate USA exact 219",
        "url":"https://ch.iptvmate.net/e569afcef3dafc9dbb0b06c1252957ee.m3u8",
    },
    {
        "channel":"Nicktoons",
        "label":"IPTVMate USA HD 536",
        "url":"https://ch.iptvmate.net/153646206778dd318beef4b6a1469193.m3u8",
    },
    {
        "channel":"Nicktoons",
        "label":"IPTVMate USA HD 558",
        "url":"https://ch.iptvmate.net/ca7520e29310f9b0fd2a1f400b0ebbab.m3u8",
    },
    {
        "channel":"RFD-TV",
        "label":"VuStreams playlist form",
        "url":"https://rfdtv-jw.cdn.vustreams.com/live/7cba1a3b-318a-4097-8492-374478370b91/live.isml/playlist.m3u8",
    },
    {
        "channel":"RFD-TV",
        "label":"Public short redirect",
        "url":"https://da.gd/rfdfreetv",
    },
]
rows=[]
for item in candidates:
    started=time.time()
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-rw_timeout","10000000"]
    headers=item.get("headers") or {}
    if headers:
        if headers.get("User-Agent"):
            cmd += ["-user_agent",headers["User-Agent"]]
        header_lines="".join(f"{k}: {v}\\r\\n" for k,v in headers.items() if k.lower() != "user-agent")
        if header_lines:
            cmd += ["-headers",header_lines]
    cmd += [
        "-i",item["url"],"-t","12","-map","0:v:0",
        "-vf","fps=2,scale=160:-2","-an","-f","framemd5","-"
    ]
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=22)
        hashes=[]
        for line in p.stdout.splitlines():
            if not line or line.startswith("#") or "," not in line:
                continue
            parts=[x.strip() for x in line.split(",")]
            if parts:
                hashes.append(parts[-1])
        frames=len(hashes)
        repeat=False
        repeat_seconds=None
        for width in range(4,min(8,frames//2)+1):
            for start in range(0,frames-2*width+1):
                a=hashes[start:start+width]
                b=hashes[start+width:start+2*width]
                if len(set(a)) >= 3 and a==b:
                    repeat=True
                    repeat_seconds=round(width/2,1)
                    break
            if repeat:
                break
        rows.append({
            **{k:v for k,v in item.items() if k!="headers"},
            "frames":frames,
            "decoded_seconds":round(frames/2,1),
            "repeat_detected":repeat,
            "repeat_seconds":repeat_seconds,
            "exit":p.returncode,
            "elapsed":round(time.time()-started,2),
            "stderr":p.stderr[-700:],
            "passed":frames>=20 and not repeat,
        })
    except subprocess.TimeoutExpired:
        rows.append({
            **{k:v for k,v in item.items() if k!="headers"},
            "frames":0,"decoded_seconds":0,"repeat_detected":False,
            "exit":None,"elapsed":round(time.time()-started,2),
            "stderr":"timeout","passed":False
        })
with open("replacement-candidates.json","w") as f:
    json.dump(rows,f,indent=2)
print(json.dumps(rows,indent=2))
