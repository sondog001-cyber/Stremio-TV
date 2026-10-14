#!/usr/bin/env python3
"""Read-only 111-lineup recovery discovery with strict identity and media vetting.

Discover exact tvg-ids from public GitHub M3U sources; test ONLY direct HTTP(S)
HLS candidates. Do not change config, allowlist, streams, primary ordering, QA,
deployed artifacts, or automatically approve program identity.
"""
import concurrent.futures
import datetime
import hashlib
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

PUBLIC_PLAYLISTS = [
    ("iptv-org-master", "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/us.m3u"),
    ("judy-moveonjoy", "https://raw.githubusercontent.com/judy-gotv/iptv/main/Moveonjoy.m3u"),
    ("cereslabx-us", "https://raw.githubusercontent.com/CeresLabX/us-tv/main/playlist.m3u"),
    ("doms9-base", "https://raw.githubusercontent.com/doms9/iptv/default/M3U8/base.m3u8"),
]
# Exact output IDs ONLY; US East, US national and named Philly affiliates.
# Exclude FAST spinoffs, foreign feeds, radio and West regional variants.
IDENTITIES = {
    "History.us": ["History.us", "History.us@East"],
    "CookingChannel.us": ["CookingChannel.us", "CookingChannel.us@SD"],
    "NationalGeographic.us": ["NationalGeographic.us", "NationalGeographic.us@East", "NationalGeographic.us@HDEast"],
    "DisneyChannel.us": ["DisneyChannel.us", "DisneyChannel.us@East"],
    "Bravo.us": ["Bravo.us", "Bravo.us@East"],
    "USANetwork.us": ["USANetwork.us", "USANetwork.us@East"],
    "E.us": ["E.us", "E.us@East"],
    "WPVI.us": ["WPVI.us", "WPVIDT1.us", "ABCWPVI.us"],
    "WCAU.us": ["WCAU.us", "WCAUDT1.us", "NBC10WCAU.us"],
    "KYW.us": ["KYW.us", "KYWDT1.us", "CBS3KYW.us"],
    "WPHL.us": ["WPHL.us", "WPHLDT1.us"],
    "WPSG.us": ["WPSG.us", "WPSGDT1.us"],
    # Secondary exact gaps provide extra safety above the 86-channel floor.
    "BET.us": ["BET.us", "BET.us@East"],
    "CMT.us": ["CMT.us", "CMT.us@East"],
    "FoodNetwork.us": ["FoodNetwork.us", "FoodNetwork.us@East"],
    "CBSSportsNetwork.us": ["CBSSportsNetwork.us"],
    "ESPNews.us": ["ESPNews.us"],
    "StarzKidsFamily.us": ["StarzKidsFamily.us", "StarzKidsFamily.us@East"],
    "CinemaxHits.us": ["CinemaxHits.us", "CinemaxHits.us@East"],
    "MLBStrikeZone.us": ["MLBStrikeZone.us", "MLBStrikeZone.us@SD"],
    "WEtv.us": ["WEtv.us", "WEtv.us@East"],
}
ID_LOOKUP={alias.lower():canonical for canonical,aliases in IDENTITIES.items() for alias in aliases}
SEEDS=[
    ("NationalGeographic.us","natgeo-known-hd-east","http://198.58.104.90:8989/natgeo/index.m3u8"),
    ("History.us","history-aynaott-alt","https://tvsen3.aynaott.com/np3JstRE/index.m3u8"),
    ("History.us","history-aynascope","https://tvsen5.aynascope.net/historyen/index.m3u8"),
    ("CookingChannel.us","cooking-aynascope","https://tvsen7.aynascope.net/cooking/index.m3u8"),
    ("DisneyChannel.us","disney-moveonjoy-fl12","http://fl12.moveonjoy.com/DISNEY/index.m3u8"),
    ("NationalGeographic.us","natgeo-moveonjoy-fl31","https://fl31.moveonjoy.com/National_Geographic/index.m3u8"),
    ("E.us","e-moveonjoy-https","https://fl2.moveonjoy.com/E_ENTERTAINMENT_TELEVISION/index.m3u8"),
    ("Bravo.us","bravo-aynascope-english","http://tvsen7.aynascope.net/bravo/index.m3u8"),
    ("Bravo.us","bravo-new-40-160-host","http://40.160.24.52/BRAVO/index.m3u8"),
    ("USANetwork.us","usa-new-190-11-host","http://190.11.225.124:5000/live/usa_hd/playlist.m3u8"),
    ("USANetwork.us","usa-new-40-160-host","http://40.160.24.55/USA_NETWORK/index.m3u8"),
    ("History.us","history-alt-84-origin","http://84.17.50.102/history/index.m3u8"),
]
KNOWN_PREVIOUSLY_FAILED_HOSTS={
    "23.237.104.106", "212.5.144.156", "41.205.93.154",
    "190.197.41.183","200.32.231.178","v-pi.theus6tv.tk",
}
def clean_id(value):
    return ID_LOOKUP.get(value.strip().lower())
def permitted_url(url):
    if not url.startswith(("http://","https://")):return False,"not-http"
    p=urlsplit(url)
    if not p.hostname:return False,"no-host"
    if p.username or p.password:return False,"embedded-basic-auth"
    if re.search(r"(?i)(?:username|password|passwd|apikey|api_key)=",p.query):return False,"account-query"
    if re.search(r"(?i)/(?:live|movie|series)/[^/]{3,}/[^/]{4,}/\d+(?:\.m3u8)?$",p.path):return False,"xtream-credential-path"
    if re.search(r"(?i)(?:drm|widevine|playready)",url):return False,"protected"
    if not (".m3u8" in p.path or "/play/" in p.path or "/live/" in p.path):
        return False,"not-obvious-direct-hls"
    return True,""
