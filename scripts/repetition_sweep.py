#!/usr/bin/env python3
import argparse, concurrent.futures, hashlib, json, re, time, urllib.parse, urllib.request
from collections import defaultdict

UA = "StremioTV-RepetitionSweep/1.0"

def fetch(url, headers=None, timeout=8, limit=1_000_000):
    h = {"User-Agent": UA, "Accept": "*/*", "Accept-Encoding": "identity"}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.geturl(), r.read(limit), (r.headers.get("Content-Type") or "").lower()

def parse_attrs(line):
    out = {}
    for m in re.finditer(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)', line, re.I):
        out[m.group(1).upper()] = m.group(2).strip('"')
    return out

def choose_media(text, base, headers, timeout):
    lines = [x.strip() for x in text.splitlines()]
    variants = []
    for i, line in enumerate(lines):
        if not line.upper().startswith("#EXT-X-STREAM-INF:"):
            continue
        attrs = parse_attrs(line.split(":",1)[1])
        uri = next((x for x in lines[i+1:] if x and not x.startswith("#")), "")
        if not uri:
            continue
        res = attrs.get("RESOLUTION","0x0").lower().split("x")
        try: score = (int(res[-1]), int(attrs.get("BANDWIDTH","0")))
        except: score = (0,0)
        variants.append((score, urllib.parse.urljoin(base, uri)))
    if not variants:
        return base, text
    media = max(variants, key=lambda x:x[0])[1]
    final, body, _ = fetch(media, headers, timeout)
    return final, body.decode("utf-8","ignore")

