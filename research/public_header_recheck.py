#!/usr/bin/env python3
"""Compare two distinct publicly indexed CDN/gateway families with safe headers.

Read-only HLS preflight; no proxy/restream/DRM, no production changes. The two
gateway families are NOT asserted to be different broadcaster media origins.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
from research import fresh_origin_discovery as hls

SEEDS=(
    {"name":"nightah-daddylive","url":"https://raw.githubusercontent.com/nightah/daddylive/main/daddylive-channels.m3u8"},
    {"name":"bennschmidt-example","url":"https://raw.githubusercontent.com/bennschmidt/example-m3u/main/playlist.m3u8"},
)
# Explicit audited *legacy ID + name* pairs; exclude all other lookalikes.
IDENTITIES={
    ("bravo", "bravo"): "Bravo.us",
    ("bravo", "bravousa"): "Bravo.us",
    ("bravousaeasternfeed", "bravousa"): "Bravo.us",
    ("cbssportsnetwork", "cbssportsnetworkcbssn"): "CBSSportsNetwork.us",
    ("cbssportsnetworkus", "cbssportsnetworkcbssn"): "CBSSportsNetwork.us",
    ("espnews", "espnews"): "ESPNews.us",
    ("espnnews", "espnews"): "ESPNews.us",
    ("nicktoons", "nicktoons"): "Nicktoons.us",
    ("nicktoonseast", "nicktoons"): "Nicktoons.us",
}
FOCUS={"Bravo.us","CBSSportsNetwork.us","ESPNews.us","Nicktoons.us"}
CAP_TOTAL=8

def eligible(entries, source):
    for row in entries:
        if row.get("invalid") or not hls.valid_public_url(row.get("url","")):
            continue
        id_key=hls.canonical(row.get("tvg_id",""))
        name_key=hls.canonical(row.get("name",""))
        target=IDENTITIES.get((id_key,name_key))
        if target not in FOCUS:
            continue
        url=row["url"]
        host=hls.host(url)
        if not host:
            continue
        yield {"tvg_id":target,"source":source,"url":url,"host":host,
               "gateway_family":hls.host_family(host),
               "public_headers":row.get("public_headers") or {}}

def collect_candidates(seeds):
    seen=set()
    candidates=[]
    source_stats=[]
    for source in seeds:
        try:
            data=hls.fetch(source["url"], hls.MAX_PLAYLIST)
            parsed=list(hls.parse_m3u(data["data"].decode("utf-8-sig","replace")))
            matching=list(eligible(parsed,source["name"]))
            source_stats.append({"name":source["name"],"matched":len(matching),"total":len(parsed)})
        except Exception as err:
            source_stats.append({"name":source["name"],"status":"source-unavailable",
                                 "error_type":type(err).__name__})
            continue
        for candidate in matching:
            # No repeated channel+gateway-family probes from copied mirror lists.
            key=(candidate["tvg_id"],candidate["gateway_family"])
            if key in seen or len(candidates)>=CAP_TOTAL:
                continue
            seen.add(key)
            candidates.append(candidate)
    return candidates,source_stats

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,default=Path("research-results/public-header-recheck.json"))
    args=ap.parse_args()
    candidates,sources=collect_candidates(SEEDS)
    results=[]
    for c in candidates:
        detail=hls.probe_manifest(c["url"],headers=c["public_headers"])
        results.append({"channel":c["tvg_id"],"gateway_family":c["gateway_family"],
                        "entry_host":c["host"],"playlist_source":c["source"],
                        "public_header_names":sorted(c["public_headers"]),
                        "stage":detail.get("stage"),"http_status":detail.get("http_status"),
                        "media_host":detail.get("media_host"),
                        "decoder_passed":False,"exact_content_identity_verified":False,
                        "broadcaster_origin_verified":False,"authorized_public_playback_verified":False,
                        "promotion":False})
    report={"as_of":dt.datetime.now(dt.timezone.utc).isoformat(),
            "source_stats":sources,"distinct_channel_gateway_pairs":len(results),
            "preflight_progressing":sum(x["stage"]=="progressing-hls-readable-not-decoded" for x in results),
            "candidates":results,"promotions":0,
            "caution":"Different CDN/gateway roots do not prove independent original media origins. A successful manifest preflight is not permission, identity, or decoded playback."}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