def get_playlist(url):
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Stremio-TV-recovery-research/1.0"})
        with urllib.request.urlopen(req,timeout=22) as resp:
            data=resp.read(3_000_000).decode("utf-8","replace")
        return data,None
    except Exception as exc:
        return "",str(exc)[:200]
def parse_m3u(raw,label):
    pending=None
    for line in raw.splitlines():
        text=line.strip()
        if text.startswith("#EXTINF:"):
            match=re.search(r'tvg-id="([^"]+)"',text,re.I)
            pending=clean_id(match.group(1)) if match else None
        elif pending is not None and text.startswith(("http://","https://")):
            ok,reason=permitted_url(text)
            yield {"identity":pending,"url":text,"playlist":label,"permitted":ok,"reason":reason}
            pending=None
def ffmpeg_check(url,seconds):
    cmd=["ffmpeg","-hide_banner","-nostdin","-loglevel","error",
        "-rw_timeout","12000000","-user_agent","Mozilla/5.0"]
    cmd+=["-i",url,"-map","0:v:0","-an","-t",str(seconds),
          "-vf","fps=2,scale=160:-2","-f","framemd5","-"]
    started=time.monotonic()
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=seconds+25)
        frames=[line.split(",")[-1].strip() for line in p.stdout.splitlines()
            if not line.startswith("#") and re.search(r",\s*[0-9a-f]{32}\s*$",line)]
        windows=[tuple(frames[i:i+4]) for i in range(0,len(frames)-3,4)]
        short_loop=len(windows)>=3 and len(set(windows))<len(windows)
        success=p.returncode==0 and len(frames)>=seconds*1.3 and len(set(frames))>=4 and not short_loop
        return {"passed":success,"exit":p.returncode,"frames":len(frames),
           "distinct_frames":len(set(frames)),"loop":short_loop,
           "first_hash":hashlib.sha256(",".join(frames[:12]).encode()).hexdigest()[:12],
           "elapsed":round(time.monotonic()-started,1),"error":p.stderr[-240:]}
    except subprocess.TimeoutExpired:
        return {"passed":False,"error":"timeout"}
def test(row):
    entry={"identity":row["identity"],"playlist":row["playlist"],"url":row["url"],
       "origin":urlsplit(row["url"]).netloc,
       "previously_failing_origin":urlsplit(row["url"]).hostname in KNOWN_PREVIOUSLY_FAILED_HOSTS,
       "attempts":[],"media_pass":False,"identity_verified":False,
       "programme_matches_us_east":False}
    for sec in (12,12,65):
        report=ffmpeg_check(entry["url"],sec)
        report["requested_seconds"]=sec
        entry["attempts"].append(report)
        if not report["passed"]:break
        if len(entry["attempts"])==2 and report["first_hash"]==entry["attempts"][0]["first_hash"]:
            entry["warning"]="identical first frames across delayed rechecks"
            break
        if sec==12:time.sleep(4)
    entry["media_pass"]=len(entry["attempts"])==3 and all(x["passed"] for x in entry["attempts"])
    print(entry["identity"],entry["playlist"],entry["origin"],"pass",entry["media_pass"],flush=True)
    return entry
def main():
    captured=[]
    errors={}
    for label,url in PUBLIC_PLAYLISTS:
        raw,error=get_playlist(url)
        if error:errors[label]=error;continue
        captured.extend(parse_m3u(raw,label))
    for identity,label,url in SEEDS:
        ok,reason=permitted_url(url)
        captured.append({"identity":identity,"url":url,"playlist":label,"permitted":ok,"reason":reason})
    rejected=[]
    distinct={}
    for r in captured:
        if not r["permitted"]:
            rejected.append({k:r[k] for k in ("identity","playlist","reason")})
            continue
        # If a URL appears in two playlists, retain source provenance.
        key=(r["identity"],r["url"])
        if key in distinct:distinct[key]["also_in"].append(r["playlist"])
        else:distinct[key]={**r,"also_in":[]}
    # Control runner load: sample per channel with seed priority, distinct origin preference.
    groups={}
    for x in distinct.values():groups.setdefault(x["identity"],[]).append(x)
    selected=[]
    for name,rows in groups.items():
        rows.sort(key=lambda r:(r["playlist"] not in [s[1] for s in SEEDS],urlsplit(r["url"]).hostname in KNOWN_PREVIOUSLY_FAILED_HOSTS))
        hosts=set()
        for r in rows:
            h=urlsplit(r["url"]).netloc
            if h in hosts:continue
            selected.append(r);hosts.add(h)
            if len(hosts)>=5:break
    selected=selected[:75]
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        tested=list(pool.map(test,selected))
    outfile=Path("research/diagnostics/priority-12-source-sweep.json")
    outfile.parent.mkdir(parents=True,exist_ok=True)
    results={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "target_channel_count":len(IDENTITIES),"discovered":len(captured),
      "unique_permitted":len(distinct),"rejected":rejected[:45],
      "playlist_errors":errors,"tested":len(tested),
      "media_qualified":[r for r in tested if r["media_pass"]],
      "all_results":tested,
      "caution":"Research only. Full media pass DOES NOT verify exact network or availability in full addon QA. No automatic promotion."}
    outfile.write_text(json.dumps(results,indent=2)+"\n")
    print("SUMMARY",json.dumps({"discovered":len(captured),"unique":len(distinct),
       "tested":len(tested),"media_qualified":[(r["identity"],r["origin"]) for r in tested if r["media_pass"]],
       "errors":errors},indent=2))
if __name__=="__main__":main()
