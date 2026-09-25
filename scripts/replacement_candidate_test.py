#!/usr/bin/env python3
import json, re, subprocess, time, urllib.request

PLAYLIST="https://8-rouge-gamma.vercel.app/playlist?url=https%3A%2F%2Fbit.ly%2Fddy-m3u2&data=MT1odHRwczovL2Nvb2tpZXdlYnBsYXkueHl6L3wyPWh0dHBzOi8vY29va2lld2VicGxheS54eXov&epgMerging=true"
TARGETS = [
    ("CBSSportsNetwork.us", ["CBS Sports Network"]),
    ("DiscoveryChannel.us", ["Discovery Channel"]),
    ("FXMovieChannel.us", ["FX Movie", "FXM"]),
    ("FXX.us", ["FXX"]),
    ("FoxSports2.us", ["Fox Sports 2", "FS2"]),
    ("HGTV.us", ["HGTV"]),
    ("InvestigationDiscovery.us", ["Investigation Discovery"]),
    ("MLBNetwork.us", ["MLB Network"]),
    ("NBCSportsPhiladelphia.us", ["NBC Sports Philadelphia"]),
    ("OWN.us", ["Oprah Winfrey Network", "OWN"]),
    ("Reelz.us", ["Reelz"]),
    ("SmithsonianChannel.us", ["Smithsonian Channel"]),
    ("SundanceTV.us", ["Sundance TV", "SundanceTV"]),
    ("TLC.us", ["TLC"]),
    ("TVLand.us", ["TV Land"]),
    ("TravelChannel.us", ["Travel Channel"]),
    ("WeatherChannel.us", ["The Weather Channel", "Weather Channel"]),
    ("RFDTV.us", ["RFD-TV", "RFD TV"]),
    ("StarzComedy.us", ["Starz Comedy"]),
    ("StarzEncoreSpanish.us", ["Starz Encore Spanish"]),
]
req=urllib.request.Request(PLAYLIST,headers={"User-Agent":"Mozilla/5.0"})
with urllib.request.urlopen(req,timeout=25) as r:
    text=r.read(8_000_000).decode("utf-8","ignore")
lines=[x.strip() for x in text.splitlines()]
entries=[]
for i,line in enumerate(lines):
    if not line.startswith("#EXTINF"): continue
    name=line.split(",",1)[1].strip() if "," in line else ""
    tvg=""
    m=re.search(r'tvg-id="([^"]*)"',line,re.I)
    if m: tvg=m.group(1)
    url=""
    for j in range(i+1,min(i+8,len(lines))):
        if lines[j] and not lines[j].startswith("#"):
            url=lines[j]; break
    if url: entries.append({"name":name,"tvg_id":tvg,"url":url})

matches=[]
for target_id,names in TARGETS:
    for e in entries:
        hay=(e["name"]+" "+e["tvg_id"]).lower()
        if any(n.lower() in hay for n in names):
            item={"target_id":target_id,**e}
            if item not in matches: matches.append(item)

rows=[]
for item in matches[:40]:
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
        rows.append({**item,"frames":0,"decoded_seconds":0.0,"exit":None,"elapsed":round(time.time()-started,2),"stderr":"timeout","passed":False})

payload={"playlist_entries":len(entries),"matches":len(matches),"tested":len(rows),"passed":sum(1 for r in rows if r["passed"]),"rows":rows}
with open("replacement-candidates.json","w") as f: json.dump(payload,f,indent=2)
print(json.dumps(payload,indent=2))
