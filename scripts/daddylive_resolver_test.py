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

def ffmpeg_decode(url, seconds=10, timeout=18, user_agent=None, referer=None):
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-rw_timeout", "10000000"]
    if user_agent:
        command += ["-user_agent", user_agent]
    if referer:
        command += ["-headers", f"Referer: {referer}\\r\\n"]
    command += [
        "-i", url, "-t", str(seconds), "-map", "0:v:0",
        "-vf", "fps=2,scale=160:-2", "-an", "-f", "framemd5", "-"
    ]
    started=time.time()
    try:
        p=subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        hashes=[]
        for line in p.stdout.splitlines():
            if not line or line.startswith("#") or "," not in line:
                continue
            hashes.append(line.split(",")[-1].strip())
        frames=len(hashes)
        repeat=False
        repeat_seconds=None
        for width in range(4,min(8,frames//2)+1):
            for pos in range(0,frames-2*width+1):
                first=hashes[pos:pos+width]
                second=hashes[pos+width:pos+2*width]
                if len(set(first)) >= 3 and first == second:
                    repeat=True
                    repeat_seconds=round(width/2,1)
                    break
            if repeat:
                break
        return {
            "frames":frames,
            "decoded_seconds":round(frames/2,1),
            "repeat_detected":repeat,
            "repeat_seconds":repeat_seconds,
            "passed":frames >= 16 and not repeat,
            "exit":p.returncode,
            "elapsed":round(time.time()-started,2),
            "stderr":p.stderr[-500:],
        }
    except subprocess.TimeoutExpired:
        return {"frames":0,"decoded_seconds":0.0,"repeat_detected":False,"passed":False,"exit":None,"elapsed":round(time.time()-started,2),"stderr":"timeout"}

def parse_vlc_headers(vlc):
    import re
    ua_match=re.search(r":http-user-agent='([^']+)'", vlc or "")
    ref_match=re.search(r":http-referrer='([^']+)'", vlc or "")
    return (
        ua_match.group(1) if ua_match else None,
        ref_match.group(1) if ref_match else None,
    )

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
                user_agent, referer = parse_vlc_headers(resolved.get("vlc"))
                attempt["direct_headers"] = {
                    "User-Agent": user_agent,
                    "Referer": referer,
                }
                attempt["direct_decode_with_headers"]=ffmpeg_decode(
                    direct,
                    seconds=10,
                    timeout=18,
                    user_agent=user_agent,
                    referer=referer,
                )
            channel_row["attempts"].append(attempt)
            if (attempt.get("direct_decode_with_headers") or {}).get("passed"):
                channel_row["passed"]=True
                channel_row["winning_server"]=server
                channel_row["publishable_direct"]=True
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
