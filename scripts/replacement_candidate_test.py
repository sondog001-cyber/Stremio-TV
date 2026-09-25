#!/usr/bin/env python3
import json, re, subprocess, time, urllib.parse, urllib.request

PLAYLIST="https://raw.githubusercontent.com/nightah/daddylive/main/daddylive-channels-kodi.m3u8"
TARGET_IDS={
    "CBS.Sports.Network.USA.us":"CBSSportsNetwork.us",
    "Discovery.Channel.(US).-.Eastern.Feed.us":"DiscoveryChannel.us",
    "FX.Movie.Channel.us":"FXMovieChannel.us",
    "FXX.USA.-.Eastern.us":"FXX.us",
    "Fox.Sports.2.us":"FoxSports2.us",
    "HGTV.USA.-.Eastern.Feed.us":"HGTV.us",
    "Investigation.Discovery.USA.-.Eastern.us":"InvestigationDiscovery.us",
    "MLB.Network.us":"MLBNetwork.us",
    "NBC.Sports.Philadelphia.HDTV.(NBCSPAHD).us":"NBCSportsPhiladelphia.us",
    "Oprah.Winfrey.Network.USA.Eastern.us":"OWN.us",
    "ReelzChannel.us":"Reelz.us",
    "Smithsonian.Channel.USA.HD.us":"SmithsonianChannel.us",
    "SundanceTV.USA.-.East.us":"SundanceTV.us",
    "TLC.USA.-.Eastern.us":"TLC.us",
    "The.Weather.Channel.us":"WeatherChannel.us",
    "TheTravelChannel.us":"TravelChannel.us",
}

req=urllib.request.Request(PLAYLIST,headers={"User-Agent":"Mozilla/5.0"})
with urllib.request.urlopen(req,timeout=20) as r:
    text=r.read(8_000_000).decode("utf-8","ignore")
lines=text.splitlines()
entries=[]
for i,line in enumerate(lines):
    if not line.startswith("#EXTINF"): continue
    m=re.search(r'tvg-id="([^"]+)"',line)
    if not m or m.group(1) not in TARGET_IDS: continue
    tvg=m.group(1)
    name=line.split(",",1)[1].strip() if "," in line else tvg
    raw=""
    for j in range(i+1,min(i+8,len(lines))):
        if lines[j].strip() and not lines[j].startswith("#"):
            raw=lines[j].strip(); break
    if not raw: continue
    if "|" in raw:
        url, header_blob=raw.split("|",1)
        params=urllib.parse.parse_qs(header_blob,keep_blank_values=True)
        headers={k:urllib.parse.unquote(v[-1]) for k,v in params.items()}
    else:
        url=raw; headers={}
    entries.append({"target_id":TARGET_IDS[tvg],"source_tvg_id":tvg,"name":name,"url":url,"headers":headers})

rows=[]
for item in entries:
    started=time.time()
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-rw_timeout","10000000"]
    ua=item["headers"].get("User-Agent")
    if ua: cmd += ["-user_agent",ua]
    extra={k:v for k,v in item["headers"].items() if k.lower()!="user-agent"}
    if extra:
        cmd += ["-headers","".join(f"{k}: {v}\\r\\n" for k,v in extra.items())]
    cmd += ["-i",item["url"],"-t","12","-map","0:v:0","-vf","fps=2,scale=160:-2","-an","-f","framemd5","-"]
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=22)
        frames=sum(1 for line in p.stdout.splitlines() if line and not line.startswith("#") and "," in line)
        rows.append({**item,"frames":frames,"decoded_seconds":round(frames/2,1),"exit":p.returncode,"elapsed":round(time.time()-started,2),"stderr":p.stderr[-500:],"passed":frames>=20})
    except subprocess.TimeoutExpired:
        rows.append({**item,"frames":0,"decoded_seconds":0.0,"exit":None,"elapsed":round(time.time()-started,2),"stderr":"timeout","passed":False})

payload={"tested":len(rows),"passed":sum(1 for r in rows if r["passed"]),"rows":rows}
with open("replacement-candidates.json","w") as f: json.dump(payload,f,indent=2)
print(json.dumps(payload,indent=2))