def repeated_uri_pattern(uris, max_width=3):
    u = [x for x in uris if x]
    for width in range(1, min(max_width, len(u)//2)+1):
        for start in range(len(u)-2*width+1):
            if u[start:start+width] == u[start+width:start+2*width]:
                return {"start":start,"width":width,"sequence":u[start:start+width]}
    return None

def probe(item, timeout=8, segment_bytes=131072):
    url = item["url"]
    headers = item.get("headers") or {}
    result = {"url":url, "ok":False}
    try:
        final, body, ctype = fetch(url, headers, timeout)
        text = body.decode("utf-8","ignore")
        if "#EXTM3U" not in text and "mpegurl" not in ctype and ".m3u8" not in urllib.parse.urlsplit(final).path.lower():
            result.update({"error":"not-hls"})
            return result
        media_url, media = choose_media(text, final, headers, timeout)
        if "#EXTM3U" not in media:
            result.update({"error":"invalid-media-playlist"})
            return result
        lines = [x.strip() for x in media.splitlines() if x.strip()]
        target = None
        seq = None
        for line in lines:
            m = re.match(r"#EXT-X-TARGETDURATION:(\d+)", line, re.I)
            if m: target = int(m.group(1))
            m = re.match(r"#EXT-X-MEDIA-SEQUENCE:(\d+)", line, re.I)
            if m: seq = int(m.group(1))
        segs = [x for x in lines if not x.startswith("#")]
        live = not any(x.upper().startswith("#EXT-X-ENDLIST") for x in lines)
        pattern = None if any("EXT-X-BYTERANGE" in x.upper() for x in lines) else repeated_uri_pattern(segs)
        tail = segs[-4:]
        hashes = []
        if not any("EXT-X-BYTERANGE" in x.upper() for x in lines):
            start_index = max(0, len(segs)-len(tail))
            for offset, uri in enumerate(tail):
                seg_url = urllib.parse.urljoin(media_url, uri)
                sh = dict(headers)
                sh["Range"] = f"bytes=0-{segment_bytes-1}"
                try:
                    _, data, _ = fetch(seg_url, sh, timeout, segment_bytes)
                    digest = hashlib.sha256(data).hexdigest() if len(data) >= 4096 else None
                    hashes.append({
                        "seq": (seq + start_index + offset) if seq is not None else None,
                        "uri": seg_url,
                        "hash": digest,
                        "bytes": len(data),
                    })
                except Exception as exc:
                    hashes.append({"seq":None,"uri":seg_url,"hash":None,"error":str(exc)[:120]})
        result.update({
            "ok":True,
            "final_url":media_url,
            "live":live,
            "media_sequence":seq,
            "target_duration":target,
            "segment_count":len(segs),
            "tail":tail,
            "tail_hash":hashlib.sha256("\n".join(tail).encode()).hexdigest() if tail else None,
            "repeated_uri_pattern":pattern,
            "segment_hashes":hashes,
        })
        return result
    except Exception as exc:
        result["error"] = str(exc)[:180]
        return result

def load_preview(url, timeout):
    _, body, _ = fetch(url, timeout=timeout, limit=8_000_000)
    return json.loads(body)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview-url", required=True)
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--interval", type=int, default=6)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--timeout", type=int, default=8)
    ap.add_argument("--output", default="repetition-sweep.json")
    args = ap.parse_args()

    preview = load_preview(args.preview_url, args.timeout)
    items = []
    for row in preview.get("channels", []):
        ch = row.get("channel") or {}
        streams = row.get("streams") or []
        if not streams:
            continue
        s = streams[0]  # What Stremio will try first for this channel.
        hints = s.get("behaviorHints") or {}
        proxy = hints.get("proxyHeaders") or {}
        items.append({
            "channel_id": ch.get("id"),
            "channel_name": ch.get("name"),
            "stream_name": s.get("name"),
            "url": s.get("url"),
            "headers": proxy.get("request") or {},
        })

    rounds = max(2, args.duration // args.interval + 1)
    history = {x["channel_id"]: [] for x in items}
    started = time.time()
    for r in range(rounds):
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = {ex.submit(probe, item, args.timeout): item for item in items}
            for fut in concurrent.futures.as_completed(futures):
                item = futures[fut]
                try: result = fut.result()
                except Exception as exc: result = {"ok":False,"error":str(exc)[:180]}
                history[item["channel_id"]].append({"round":r,"at":round(time.time()-started,2),**result})
        if r != rounds-1:
            remaining = args.interval - ((time.time()-started) % args.interval)
            time.sleep(max(0.1, remaining))

    results = []
    repeat_channels = []
    stalled_channels = []
    probe_error_channels = []
    for item in items:
        samples = history[item["channel_id"]]
        ok = [s for s in samples if s.get("ok")]
        reasons = []
        if any(s.get("repeated_uri_pattern") for s in ok):
            reasons.append("repeated-uri-sequence-in-playlist")

        seq_hash = {}
        for s in ok:
            for h in s.get("segment_hashes") or []:
                if h.get("seq") is not None and h.get("hash"):
                    seq_hash[h["seq"]] = h["hash"]
        duplicate_pairs = []
        for seq in sorted(seq_hash):
            if seq+1 in seq_hash and seq_hash[seq] == seq_hash[seq+1]:
                duplicate_pairs.append([seq, seq+1])
        if len(duplicate_pairs) >= 2:
            reasons.append("repeated-segment-content")

        stalled = False
        live_ok = [s for s in ok if s.get("live")]
        if len(live_ok) >= 2:
            sequences = [s.get("media_sequence") for s in live_ok if s.get("media_sequence") is not None]
            tails = [s.get("tail_hash") for s in live_ok if s.get("tail_hash")]
            target = max([s.get("target_duration") or 0 for s in live_ok] or [0])
            if args.duration >= max(18, target*2) and sequences and len(set(sequences)) == 1 and tails and len(set(tails)) == 1:
                stalled = True
                reasons.append("live-playlist-did-not-advance")

        row = {
            **item,
            "samples":len(samples),
            "successful_samples":len(ok),
            "failed_samples":len(samples)-len(ok),
            "repeat_detected": any(x.startswith("repeated") for x in reasons),
            "stalled":stalled,
            "reasons":reasons,
            "duplicate_content_pairs":duplicate_pairs[:10],
            "media_sequence_range":[min(seq_hash) if seq_hash else None, max(seq_hash) if seq_hash else None],
            "errors":[s.get("error") for s in samples if s.get("error")][:5],
            "history":samples,
        }
        results.append(row)
        if row["repeat_detected"]: repeat_channels.append(item["channel_name"])
        if stalled: stalled_channels.append(item["channel_name"])
        if not ok: probe_error_channels.append(item["channel_name"])

    payload = {
        "tested_at":time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "preview_url":args.preview_url,
        "test_duration_seconds":args.duration,
        "interval_seconds":args.interval,
        "rounds":rounds,
        "channels_tested":len(items),
        "summary":{
            "repeat_detected":len(repeat_channels),
            "stalled":len(stalled_channels),
            "no_successful_probe":len(probe_error_channels),
            "clean":sum(1 for r in results if not r["repeat_detected"] and not r["stalled"] and r["successful_samples"]>0),
        },
        "repeat_channels":repeat_channels,
        "stalled_channels":stalled_channels,
        "no_successful_probe_channels":probe_error_channels,
        "results":results,
    }
    with open(args.output,"w",encoding="utf-8") as f:
        json.dump(payload,f,indent=2)
    print(json.dumps({k:v for k,v in payload.items() if k not in {"results"}}, indent=2))
    if repeat_channels or stalled_channels:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
