#!/usr/bin/env python3
import json, subprocess, time, concurrent.futures

candidates = [
    {"channel":"CBS Sports Network","url":"https://zekonew.newkso.ru/zeko/premium308/mono.m3u8"},
    {"channel":"Discovery Channel","url":"https://zekonew.newkso.ru/zeko/premium313/mono.m3u8"},
    {"channel":"FXX","url":"https://ddy6new.newkso.ru/ddy6/premium298/mono.m3u8"},
    {"channel":"Fox Sports 2","url":"https://zekonew.newkso.ru/zeko/premium758/mono.m3u8"},
    {"channel":"HGTV","url":"https://zekonew.newkso.ru/zeko/premium382/mono.m3u8"},
    {"channel":"Investigation Discovery","url":"https://windnew.newkso.ru/wind/premium324/mono.m3u8"},
    {"channel":"MLB Network","url":"https://windnew.newkso.ru/wind/premium399/mono.m3u8"},
    {"channel":"Magnolia Network","url":"https://ddy6new.newkso.ru/ddy6/premium299/mono.m3u8"},
    {"channel":"NBC Sports Philadelphia","url":"https://zekonew.newkso.ru/zeko/premium777/mono.m3u8"},
    {"channel":"OWN","url":"https://windnew.newkso.ru/wind/premium331/mono.m3u8"},
    {"channel":"Reelz","url":"https://zekonew.newkso.ru/zeko/premium293/mono.m3u8"},
    {"channel":"Smithsonian Channel","url":"https://dokko1new.newkso.ru/dokko1/premium603/mono.m3u8"},
    {"channel":"SundanceTV","url":"https://dokko1new.newkso.ru/dokko1/premium658/mono.m3u8"},
    {"channel":"TLC","url":"https://windnew.newkso.ru/wind/premium337/mono.m3u8"},
    {"channel":"Weather Channel","url":"https://zekonew.newkso.ru/zeko/premium394/mono.m3u8"},
    {"channel":"Travel Channel","url":"https://windnew.newkso.ru/wind/premium340/mono.m3u8"},
]
def check(item):
    started=time.time()
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-rw_timeout","10000000","-i",item["url"],"-t","12","-map","0:v:0","-vf","fps=2,scale=160:-2","-an","-f","framemd5","-"]
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=24)
        frames=sum(1 for line in p.stdout.splitlines() if line and not line.startswith("#") and "," in line)
        return {**item,"frames":frames,"decoded_seconds":round(frames/2,1),"exit":p.returncode,"elapsed":round(time.time()-started,2),"stderr":p.stderr[-400:],"passed":frames>=20}
    except subprocess.TimeoutExpired:
        return {**item,"frames":0,"decoded_seconds":0,"exit":None,"elapsed":round(time.time()-started,2),"stderr":"timeout","passed":False}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
    rows=list(ex.map(check,candidates))
with open("replacement-candidates.json","w") as f: json.dump(rows,f,indent=2)
print(json.dumps(rows,indent=2))
