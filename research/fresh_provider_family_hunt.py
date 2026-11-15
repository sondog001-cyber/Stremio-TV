#!/usr/bin/env python3
"""Fresh provider-family hunt for exact US East and Philadelphia networks.

Research only. Excludes playlist clones, known failed origin families, login/
credential-style URLs, DRM/TVE feeds, and unrelated FAST local-news streams.
Only *new* candidate media origins are scheduled for FFmpeg. Output never
auto-verifies network identity or alters the production manifest.
"""
from __future__ import annotations
import concurrent.futures
from datetime import datetime, timezone
from collections import Counter,defaultdict
from pathlib import Path
from urllib.parse import urlsplit
import json
import re
import origin_aware_targeted_discovery as prior
import priority_12_source_sweep as old

SOURCES=[
 ("branden-independent-catalog","https://raw.githubusercontent.com/brandenp198483-collab/branden-tv/main/BrandenTV-USA.m3u","aggregator-review"),
 ("shovo-alt-repos","https://raw.githubusercontent.com/shovo127/IPTV-By-Shovo/main/streams/us.m3u","possible-iptv-org-mirror"),
 ("buddy-nexgen","https://raw.githubusercontent.com/BuddyChewChew/My-Streams/main/Archive/nexgen.m3u8","alternate-iptv-origin"),
 ("kilirushi-ota","https://raw.githubusercontent.com/kilirushi/iptv/main/us_localbtv.m3u","ota-feed-catalog"),
 ("scribbay-xumo","https://raw.githubusercontent.com/Scribbay/IPTV-Scraper/main/xumo_playlist.m3u","fast-only-not-full-station"),
 ("sajadtroy-us","https://raw.githubusercontent.com/SajadTroy/openstream/main/streams/us.m3u","possible-iptv-org-mirror"),
]
TARGETS={"Bravo.us","USANetwork.us","E.us","DisneyChannel.us",
         "WPVI.us","WCAU.us","KYW.us","WPHL.us","WPSG.us"}
LOCAL_ID_VARIANTS={"wpvidt1.us@sd":"WPVI.us","wcaudt1.us@sd":"WCAU.us",
                   "kywdt1.us@sd":"KYW.us","wphldt1.us@sd":"WPHL.us",
                   "wpsgdt1.us@sd":"WPSG.us"}
# Evidence-backed but not otherwise covered candidates.
SEEDS=[
 ("Bravo.us","independent-bravo-170","http://170.254.18.106/BRAVO/index.m3u8"),
 ("USANetwork.us","independent-usa-tier1","https://gpuserver5.tier1streams.com/USA_NETWORK/index.m3u8"),
 ("History.us","independent-history-84","http://84.17.50.102/history/index.m3u8"),
]
# Network identity must match EXACT tvg-id, never infer from "Philadelphia News".
# A local news-only stream is not interchangeable with a primary OTA broadcast.
LOCAL_NEWS_ONLY=re.compile(r"\b(?:news only|local news|breaking news|nbc 10 philadelphia news|fox local philadelphia)\b",re.I)
RESTRICTED_HOSTS={"v-pi.theus6tv.tk","v-pi.mybtv.net","23.237.104.106",
 "tvpass.org","thetvapp.to"}  # last two are indirect platform/player endpoints
SIGNATURES=[
 re.compile(r"/(?:live|movie|series)/[^/]+/[^/]+/\d+",re.I),
 re.compile(r"/api/stream/[^/]*@[^/]+/\d+/",re.I),
 re.compile(r"/play/[A-Za-z0-9_-]{24,}/",re.I),
]
def has_credential_shape(url):
 p=urlsplit(url)
 if p.username or p.password:return True
 return any(rx.search(p.path) for rx in SIGNATURES)
def candidate_rows(raw,label):
 # Do not infer a missing tvg-id from an informal network name.
 lines=raw.splitlines()
 pending=None; name=""
 for line in lines:
  line=line.strip()
  if line.startswith("#EXTINF"):
   id_match=re.search(r'tvg-id="([^"]+)"',line,re.I)
   name=line.rsplit(",",1)[-1] if "," in line else ""
   pending=(old.clean_id(id_match.group(1)) or LOCAL_ID_VARIANTS.get(id_match.group(1).lower())) if id_match else None
  elif pending in TARGETS and line.startswith(("http://","https://")):
   url=line
   yield {"identity":pending,"url":url,"playlist":label,"channel_label":name}
   pending=None
