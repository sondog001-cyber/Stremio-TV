#!/usr/bin/env python3
import json, subprocess, time

candidates = [
    {"channel":"Starz Comedy","label":"arquerido NEX","url":"http://143.244.60.30/STARZ_COMEDY/index.m3u8"},
    {"channel":"Starz Comedy","label":"MoveOnJoy","url":"http://fl2.moveonjoy.com/STARZ_COMEDY/index.m3u8"},
    {"channel":"Starz Comedy","label":"historical mirror","url":"http://40.160.24.55/STARZ_COMEDY/index.m3u8"},
    {"channel":"Starz Comedy","label":"IPTVMate redirect","url":"https://ch.iptvmate.net/26051a4a8efad9bba4d60d9443832216.m3u8"},
    {"channel":"Cinemax Classics","label":"852851 proxy","url":"https://iptv.852851.xyz/ch/b87c7b595ab0e18621da9e14c865480c/master.m3u8"},
]
rows=[]
for item in candidates:
    started=time.time()
    cmd=[
        "ffmpeg","-hide_banner","-loglevel","error","-nostdin",
        "-rw_timeout","10000000","-i",item["url"],
        "-t","12","-map","0:v:0","-vf","fps=2,scale=160:-2",
        "-an","-f","framemd5","-"
    ]
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=22)
        frames=sum(1 for line in p.stdout.splitlines() if line and not line.startswith("#") and "," in line)
        rows.append({**item,"frames":frames,"decoded_seconds":round(frames/2,1),"exit":p.returncode,"elapsed":round(time.time()-started,2),"stderr":p.stderr[-500:],"passed":frames>=20})
    except subprocess.TimeoutExpired:
        rows.append({**item,"frames":0,"decoded_seconds":0,"exit":None,"elapsed":round(time.time()-started,2),"stderr":"timeout","passed":False})
with open("replacement-candidates.json","w") as f: json.dump(rows,f,indent=2)
print(json.dumps(rows,indent=2))
