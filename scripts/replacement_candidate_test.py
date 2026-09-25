#!/usr/bin/env python3
import base64, json, subprocess, time, urllib.parse

PROXY="https://playlist.freecdnllm.sbs/"
HEADERS={
    "Origin":"https://jxoxkplay.xyz",
    "Referer":"https://jxoxkplay.xyz/",
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
}
CANDIDATES=[
    ("HGTV.us","HGTV","https://zekonew.newkso.ru/zeko/premium382/mono.m3u8"),
    ("NBCSportsPhiladelphia.us","NBC Sports Philadelphia","https://zekonew.newkso.ru/zeko/premium777/mono.m3u8"),
    ("CBSSportsNetwork.us","CBS Sports Network","https://zekonew.newkso.ru/zeko/premium308/mono.m3u8"),
    ("TLC.us","TLC","https://windnew.newkso.ru/wind/premium337/mono.m3u8"),
]

def wrap(url):
    enc_url=base64.b64encode(urllib.parse.quote(url,safe="").encode()).decode()
    enc_headers=base64.b64encode(json.dumps(HEADERS,separators=(",",":")).encode()).decode()
    return PROXY+"?url="+urllib.parse.quote(enc_url,safe="")+"&headers="+urllib.parse.quote(enc_headers,safe="")

rows=[]
for target_id,name,upstream in CANDIDATES:
    url=wrap(upstream)
    started=time.time()
    cmd=[
        "ffmpeg","-hide_banner","-loglevel","error","-nostdin",
        "-rw_timeout","12000000","-i",url,
        "-t","12","-map","0:v:0","-vf","fps=2,scale=160:-2",
        "-an","-f","framemd5","-"
    ]
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=24)
        frames=sum(1 for line in p.stdout.splitlines() if line and not line.startswith("#") and "," in line)
        rows.append({
            "target_id":target_id,"name":name,"upstream":upstream,"proxy_url":url,
            "frames":frames,"decoded_seconds":round(frames/2,1),"exit":p.returncode,
            "elapsed":round(time.time()-started,2),"stderr":p.stderr[-800:],"passed":frames>=20
        })
    except subprocess.TimeoutExpired:
        rows.append({"target_id":target_id,"name":name,"upstream":upstream,"proxy_url":url,"frames":0,"decoded_seconds":0.0,"exit":None,"elapsed":round(time.time()-started,2),"stderr":"timeout","passed":False})
payload={"tested":len(rows),"passed":sum(1 for r in rows if r["passed"]),"rows":rows}
with open("replacement-candidates.json","w") as f: json.dump(payload,f,indent=2)
print(json.dumps(payload,indent=2))