def novel_candidates(rows):
 baseline=prior.SEEDS+[(identity,label,url) for identity,label,url in old.SEEDS if identity in TARGETS]
 legacy_keys={(identity,prior.media_key(url)) for identity,_,url in baseline}
 kept={};rejections=[];provenance=defaultdict(list)
 for row in rows:
  identity,url=row["identity"],row["url"]
  if identity not in TARGETS:continue
  p=urlsplit(url)
  reason=None
  if LOCAL_NEWS_ONLY.search(row.get("channel_label","")):reason="local-news-not-full-affiliate"
  elif has_credential_shape(url):reason="credentials-or-opaque-account-url"
  elif (p.hostname or "").lower() in RESTRICTED_HOSTS:reason="old-dead-or-indirect-origin"
  else:
   ok,why=prior.qualifies(row)
   if not ok:reason=why
  key=(identity,prior.media_key(url))
  if reason:
   rejections.append({"identity":identity,"source":row["playlist"],"reason":reason})
  elif key in legacy_keys:
   rejections.append({"identity":identity,"source":row["playlist"],"reason":"previously-tested-source"})
  else:
   provenance[key].append(row["playlist"])
   if key not in kept:kept[key]={k:v for k,v in row.items() if k!="channel_label"}
 # Extra host diversity and only genuinely novel media origins.
 ordered=sorted(kept.items(),key=lambda kv:(kv[1]["identity"],-len(provenance[kv[0]]),prior.origin_key(kv[1]["url"])))
 distinct=[];deferred=[];seen=defaultdict(set)
 for key,row in ordered:
  host=prior.origin_key(row["url"])
  if host in seen[row["identity"]]:reason="same-host-as-selected"
  elif len(seen[row["identity"]])>=4:reason="per-channel-host-cap"
  else:reason=""
  if reason:
   deferred.append({"identity":row["identity"],"origin":host,"reason":reason})
  else:
   seen[row["identity"]].add(host)
   distinct.append({**row,"origin":host,"provenance":sorted(set(provenance[key]))})
 return distinct,rejections,deferred
def main():
 records=[];errors={};family_stats=[]
 for label,url,family in SOURCES:
  raw,err=old.get_playlist(url)
  if err:
   errors[label]=err
   continue
  rows=list(candidate_rows(raw,label))
  records.extend(rows)
  family_stats.append({"source":label,"family":family,"parsed_exact_matches":len(rows)})
 # Evidence backed direct-host seeds, after other identical URLs are deduplicated.
 records.extend({"identity":i,"url":url,"playlist":label,"channel_label":""}
   for i,label,url in SEEDS if i in TARGETS)
 novel,rejections,deferred=novel_candidates(records)
 # Do not treat same provider across several domains as independent operators.
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  out=list(pool.map(lambda r:{**r,"probe":old.test({
       "identity":r["identity"],"url":r["url"],
       "playlist":",".join(r["provenance"])})},novel))
 results={
  "timestamp":datetime.now(timezone.utc).isoformat(),"research_only":True,
  "provider_catalogs":family_stats,"source_errors":errors,
  "raw_matched":len(records),"new_distinct_origins_tested":len(out),
  "rejection_counts":dict(Counter(x["reason"] for x in rejections)),
  "deferred":deferred,
  "media_qualified":[{"identity":r["identity"],"origin":r["origin"],
    "provenance":r["provenance"]} for r in out if r["probe"]["media_pass"]],
  "tested":out,"identity_verified":False,
  "warnings":["Do not auto-promote sources.","Indirect, protected or login-dependent feeds excluded.",
    "Philadelphia news-only stations are not full OTA affiliates.",
    "Source hosts can share an operator; host diversity alone is not provider independence."]
 }
 path=Path("research/diagnostics/fresh-provider-family-hunt.json")
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(results,indent=2)+"\n")
 print("FRESH_FAMILY_SUMMARY",json.dumps({
  "families":family_stats,"catalog_errors":errors,
  "raw_matches":len(records),"novel_origins_tested":len(out),
  "rejected_reasons":results["rejection_counts"],
  "media_qualified":results["media_qualified"]},indent=2),flush=True)
if __name__=="__main__":main()
