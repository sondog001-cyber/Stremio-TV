#!/usr/bin/env python3
import json, re, subprocess, time, urllib.parse, urllib.request

PLAYLIST="https://raw.githubusercontent.com/nightah/daddylive/main/daddylive-channels-kodi.m3u8"
TARGETS={
    "FXX.USA.-.Eastern.us":"FXX.us",
    "Fox.Sports.2.us":"FoxSports2.us",
    "HGTV.USA.-.Eastern.Feed.us":"HGTV.us",
    "SundanceTV.USA.-.East.us":"SundanceTV.us",
    "TLC.USA.-.Eastern.us":"TLC.us",
    "Magnolia.-.East.us":"MagnoliaNetwork.us",
    "Oprah.Winfrey.Network.USA.Eastern.us":"OWN.us",
    "ReelzChannel.us":"Reelz.us",
    "TheTravelChannel.us":"TravelChannel.us",
    "CBS.Sports.Network.USA.us":"CBSSportsNetwork.us",
    "Discovery.Channel.(US).-.Eastern.Feed.us":"DiscoveryChannel.us",
    "Investigation.Discovery.USA.-.Eastern.us":"InvestigationDiscovery.us",
    "MLB.Network.us":"MLBNetwork.us",
    "NBC.Sports.Philadelphia.HDTV.(NBCSPAHD).us":"NBCSportsPhiladelphia.us",
    "Smithsonian.Channel.USA.HD.us":"SmithsonianChannel.us",
    "The.Weather.Channel.us":"WeatherChannel.us",
    "FX.Movie.Channel.us":"FXMovieChannel.us",
}
UA="Nightah recovery test"

def decode_inline(raw):
    parts=raw.split("|")
    url=parts[0].strip()
    headers={}
    if len(parts)>1:
        for item in "|".join(parts[1:]).split("&"):
            if "=" not in item: continue
            k,v=item.split("=",1)
            k=k.strip(); v=urllib.parse.unquote(v.strip())
            if k.lower()=="origin": headers["Origin"]=v
            elif k.lower() in {"referer","referrer"}: headers["Referer"]=v
            elif k.lower()=="user-agent": headers["User-Agent"]=v
    return url,headers

req=urllib.request.Request(PLAYLIST,headers={"User-Agent":UA})
with urllib.request.urlopen(req,timeout=20) as r:
    lines=r.read(10_000_000).decode("utf-8","ignore").splitlines()

rows=[]
for i,line in enumerate(lines):
    if not line.startswith("#EXTINF"): continue
    m=re.search(r'tvg-id="([^"]+)"',line)
    if not m or m.group(1) not in TARGETS: continue
    source_id=m.group(1)
    url_line=""
    for nxt in lines[i+1:i+8]:
        nxt=nxt.strip()
        if nxt and not nxt.startswith("#"):
            url_line=nxt; break
    if not url_line: continue
    url,headers=decode_inline(url_line)
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-rw_timeout","10000000"]
    ua=headers.get("User-Agent")
    if ua: cmd += ["-user_agent",ua]
    extra={k:v for k,v in headers.items() if k.lower()!="user-agent"}
    if extra: cmd += ["-headers","".join(f"{k}: {v}\\r\\n" for k,v in extra.items())]
    cmd += ["-i",url,"-t","12","-map","0:v:0","-vf","fps=2,scale=160:-2","-an","-f","framemd5","-"]
    started=time.time()
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=22)
        frames=sum(1 for x in p.stdout.splitlines() if x.strip() and not x.startswith("#") and "," in x)
        row={
            "source_tvg_id":source_id,"tvg_id":TARGETS[source_id],"url":url,"headers":headers,
            "frames":frames,"decoded_seconds":round(frames/2,1),"passed":frames>=20,
            "exit":p.returncode,"elapsed":round(time.time()-started,2),"stderr":p.stderr[-600:]
        }
    except subprocess.TimeoutExpired:
        row={"source_tvg_id":source_id,"tvg_id":TARGETS[source_id],"url":url,"headers":headers,
             "frames":0,"decoded_seconds":0.0,"passed":False,"exit":None,"elapsed":22,"stderr":"timeout"}
    rows.append(row)
    print(f"{TARGETS[source_id]} | frames={row['frames']} | {row['decoded_seconds']}s | passed={row['passed']} | {url}",flush=True)

with open("nightah-current-recovery.json","w") as f: json.dump(rows,f,indent=2)
print("PASSING")
for r in rows:
    if r["passed"]: print(r["tvg_id"],r["url"])
