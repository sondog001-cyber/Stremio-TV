#!/usr/bin/env python3
import json, subprocess, time, concurrent.futures

candidates = [
    {"channel":"CBS Sports Network","url":"http://fl3.moveonjoy.com/CBS_SPORTS_NETWORK/index.m3u8"},
    {"channel":"HGTV relay","url":"http://50.7.161.82:8278/streams/d/HGTV/playlist.m3u8"},
    {"channel":"HGTV UbtvFans","url":"https://z88.ubtvfans.com/live/rx3/1538/ded5bfd722fc798d47ea4f2793c4b7bf/index.m3u8"},
    {"channel":"Investigation Discovery","url":"http://premium.tutvgratis.tv:8000/live/youtvplayer/app/154.m3u8"},
    {"channel":"NBC Sports Philadelphia","url":"https://iptv.852851.xyz/live/stream-9e7dfbe3-6d71-4e50-a397-05790d76f862/index.m3u8"},
    {"channel":"Starz Comedy","url":"https://z88.ubtvfans.com/live/rx3/1118/447a71029feb5c50e4638cff92627143/index.m3u8"},
]
def check(item):
    started=time.time()
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-rw_timeout","12000000","-i",item["url"],"-t","15","-map","0:v:0","-vf","fps=2,scale=160:-2","-an","-f","framemd5","-"]
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=32)
        frames=sum(1 for line in p.stdout.splitlines() if line and not line.startswith("#") and "," in line)
        return {**item,"frames":frames,"decoded_seconds":round(frames/2,1),"exit":p.returncode,"elapsed":round(time.time()-started,2),"stderr":p.stderr[-500:],"passed":frames>=24}
    except subprocess.TimeoutExpired:
        return {**item,"frames":0,"decoded_seconds":0,"exit":None,"elapsed":round(time.time()-started,2),"stderr":"timeout","passed":False}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
    rows=list(ex.map(check,candidates))
with open("replacement-candidates.json","w") as f: json.dump(rows,f,indent=2)
print(json.dumps(rows,indent=2))
