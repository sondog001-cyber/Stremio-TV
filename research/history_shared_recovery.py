#!/usr/bin/env python3
"""Read-only simultaneous diagnostics: intermittent History, shared origin, missing channels.
No curated files are modified. Decoder health never establishes channel identity.
"""
import concurrent.futures
import datetime
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

SHARED = {
 "CMT.us@East": "USA_CMT",
 "CinemaxHits.us@East": "USA_MOREMAX",
 "CookingChannel.us@SD": "USA_COOKING",
 "E.us@East": "USA_E",
 "MLBStrikeZone.us@SD": "USA_MLB_STRIKE_ZONE",
 "StarzKidsFamily.us@East": "USA_STARZ_FAMILY",
 "TennisChannel.us@SD": "USA_TENNIS",
 "WeTV.us@East": "USA_WE_TV",
 "truTV.us@East": "USA_TRUTV",
 "BigTenNetwork.us@SD": "USA_BTN",
 "OneAmericaNewsNetwork.us@SD": "USA_OAN",
 "SECNetwork.us@SD": "USA_SEC_NETWORK",
 "ScienceChannel.us": "USA_SCIENCE",
}
# List all 13 known dependent paths; historical outage analysis called this
# an 11-channel shared origin. Preserve exact identities instead of presuming count.
ROWS = [
 {"id":"History.us@East","tag":"aynascope-history-en","url":"https://tvsen5.aynascope.net/historyen/index.m3u8","kind":"history"},
 {"id":"History.us@East","tag":"aynaott-history-alt","url":"https://tvsen3.aynaott.com/np3JstRE/index.m3u8","kind":"history"},
 {"id":"History.us@East","tag":"legacy-history","url":"http://212.5.144.156:8080/history/index.m3u8","kind":"history"},
 {"id":"History.us@East","tag":"tv247-history-memfs","url":"https://ft.fbcdntv247.cfd/memfs/7ba806d9-3ae3-4425-a46d-90db0b27988a_output_0.m3u8","kind":"history"},
 {"id":"CookingChannel.us@SD","tag":"insolence-cooking-different-origin","url":"http://212.102.60.231/COOKING_CHANNEL/index.m3u8","kind":"missing"},
 {"id":"CMT.us@East","tag":"insolence-cmt-different-origin","url":"http://212.102.60.231/CMT/index.m3u8","kind":"missing"},
 {"id":"WeTV.us@East","tag":"insolence-wetv-different-origin","url":"http://212.102.60.231/WE_TV/index.m3u8","kind":"missing"},
 {"id":"MLBStrikeZone.us@SD","tag":"insolence-mlb-different-origin","url":"http://74.48.44.156:1234/stream/asd/474/master.m3u8","kind":"missing"},
 {"id":"StarzKidsFamily.us@East","tag":"insolence-starz-kids-different-origin","url":"http://74.48.44.156:1234/stream/asd/468/master.m3u8","kind":"missing"},
 {"id":"BET.us","tag":"tv247-bet-memfs","url":"https://ft.fbcdntv247.cfd/memfs/bet.m3u8","kind":"missing"},
 {"id":"BET.us","tag":"tvnow-bet","url":"https://cache0.wonvt.st/live/1a3of01189opd41qnda9f/master.m3u8","referer":"https://tvnow.st/","kind":"missing"},
 {"id":"BET.us","tag":"moveonjoy-bet-east","url":"http://fl2.moveonjoy.com/BET_EAST/index.m3u8","kind":"missing"},
 {"id":"TennisChannel.us@SD","tag":"independent-tennis","url":"http://138.59.177.78:9999/play/a0gl/index.m3u8","kind":"missing"},
 {"id":"TennisChannel.us@SD","tag":"moveonjoy-tennis-fl3","url":"http://fl3.moveonjoy.com/TENNIS_CHANNEL/index.m3u8","kind":"missing"},
 {"id":"truTV.us@East","tag":"moveonjoy-trutv-east","url":"http://fl2.moveonjoy.com/TRU_TV/index.m3u8","kind":"missing"},
 {"id":"E.us@East","tag":"wonvt-e-east-retry","url":"https://cache0.wonvt.st/live/15a0cd61f3w7um0229g5g/master.m3u8","referer":"https://tvnow.st/","kind":"missing"},
 {"id":"CookingChannel.us@SD","tag":"aynascope-cooking-retry","url":"https://tvsen7.aynascope.net/cooking/index.m3u8","kind":"missing"},
 {"id":"CinemaxHits.us@East","tag":"insolence-moremax-east","url":"http://74.48.44.156:1234/stream/asd/343/master.m3u8","kind":"missing"},
]
for identity, suffix in SHARED.items():
 ROWS.append({"id":identity,"tag":"original-shared-origin","url":f"http://23.237.104.106:8080/{suffix}/index.m3u8","kind":"shared"})

