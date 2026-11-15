#!/usr/bin/env python3
"""Origin-aware, targeted source discovery; strictly research-only.

Improves the prior sweep by removing credential URLs, exact duplicate media URLs,
previously confirmed failed endpoints, and redundant playlist mirrors BEFORE
network probes. A host fingerprint is an *operator-risk* grouping, not proof
that two channels share video content. Do not promote by label alone.
"""
from __future__ import annotations
import concurrent.futures
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import priority_12_source_sweep as legacy

# Narrow run: the user requested smarter discovery for exactly these networks.
TARGETS={
    "Bravo.us","USANetwork.us","E.us","DisneyChannel.us",
    "WPVI.us","WCAU.us","KYW.us","WPHL.us","WPSG.us",
}
PLAYLISTS=legacy.PUBLIC_PLAYLISTS+[
    ("judy-usa-extra","https://raw.githubusercontent.com/judy-gotv/iptv/main/USA.m3u"),
    ("iptv-us-raw","https://raw.githubusercontent.com/iptv-org/iptv/master/streams/us.m3u"),
    ("visualblind-us","https://raw.githubusercontent.com/visualblind/jellyfin-stuff/master/iptv-livetv/us.m3u"),
    ("bryden-locals","https://raw.githubusercontent.com/BrydenIsNotSmart/moveonjoy-iptv-streams/main/Local-Stations.md"),
]
# Research leads from current public repositories; these MUST be independently
# decoded and reviewed for US-East / Philadelphia identity before use.
SEEDS=[
 ("Bravo.us","bravo-t1","https://gpuserver3.tier1streams.com/BRAVO/index.m3u8"),
 ("Bravo.us","bravo-170","http://170.254.18.106/BRAVO/index.m3u8"),
 ("Bravo.us","bravo-fl2","http://fl2.moveonjoy.com/BRAVO/index.m3u8"),
 ("USANetwork.us","usa-tier1","https://gpuserver5.tier1streams.com/USA_NETWORK/index.m3u8"),
 ("USANetwork.us","usa-143","http://143.244.60.30/Usa_Network/index.m3u8"),
 ("USANetwork.us","usa-fl2","http://fl2.moveonjoy.com/USA_Network/index.m3u8"),
 ("DisneyChannel.us","disney-tvpass","https://tvpass.org/live/DisneyChannelEast/hd"),
 ("DisneyChannel.us","disney-legacy","http://212.5.144.156/disney/index.m3u8"),
 ("E.us","e-moveonjoy-fl2","https://fl2.moveonjoy.com/E_ENTERTAINMENT_TELEVISION/index.m3u8"),
 ("E.us","e-tvnow","https://cache0.wonvt.st/live/15a0cd61f3w7um0229g5g/master.m3u8"),
 ("WPVI.us","wpvi-fl1","https://fl1.moveonjoy.com/PA_PHILADELPHIA_ABC/index.m3u8"),
 ("WCAU.us","wcau-fl1","https://fl1.moveonjoy.com/PA_PHILADELPHIA_NBC/index.m3u8"),
 ("KYW.us","kyw-fl1","https://fl1.moveonjoy.com/PA_PHILADELPHIA_CBS/index.m3u8"),
 ("WPVI.us","wpvi-fl41","http://fl41.moveonjoy.com/PA_PHILADELPHIA_ABC/index.m3u8"),
 ("WCAU.us","wcau-fl41","http://fl41.moveonjoy.com/PA_PHILADELPHIA_NBC/index.m3u8"),
 ("KYW.us","kyw-fl41","http://fl41.moveonjoy.com/PA_PHILADELPHIA_CBS/index.m3u8"),
]
# Historical 2026-10-14 source studies conclusively failed media on these
# exact endpoints or all paths on this one shared origin. Do not assume an
# intermittent source family (212.5.144.156) is permanently dead.
DEAD_ORIGINS={"23.237.104.106:8080"}
DEAD_URLS={
 "https://cache0.wonvt.st/live/15a0cd61f3w7um0229g5g/master.m3u8",
 "http://41.205.93.154/BRAVO/index.m3u8",
 "http://190.197.41.183/USA_NETWORK/index.m3u8",
 "http://200.32.231.178/USA_NETWORK/index.m3u8",
}
# Transient hosts deliberately lower-ranked, not permanently blacklisted.
VOLATILE_ORIGINS={"212.5.144.156","212.5.144.156:8080"}
DROP_QUERY={"token","jwt","e","expires","exp","signature","sig","hdnts","hmac"}

def media_key(url):
    """Normalize scheme/case/default port and ephemeral tokens for dedup ONLY."""
    p=urlsplit(url)
    port=p.port
    hostname=(p.hostname or "").lower().rstrip(".")
    if port in (80,443) and ((port==80 and p.scheme=="http") or (port==443 and p.scheme=="https")):
        port=None
    host=hostname+(":"+str(port) if port else "")
    qs=sorted((k.lower(),v) for k,v in parse_qsl(p.query,keep_blank_values=True)
              if k.lower() not in DROP_QUERY)
    return (p.scheme.lower(),host,re.sub(r"/+","/",p.path).rstrip("/").lower(),tuple(qs))

def origin_key(url):
    """Host:port, deliberately ignores unrelated branding / playlist copies."""
    p=urlsplit(url)
    return (p.hostname or "").lower().rstrip(".")+(":"+str(p.port) if p.port else "")

