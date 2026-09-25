#!/usr/bin/env python3
import hashlib, json, re, subprocess, time, urllib.request

PREVIEW="https://sondog001-cyber.github.io/Stremio-TV/diagnostics/stremio-preview.json"
CHANNEL="NewsNation"
UA="StremioTV-NBC-ReconnectTest/1.0"

def fetch_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=15) as r:
        return json.loads(r.read(8_000_000))

def hashes_from_framemd5(text):
    out=[]
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith("#"): continue
        parts=[p.strip() for p in line.split(",")]
        if len(parts)>=6 and re.fullmatch(r"[0-9a-fA-F]{32}",parts[-1]):
            out.append(parts[-1].lower())
    return out

preview=fetch_json(PREVIEW)
item=None
for row in preview.get("channels",[]):
    ch=row.get("channel") or {}
    if ch.get("name")==CHANNEL:
        s=(row.get("streams") or [None])[0]
        if s:
            hints=s.get("behaviorHints") or {}
            item={
                "channel_id":ch.get("id"),
                "channel_name":CHANNEL,
                "stream_name":s.get("name"),
                "url":s.get("url"),
                "headers":((hints.get("proxyHeaders") or {}).get("request") or {}),
            }
        break
if not item:
    raise SystemExit("NewsNation primary not found")

attempts=[]
for attempt in range(1,7):
    cmd=[
        "ffmpeg","-hide_banner","-loglevel","error","-nostdin",
        "-user_agent",UA,"-rw_timeout","10000000",
    ]
    if item["headers"]:
        cmd += ["-headers","".join(f"{k}: {v}\r\n" for k,v in item["headers"].items())]
    cmd += [
        "-i",item["url"],"-t","8","-map","0:v:0",
        "-vf","fps=2,scale=160:-2","-an","-f","framemd5","-"
    ]
    started=time.time()
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=15)
        hashes=hashes_from_framemd5(p.stdout)
        attempts.append({
            "attempt":attempt,
            "elapsed_seconds":round(time.time()-started,3),
            "frames":len(hashes),
            "hashes":hashes,
            "sequence_sha256":hashlib.sha256("|".join(hashes).encode()).hexdigest() if hashes else None,
            "exit":p.returncode,
            "stderr":p.stderr[-800:],
        })
    except subprocess.TimeoutExpired:
        attempts.append({"attempt":attempt,"elapsed_seconds":15,"frames":0,"hashes":[],"sequence_sha256":None,"exit":None,"stderr":"timeout"})
    time.sleep(2)

nonempty=[a for a in attempts if a["hashes"]]
prefix_matches=[]
if len(nonempty)>=2:
    base=nonempty[0]["hashes"]
    for a in nonempty[1:]:
        n=min(len(base),len(a["hashes"]))
        same=0
        for i in range(n):
            if base[i]!=a["hashes"][i]: break
            same+=1
        prefix_matches.append({"attempt":a["attempt"],"common_prefix_frames":same,"compared_frames":n})

full_sequences=[a["sequence_sha256"] for a in nonempty if a["sequence_sha256"]]
payload={
    "channel":CHANNEL,
    "attempts":attempts,
    "summary":{
        "attempts_with_video":len(nonempty),
        "frame_counts":[a["frames"] for a in attempts],
        "elapsed_seconds":[a["elapsed_seconds"] for a in attempts],
        "identical_full_sequences":len(set(full_sequences))==1 if full_sequences else False,
        "prefix_matches_to_attempt_1":prefix_matches,
    }
}
with open("newsnation-reconnect-test.json","w",encoding="utf-8") as f:
    json.dump(payload,f,indent=2)
print(json.dumps(payload["summary"],indent=2))
for a in attempts:
    print(f"attempt {a['attempt']}: frames={a['frames']} elapsed={a['elapsed_seconds']} exit={a['exit']}")
    if a["stderr"]:
        print(a["stderr"].replace(item["url"],"<stream-url>"))
