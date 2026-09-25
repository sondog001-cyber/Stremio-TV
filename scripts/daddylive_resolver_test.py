#!/usr/bin/env python3
import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:3000"
SERVERS = ["stream", "cast", "watch", "plus", "casting", "player"]
CHANNELS = [
    ("Bravo", 307),
    ("CBS Sports Network", 308),
    ("Discovery Channel", 313),
    ("FXX", 298),
    ("Fox Sports 2", 758),
    ("HGTV", 382),
    ("Investigation Discovery", 324),
    ("MLB Network", 399),
    ("NBC Sports Philadelphia", 777),
    ("Nicktoons", 649),
    ("OWN", 331),
    ("Reelz", 293),
    ("Smithsonian Channel", 603),
    ("SundanceTV", 658),
    ("TLC", 337),
    ("Weather Channel", 394),
    ("Travel Channel", 340),
    ("FX Movie Channel", 381),
    ("Magnolia Network", 299),
]

def get_json(url, timeout=18):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))

def ffmpeg_decode(url, seconds=10, timeout=18):
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
        "-rw_timeout", "10000000", "-i", url,
        "-t", str(seconds), "-map", "0:v:0",
        "-vf", "fps=2,scale=160:-2", "-an", "-f", "framemd5", "-"
    ]
    started=time.time()
    try:
        p=subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        frames=sum(1 for line in p.stdout.splitlines() if line and not line.startswith("#") and "," in line)
        return {
            "frames":frames,
            "decoded_seconds":round(frames/2,1),
            "passed":frames >= 16,
            "exit":p.returncode,
            "elapsed":round(time.time()-started,2),
            "stderr":p.stderr[-500:],
        }
    except subprocess.TimeoutExpired:
        return {"frames":0,"decoded_seconds":0.0,"passed":False,"exit":None,"elapsed":round(time.time()-started,2),"stderr":"timeout"}

rows=[]
for name, channel_id in CHANNELS:
    channel_row={"channel":name,"channel_id":channel_id,"attempts":[],"passed":False}
    for server in SERVERS:
        resolve_url=f"{BASE}/api/resolve?channel={channel_id}&server={urllib.parse.quote(server)}"
        started=time.time()
        try:
            resolved=get_json(resolve_url)
            attempt={
                "server":server,
                "resolve_ok":True,
                "resolve_seconds":round(time.time()-started,2),
                "direct":resolved.get("direct"),
                "live":resolved.get("live"),
                "vlc":resolved.get("vlc"),
                "mpv":resolved.get("mpv"),
                "expiresAt":resolved.get("expiresAt"),
                "isHls":resolved.get("isHls"),
            }
            live=resolved.get("live")
            if live and live.startswith("/"):
                live=BASE+live
            if live:
                attempt["live_decode"]=ffmpeg_decode(live)
            direct=resolved.get("direct")
            if direct:
                attempt["direct_decode_no_headers"]=ffmpeg_decode(direct, seconds=6, timeout=14)
            channel_row["attempts"].append(attempt)
            if (attempt.get("live_decode") or {}).get("passed"):
                channel_row["passed"]=True
                channel_row["winning_server"]=server
                break
        except Exception as exc:
            channel_row["attempts"].append({
                "server":server,
                "resolve_ok":False,
                "resolve_seconds":round(time.time()-started,2),
                "error":str(exc)[:500],
            })
    rows.append(channel_row)
    print(json.dumps(channel_row, indent=2), flush=True)

with open("daddylive-resolver-test.json","w") as f:
    json.dump(rows,f,indent=2)
print(json.dumps({
    "tested":len(rows),
    "passed":sum(1 for r in rows if r["passed"]),
    "passing_channels":[r["channel"] for r in rows if r["passed"]],
}, indent=2))
