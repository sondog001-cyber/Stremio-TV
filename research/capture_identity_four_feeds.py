#!/usr/bin/env python3
"""Capture synchronized independent network identity evidence; research only."""
import concurrent.futures, datetime, hashlib, json, subprocess, time
from pathlib import Path
FEEDS=[
 ("History US East","aynascope","https://tvsen5.aynascope.net/historyen/index.m3u8"),
 ("History US East","aynaott","https://tvsen3.aynaott.com/np3JstRE/index.m3u8"),
 ("Cooking Channel US","aynascope-cooking-unverified","https://tvsen7.aynascope.net/cooking/index.m3u8"),
 ("Tennis Channel US","tennis-independent-unverified","http://138.59.177.78:9999/play/a0gl/index.m3u8"),
]
ROOT=Path("research/diagnostics/identity-captures")
ROOT.mkdir(parents=True,exist_ok=True)
def run(item):
 name,tag,url=item
 shots=[]; errors=[]
 for i in range(3):
  path=ROOT/(tag+"-"+str(i)+".jpg")
  cmd=["ffmpeg","-hide_banner","-nostdin","-loglevel","error","-rw_timeout","15000000","-i",url,"-map","0:v:0","-frames:v","1","-vf","scale=960:-2","-y",str(path)]
  try:
   p=subprocess.run(cmd,capture_output=True,text=True,timeout=35)
   shots.append({"file":str(path) if p.returncode==0 and path.exists() else None,"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"sha256":hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,"exit":p.returncode})
   if p.returncode:errors.append(p.stderr[-300:])
  except subprocess.TimeoutExpired:errors.append("capture timeout")
  if i<2:time.sleep(20)
 return {"name":name,"tag":tag,"shots":shots,"errors":errors,"network_logo_verified":False,"us_east_schedule_verified":False,"identity_verified":False}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 results=list(pool.map(run,FEEDS))
# These captures are evidence for manual review, not automatic proof of channel identity.
report={"captured_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"results":results,"promotion_approved":False,"warning":"Unverified until frames and contemporaneous US East schedule compared by reviewer."}
(ROOT/"report.json").write_text(json.dumps(report,indent=2)+"\n")
for r in results:print(r["tag"],"frames",sum(bool(s.get("file")) for s in r["shots"]),"identity_verified",False,"errors",r["errors"],flush=True)
