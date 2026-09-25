#!/usr/bin/env python3
import json, subprocess, time

candidates = [
    {"channel":"WPVI / 6ABC","label":"MoveOnJoy fl1","url":"https://fl1.moveonjoy.com/PA_PHILADELPHIA_ABC/index.m3u8"},
    {"channel":"KYW / CBS3","label":"MoveOnJoy fl1","url":"https://fl1.moveonjoy.com/PA_PHILADELPHIA_CBS/index.m3u8"},
    {"channel":"WCAU / NBC10","label":"MoveOnJoy fl1","url":"https://fl1.moveonjoy.com/PA_PHILADELPHIA_NBC/index.m3u8"},
    {"channel":"WPHL / PHL17","label":"LocalBTV tk","url":"https://v-pi.theus6tv.tk/hls/17.1/playlist.m3u8"},
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
