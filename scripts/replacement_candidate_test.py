#!/usr/bin/env python3
import json, subprocess, time, concurrent.futures

candidates = [
    {"channel":"Discovery","label":"NEX streamer1","url":"https://streamer1.nexgen.bz/DISCOVERY/index.m3u8"},
    {"channel":"FX","label":"NEX streamer1","url":"https://streamer1.nexgen.bz/FX/index.m3u8"},
    {"channel":"HGTV","label":"NEX streamer1","url":"https://streamer1.nexgen.bz/HGTV/index.m3u8"},
    {"channel":"TLC","label":"NEX streamer1","url":"https://streamer1.nexgen.bz/TLC/index.m3u8"},
    {"channel":"CBS Sports Network","label":"NEX 143 host","url":"http://143.244.60.30/CBS_SPORTS_NETWORK/index.m3u8"},
    {"channel":"CBS Sports Network","label":"TAZZ relay","url":"https://tazzdevil.arquerido.workers.dev/play/cbs-sport-network"},
    {"channel":"Fox Sports 2","label":"TAZZ relay","url":"https://tazzdevil.arquerido.workers.dev/play/fs2"},
    {"channel":"MLB Network","label":"TAZZ relay","url":"https://tazzdevil.arquerido.workers.dev/play/mlbnetwork"},
]
def check(item):
    started=time.time()
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-rw_timeout","10000000","-i",item["url"],"-t","12","-map","0:v:0","-vf","fps=2,scale=160:-2","-an","-f","framemd5","-"]
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=22)
        frames=sum(1 for line in p.stdout.splitlines() if line and not line.startswith("#") and "," in line)
        return {**item,"frames":frames,"decoded_seconds":round(frames/2,1),"exit":p.returncode,"elapsed":round(time.time()-started,2),"stderr":p.stderr[-500:],"passed":frames>=20}
    except subprocess.TimeoutExpired:
        return {**item,"frames":0,"decoded_seconds":0,"exit":None,"elapsed":round(time.time()-started,2),"stderr":"timeout","passed":False}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    rows=list(ex.map(check,candidates))
with open("replacement-candidates.json","w") as f: json.dump(rows,f,indent=2)
print(json.dumps(rows,indent=2))