def probe(url, seconds, referer=""):
 cmd=["ffmpeg","-hide_banner","-nostdin","-loglevel","error","-rw_timeout","15000000","-user_agent","Mozilla/5.0"]
 if referer:cmd+=["-headers","Referer: "+referer+"\r\n"]
 cmd+=["-i",url,"-map","0:v:0","-an","-t",str(seconds),"-vf","fps=2,scale=160:-2","-f","framemd5","-"]
 start=time.monotonic()
 try:
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=seconds+35)
  frames=[x.rsplit(",",1)[-1].strip() for x in p.stdout.splitlines() if not x.startswith("#") and re.search(r",[0-9a-f]{32}\s*$",x)]
  chunks=[tuple(frames[i:i+4]) for i in range(0,len(frames)-3,4)]
  loop=len(chunks)>3 and len(set(chunks))<len(chunks)
  ok=p.returncode==0 and len(frames)>=int(seconds*1.4) and len(set(frames))>=4 and not loop
  return {"ok":ok,"returncode":p.returncode,"frames":len(frames),"unique":len(set(frames)),"short_loop":loop,"seconds":seconds,"elapsed":round(time.monotonic()-start,1),"fingerprint":hashlib.sha256(",".join(frames[:12]).encode()).hexdigest()[:16],"error":p.stderr[-280:]}
 except subprocess.TimeoutExpired:
  return {"ok":False,"error":"timeout","seconds":seconds,"elapsed":round(time.monotonic()-start,1)}

def check(row):
 data={k:v for k,v in row.items() if k!="url"}
 data["origin"]=urlsplit(row["url"]).netloc
 data["probes"]=[]
 for seconds in (12,12,65):
  p=probe(row["url"],seconds,row.get("referer",""))
  data["probes"].append(p)
  if not p["ok"]:break
  if len(data["probes"])==2 and data["probes"][0]["fingerprint"]==p["fingerprint"]:
   data["warning"]="identical decoder restart fingerprints"
   break
  if seconds==12:time.sleep(4)
 data["full_media_pass"]=len(data["probes"])==3 and all(p["ok"] for p in data["probes"])
 data["identity_verified"]=False
 print(data["id"],data["tag"],"passed",data["full_media_pass"],"probe-count",len(data["probes"]),flush=True)
 return data

def main():
 start=time.monotonic()
 with concurrent.futures.ThreadPoolExecutor(max_workers=9) as pool:
  results=list(pool.map(check,ROWS))
 by_kind={k:[r for r in results if r["kind"]==k] for k in ("history","shared","missing")}
 data={"timestamp":datetime.datetime.now(datetime.timezone.utc).isoformat(),"read_only":True,"identity_verified_count":0,"results":results,
 "summary":{k:{"tested":len(v),"full_media_pass":sum(r["full_media_pass"] for r in v),"passing_tags":[r["tag"] for r in v if r["full_media_pass"]]} for k,v in by_kind.items()},"elapsed":round(time.monotonic()-start,1)}
 dest=Path("research/diagnostics/history-shared-recovery.json")
 dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(data,indent=2)+"\n")
 print(json.dumps(data["summary"],indent=2))
 print("No source promoted. Full media decoding is not identity validation.")
if __name__=="__main__":main()