def qualifies(row):
    url=row["url"]
    ok,why=legacy.permitted_url(url)
    if not ok:return False,why
    origin=origin_key(url)
    if origin in DEAD_ORIGINS:return False,"historic-shared-host-unreachable"
    if url in DEAD_URLS:return False,"historic-exact-url-failed"
    return True,""

def select(rows):
    """Prefer new distinct origins; preserve references and group shared risks."""
    rejected=[]
    unique={}
    for row in rows:
        if row["identity"] not in TARGETS:continue
        ok,reason=qualifies(row)
        if not ok:
            rejected.append({"identity":row["identity"],"source":row["playlist"],
                             "reason":reason,"origin":origin_key(row["url"])})
            continue
        key=(row["identity"],media_key(row["url"]))
        if key not in unique:
            unique[key]={"identity":row["identity"],"url":row["url"],"origin":origin_key(row["url"]),
              "sources":[row["playlist"]]}
        else:
            if row["playlist"] not in unique[key]["sources"]:
                unique[key]["sources"].append(row["playlist"])
    buckets=defaultdict(list)
    for item in unique.values():buckets[item["identity"]].append(item)
    selected=[]
    deprioritized=[]
    for ident in sorted(TARGETS):
        items=buckets.get(ident,[])
        items.sort(key=lambda r:(
          r["origin"] in VOLATILE_ORIGINS,
          r["origin"].startswith("fl") and "moveonjoy" in r["origin"],
          -len(r["sources"]),r["origin"],r["url"]))
        origins=set()
        for item in items:
            if item["origin"] in origins:
                deprioritized.append({**item,"reason":"same-media-origin-as-selected"})
                continue
            if len(origins)>=5:
                deprioritized.append({**item,"reason":"per-channel-origin-cap"})
                continue
            origins.add(item["origin"])
            selected.append(item)
    # Additional system-wide fairness: max three media paths from same origin.
    # These are still independent streams, but a shared outage is correlated.
    tested=[]
    origin_counts=Counter()
    for item in selected:
        if origin_counts[item["origin"]]>=3:
            deprioritized.append({**item,"reason":"system-wide-shared-origin-cap"})
            continue
        origin_counts[item["origin"]]+=1
        tested.append(item)
    return tested,unique,rejected,deprioritized

def extract_markdown_locations(markdown):
    """Explicit city and station names; no generic national affiliates."""
    city_id={"Philadelphia ABC":"WPVI.us","Philadelphia NBC":"WCAU.us",
             "Philadelphia CBS":"KYW.us","Philadelphia CW":"WPHL.us",
             "Philadelphia MyNetworkTV":"WPSG.us"}
    out=[]
    for city,identity in city_id.items():
        for match in re.finditer(r"\b"+re.escape(city)+r"\b.*?\((https?://[^)\s]+)\)",markdown,re.I):
            out.append({"identity":identity,"url":match.group(1),"playlist":"bryden-locals"})
    return out

def main():
    rows=[]
    source_errors={}
    for label,url in PLAYLISTS:
        raw,error=legacy.get_playlist(url)
        if error:
            source_errors[label]=error
            continue
        if label=="bryden-locals":
            rows.extend(extract_markdown_locations(raw))
        else:
            rows.extend(legacy.parse_m3u(raw,label))
    rows.extend({"identity":identity,"url":url,"playlist":label} for identity,label,url in SEEDS)
    # Previous sweep seeds provide low-priority candidates, not source promotions.
    rows.extend({"identity":i,"url":url,"playlist":label} for i,label,url in legacy.SEEDS if i in TARGETS)
    tested,unique,rejected,deprioritized=select(rows)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda r: {**r,"media":legacy.test({**r,"playlist":",".join(r["sources"])})},tested))
    risk_groups=defaultdict(list)
    for r in results:risk_groups[r["origin"]].append(r["identity"])
    report={
        "utc":datetime.now(timezone.utc).isoformat(),
        "scope":"research-only exact US East/Philadelphia origin-aware discovery",
        "targets":sorted(TARGETS),
        "raw_matches":len(rows),"unique_media_keys":len(unique),
        "sources_checked":len(PLAYLISTS),"source_errors":source_errors,
        "blocked":rejected,"deferred":deprioritized,
        "tested_count":len(results),
        "media_pass_count":sum(r["media"]["media_pass"] for r in results),
        "full_media_passes":[{"identity":r["identity"],"origin":r["origin"],"url":r["url"]}
            for r in results if r["media"]["media_pass"]],
        "shared_origin_risk_groups":{host:sorted(set(ids)) for host,ids in risk_groups.items() if len(set(ids))>1},
        "results":results,
        "identity_confirmed_count":0,
        "warning":"Decoder pass != US East or station identity; never auto-promote candidates."
    }
    path=Path("research/diagnostics/origin-aware-targeted-discovery.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+"\n")
    print("ORIGIN_AWARE_SUMMARY",json.dumps({
       "raw_matches":report["raw_matches"],"unique_media_keys":report["unique_media_keys"],
       "blocked":len(rejected),"deferred":len(deprioritized),
       "tested":report["tested_count"],"passes":report["full_media_passes"],
       "source_errors":source_errors},indent=2),flush=True)

if __name__=="__main__":main()
