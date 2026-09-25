#!/usr/bin/env python3
import argparse, concurrent.futures, json, os, re, subprocess, tempfile, time, urllib.request

UA = "StremioTV-FrameSweep/1.0"

def fetch_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(8_000_000))

def hashes_from_framemd5(text):
    out=[]
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith("#"):
            continue
        parts=[p.strip() for p in line.split(",")]
        if len(parts) >= 6 and re.fullmatch(r"[0-9a-fA-F]{32}", parts[-1]):
            out.append(parts[-1].lower())
    return out

def find_repeat(hashes, fps=2):
    # Look for immediate repeated clips from 2 to 4 seconds.
    for width in range(int(2*fps), int(4*fps)+1):
        for start in range(0, len(hashes)-2*width+1):
            a=hashes[start:start+width]
            b=hashes[start+width:start+2*width]
            # Avoid static/slate false positives.
            if len(set(a)) < 3:
                continue
            if a == b:
                return {
                    "start_frame":start,
                    "width_frames":width,
                    "seconds":round(width/fps,2),
                    "unique_frames":len(set(a)),
                }
    return None

def ffmpeg_test(item, seconds=18, timeout=32, fps=2):
    url=item["url"]
    headers=item.get("headers") or {}
    cmd=[
        "ffmpeg","-hide_banner","-loglevel","error",
        "-nostdin","-user_agent",UA,
        "-rw_timeout","10000000",
    ]
    if headers:
        blob="".join(f"{k}: {v}\r\n" for k,v in headers.items())
        cmd += ["-headers", blob]
    cmd += [
        "-i",url,
        "-t",str(seconds),
        "-map","0:v:0",
        "-vf",f"fps={fps},scale=160:-2",
        "-an",
        "-f","framemd5","-",
    ]
    started=time.time()
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout)
        elapsed=round(time.time()-started,2)
        hashes=hashes_from_framemd5(p.stdout)
        repeat=find_repeat(hashes,fps=fps) if hashes else None
        return {
            **item,
            "status":"repeat" if repeat else ("clean" if len(hashes) >= fps*6 else "insufficient"),
            "elapsed_seconds":elapsed,
            "decoded_frames":len(hashes),
            "repeat":repeat,
            "ffmpeg_exit":p.returncode,
            "stderr":p.stderr[-500:] if p.stderr else "",
        }
    except subprocess.TimeoutExpired as exc:
        return {**item,"status":"timeout","elapsed_seconds":round(time.time()-started,2),"decoded_frames":0,"repeat":None,"stderr":"ffmpeg timeout"}
    except Exception as exc:
        return {**item,"status":"error","elapsed_seconds":round(time.time()-started,2),"decoded_frames":0,"repeat":None,"stderr":str(exc)[:500]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--preview-url",required=True)
    ap.add_argument("--seconds",type=int,default=18)
    ap.add_argument("--workers",type=int,default=8)
    ap.add_argument("--timeout",type=int,default=32)
    ap.add_argument("--fps",type=int,default=2)
    ap.add_argument("--output",default="frame-repetition-sweep.json")
    args=ap.parse_args()

    preview=fetch_json(args.preview_url)
    items=[]
    for row in preview.get("channels",[]):
        ch=row.get("channel") or {}
        streams=row.get("streams") or []
        if not streams: continue
        s=streams[0]
        hints=s.get("behaviorHints") or {}
        proxy=hints.get("proxyHeaders") or {}
        items.append({
            "channel_id":ch.get("id"),
            "channel_name":ch.get("name"),
            "stream_name":s.get("name"),
            "url":s.get("url"),
            "headers":proxy.get("request") or {},
        })

    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs={ex.submit(ffmpeg_test,x,args.seconds,args.timeout,args.fps):x for x in items}
        for i,fut in enumerate(concurrent.futures.as_completed(futs),1):
            r=fut.result()
            results.append(r)
            print(f"[{i}/{len(items)}] {r['channel_name']}: {r['status']} frames={r.get('decoded_frames',0)}",flush=True)

    order={x["channel_id"]:i for i,x in enumerate(items)}
    results.sort(key=lambda r:order.get(r["channel_id"],9999))
    repeats=[r["channel_name"] for r in results if r["status"]=="repeat"]
    clean=[r["channel_name"] for r in results if r["status"]=="clean"]
    unresolved=[r["channel_name"] for r in results if r["status"] not in {"clean","repeat"}]
    payload={
        "tested_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
        "preview_url":args.preview_url,
        "seconds_per_channel":args.seconds,
        "fps":args.fps,
        "channels_tested":len(results),
        "summary":{
            "repeat_detected":len(repeats),
            "clean":len(clean),
            "unresolved":len(unresolved),
        },
        "repeat_channels":repeats,
        "unresolved_channels":unresolved,
        "results":results,
    }
    with open(args.output,"w",encoding="utf-8") as f: json.dump(payload,f,indent=2)
    print(json.dumps({k:v for k,v in payload.items() if k!="results"},indent=2))
    if repeats:
        raise SystemExit(2)

if __name__=="__main__":
    main()
