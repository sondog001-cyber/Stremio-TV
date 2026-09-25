#!/usr/bin/env python3
import json, subprocess, time, concurrent.futures

candidates = [
    {"channel":"Discovery Channel","url":"https://s2.thetvapp.to/live/56/tracks-v1a1/mono.m3u8?token=WFU5PvgZWRbibaFG30IORgMYYkPQGy0rQFIErfaW"},
    {"channel":"FX Movie Channel","url":"https://s2.thetvapp.to/live/36/tracks-v1a1/mono.m3u8?token=WFU5PvgZWRbibaFG30IORgMYYkPQGy0rQFIErfaW"},
    {"channel":"FXX","url":"https://s2.thetvapp.to/live/34/tracks-v1a1/mono.m3u8?token=WFU5PvgZWRbibaFG30IORgMYYkPQGy0rQFIErfaW"},
    {"channel":"HGTV","url":"https://s2.thetvapp.to/live/104/tracks-v1a1/mono.m3u8?token=WFU5PvgZWRbibaFG30IORgMYYkPQGy0rQFIErfaW"},
    {"channel":"Investigation Discovery","url":"https://s2.thetvapp.to/live/106/tracks-v1a1/mono.m3u8?token=WFU5PvgZWRbibaFG30IORgMYYkPQGy0rQFIErfaW"},
    {"channel":"TLC","url":"https://s2.thetvapp.to/live/139/tracks-v1a1/mono.m3u8?token=WFU5PvgZWRbibaFG30IORgMYYkPQGy0rQFIErfaW"},
    {"channel":"TV Land","url":"https://s2.thetvapp.to/live/145/tracks-v1a1/mono.m3u8?token=WFU5PvgZWRbibaFG30IORgMYYkPQGy0rQFIErfaW"},
    {"channel":"Cinemax Classics UHD","url":"https://s2.thetvapp.to/live/6069/tracks-v1a1/mono.m3u8?token=WFU5PvgZWRbibaFG30IORgMYYkPQGy0rQFIErfaW"},
    {"channel":"Smithsonian UHD","url":"https://s2.thetvapp.to/live/6184/tracks-v1a1/mono.m3u8?token=WFU5PvgZWRbibaFG30IORgMYYkPQGy0rQFIErfaW"},
    {"channel":"Starz Comedy UHD","url":"https://s2.thetvapp.to/live/6189/tracks-v1a1/mono.m3u8?token=WFU5PvgZWRbibaFG30IORgMYYkPQGy0rQFIErfaW"},
    {"channel":"Sundance UHD","url":"https://s2.thetvapp.to/live/6203/tracks-v1a1/mono.m3u8?token=WFU5PvgZWRbibaFG30IORgMYYkPQGy0rQFIErfaW"}
]
HEADERS = "Referer: https://thetvapp.to/\\r\\nOrigin: https://thetvapp.to\\r\\n"
def check(item):
    started=time.time()
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-user_agent","Mozilla/5.0","-headers",HEADERS,"-rw_timeout","12000000","-i",item["url"],"-t","15","-map","0:v:0","-vf","fps=2,scale=160:-2","-an","-f","framemd5","-"]
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=32)
        frames=sum(1 for line in p.stdout.splitlines() if line and not line.startswith("#") and "," in line)
        return {**item,"frames":frames,"decoded_seconds":round(frames/2,1),"exit":p.returncode,"elapsed":round(time.time()-started,2),"stderr":p.stderr[-600:],"passed":frames>=24}
    except subprocess.TimeoutExpired:
        return {**item,"frames":0,"decoded_seconds":0,"exit":None,"elapsed":round(time.time()-started,2),"stderr":"timeout","passed":False}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    rows=list(ex.map(check,candidates))
with open("replacement-candidates.json","w") as f: json.dump(rows,f,indent=2)
print(json.dumps(rows,indent=2))
