#!/usr/bin/env python3
"""Non-intrusive audit of official, public TV watch page mechanisms.

This tool does NOT sign in, trigger paywall/TVE auth flows, resolve DRM, scrape
protected APIs, or interpret local-news-only streams as full broadcast feeds.
Read-only HTTP GET of published watch pages, limited to one response/page;
no headless browser, no subresource traversal, no playback promotion.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime,timezone
from html import unescape
import hashlib
import json
from pathlib import Path
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit

WATCH_PAGES=[
 {"identity":"Bravo.us","label":"Bravo official TV player","url":"https://www.bravotv.com/live","policy":"tve_auth_required"},
 {"identity":"USANetwork.us","label":"USA official player","url":"https://www.usanetwork.com/live","policy":"tve_auth_required"},
 {"identity":"E.us","label":"E! official watch player","url":"https://www.eonline.com/watch/live","policy":"tve_auth_required"},
 {"identity":"WPVI.us","label":"6abc Philly 24/7 Watch","url":"https://6abc.com/watch/video/","policy":"news_or_24_7_not_full_affiliate"},
 {"identity":"WPVI.us","label":"ABC WPVI Watch Live guide","url":"https://abc.com/watch-live/ceb5fbbb-c5db-4470-8f10-c1d98097bebd","policy":"needs_exact_programming_check"},
 {"identity":"WCAU.us","label":"NBC10 Philadelphia watch 24/7","url":"https://www.nbcphiladelphia.com/watch/","policy":"news_only_not_full_affiliate"},
 {"identity":"KYW.us","label":"CBS News Philadelphia","url":"https://www.cbsnews.com/philadelphia/live/","policy":"news_only_not_full_affiliate"},
 {"identity":"WPHL.us","label":"PHL17 official homepage","url":"https://phl17.com/","policy":"unknown_no_replacement"},
 {"identity":"WPSG.us","label":"Philly57 TV guide on CBS","url":"https://www.cbsnews.com/philadelphia/","policy":"guide_not_player"},
]
NBC_TVE="https://help.nbc.com/hc/en-us/articles/360033854593-TV-Provider-vs-Internet-Provider"
PROVENANCE={
 "NBCUniversal TVE":"https://github.com/kineticman/FastChannels",
 "NBCUniversal extraction reference":"https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/nbc.py",
 "USA TV Next independent catalogs":"https://github.com/yowmamasita/usa-tv-next",
}
RX_MEDIA=re.compile(r'https?:(?:\\?/){2}[^"\'\s<>]{5,500}?\.(?:m3u8|mpd)(?:\?[^"\'\s<>]{0,150})?',re.I)
RX_RELATIVE=re.compile(r'(?<![A-Za-z0-9])[^\s"\'<>]{2,150}\.(?:m3u8|mpd)(?:\?[^"\'<>]*)?',re.I)
RX_FLAGS={
 "tve":re.compile(r"tv.?provider|adobe.?pass|mvpd|login.?provider|link.?provider|sign.?in.?with",re.I),
 "drm":re.compile(r"widevine|playready|fairplay|drm|licenseServer|license_url",re.I),
 "hls_word":re.compile(r"m3u8|hls|streaming",re.I),
 "news_only":re.compile(r"24/7 (?:news|live)|local news|watch live news|breaking news|action news",re.I),
}
def redact(url):
 p=urlsplit(unescape(url).replace("\\/","/"))
 # Never emit token or credential-like query fragments into diagnostics.
 return (p.scheme+"://"+(p.hostname or "")+((":"+str(p.port)) if p.port else "")
         +p.path[:150]).rstrip("/")
def safe_fetch(url):
 req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; StremioTVResearch/1.0)","Accept":"text/html"})
 try:
  with urllib.request.urlopen(req,timeout=17) as response:
   content_type=response.headers.get("Content-Type","")
   final=response.geturl()
   data=response.read(250_000).decode("utf-8","replace")
   return {"ok":True,"http":response.status,"content_type":content_type,
           "redirected_host":urlsplit(final).hostname,
           "body":data},None
 except Exception as e:return None,str(e)[:160]
def inspect(row):
 response,error=safe_fetch(row["url"])
 result={k:v for k,v in row.items() if k!="url"}
 result["watch_url"]=row["url"]
 result["published_media_urls"]=[]
 result["promotable_to_full_network"]=False
 result["exact_live_programme_verified"]=False
 if error:
  result["access"]="unreachable_or_blocked_from_runner"
  result["error"]=error
  return result
 body=response["body"]
 result["http"]=response["http"]
 result["content_type"]=response["content_type"]
 result["redirected_host"]=response["redirected_host"]
 result["signals"]={k:bool(rx.search(body)) for k,rx in RX_FLAGS.items()}
 url_matches=list(RX_MEDIA.finditer(body))
 candidates={}
 for m in url_matches:
  raw=unescape(m.group(0)).replace("\\/","/")
  u=urlsplit(raw)
  if (u.hostname or "").endswith(("bravotv.com","usanetwork.com","eonline.com","6abc.com",
     "nbcphiladelphia.com","cbsnews.com")):
   # Same-site URLs are not automatically confirmed as full live-TV media.
   pass
  canonical=redact(raw)
  candidates[canonical]={"host":u.hostname,"path":u.path[:150],
   "protocol":"HLS" if ".m3u8" in u.path else "DASH",
   "has_signed_or_tokenized_query":bool(u.query)}
 result["embedded_media_refs"]=list(candidates.values())[:15]
 result["embedded_media_count"]=len(candidates)
 # An HTML signal is a lead ONLY, not verified playback. This classification
 # prevents false-positive "recoveries" from autoplay promos and local news.
 if row["policy"]=="tve_auth_required":result["access"]="TVE_subscriber_login_required"
 elif row["policy"] in ("news_only_not_full_affiliate","news_or_24_7_not_full_affiliate"):
  result["access"]="public_news_or_24_7_not_full_affiliate"
 elif row["policy"]=="guide_not_player":result["access"]="station_guide_not_full_player"
 else:result["access"]="unverified_full_station_player"
 return result
def main():
 results=[inspect(row) for row in WATCH_PAGES]
 path=Path("research/diagnostics/live-player-mechanisms.json")
 path.parent.mkdir(parents=True,exist_ok=True)
 report={"utc":datetime.now(timezone.utc).isoformat(),"read_only":True,
  "audit_scope":"Official public watch HTML, single request per URL, no auth or playback extraction",
  "results":results,"related_implementations":PROVENANCE,
  "verified_full_network_count":0,"safe_to_promote_count":0,
  "cautions":["Do not use playback URLs requiring credentials, TVE auth, or DRM bypass.",
   "Free local-news/24-7 channels are not the corresponding full affiliate.",
   "Any embedded HLS reference still needs independent identity and original full FFmpeg QA.",
   "No manifest, channel identity, logo or production changes."]}
 path.write_text(json.dumps(report,indent=2)+"\n")
 for r in results:
  print(r["identity"],r["label"],r["access"],
      "embedded",r.get("embedded_media_count",0),"flags",r.get("signals",{}),flush=True)
 print("AUDIT_SUMMARY",json.dumps({"pages":len(results),"reachable":sum("http" in r for r in results),
 "access_types":dict(Counter(r["access"] for r in results)),
 "embedded_media_refs":sum(r.get("embedded_media_count",0) for r in results),
 "verified_full_network_count":0},indent=2))
if __name__=="__main__":main()
