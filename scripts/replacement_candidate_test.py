#!/usr/bin/env python3
import json, subprocess, time

candidates = [
    {"channel":"CBS Sports Network","label":"IPTVMate HD","url":"https://ch.iptvmate.net/c7d0bb4656a79af19f4de168162d60f1.m3u8"},
    {"channel":"Discovery Channel","label":"IPTVMate HD","url":"https://ch.iptvmate.net/122bed766f4d7cae35d61372a978a4d6.m3u8"},
    {"channel":"FXX","label":"IPTVMate FHD","url":"https://ch.iptvmate.net/c4db5de035d40f549ea5835804e6e1cd.m3u8"},
    {"channel":"Fox Sports 2","label":"IPTVMate HD","url":"https://ch.iptvmate.net/177b338cf73bfd3b64b181a5bc1517f5.m3u8"},
    {"channel":"HGTV","label":"IPTVMate HD","url":"https://ch.iptvmate.net/f66596df7e6d45466f45d5052ddc3992.m3u8"},
    {"channel":"MLB Network","label":"IPTVMate HD","url":"https://ch.iptvmate.net/0897c5e0c5251314b604d1d8aa500b62.m3u8"},
    {"channel":"TLC","label":"IPTVMate HD","url":"https://ch.iptvmate.net/be15df13575e823a25c074f497624a4f.m3u8"},
    {"channel":"The Weather Channel","label":"IPTVMate HD","url":"https://ch.iptvmate.net/13f8cc3131cfc1c7981b6899ca605342.m3u8"},
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
