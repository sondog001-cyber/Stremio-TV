#!/usr/bin/env python3
"""At least five minutes of active public GitHub playlist/source-family research."""
import argparse,json,time,urllib.request,urllib.error
from pathlib import Path
from urllib.parse import urlsplit
import priority_12_source_sweep as existing
import origin_aware_targeted_discovery as origin

FAMILIES=[
 ["iptv-org/iptv/master/streams/us.m3u","judy-gotv/iptv/main/Moveonjoy.m3u"],
 ["brandenp198483-collab/branden-tv/main/BrandenTV-USA.m3u","shovo127/IPTV-By-Shovo/main/streams/us.m3u"],
 ["SajadTroy/openstream/main/streams/us.m3u","visualblind/jellyfin-stuff/master/iptv-livetv/us.m3u"],
 ["BuddyChewChew/My-Streams/main/Archive/nexgen.m3u8","BuddyChewChew/My-Streams/main/Archive/Backup.m3u"],
 ["spookyhost1/yarr-stremio/main/src/iptv/m3u-sources/us_moveonjoy.m3u","spookyhost1/yarr-stremio/main/src/iptv/m3u-sources/us_tvpass.m3u"],
 ["AdeelWajid/iptv_validated_list/main/playlists/categories/series.m3u","TonyBlanco/iptv/main/streams/us.m3u"],
]
TARGET={"Bravo.us","USANetwork.us","E.us","DisneyChannel.us","WPVI.us","WCAU.us","KYW.us","WPHL.us","WPSG.us","FoodNetwork.us","BET.us","CMT.us","CookingChannel.us","CBSSportsNetwork.us","ESPNews.us"}
def source(url):
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"StremioTV-Research/1.0"}),timeout=22) as r:return r.read(1500000).decode("utf-8","replace")
 except Exception:return ""
def run(index):
 results=[];unique=set();hosts=set();tested=[]
 for path in FAMILIES[index]:
  url="https://raw.githubusercontent.com/"+path
  text=source(url)
  for r in existing.parse_m3u(text,path):
   if r["identity"] not in TARGET:continue
   ok,reason=origin.qualifies(r)
   if not ok:continue
   key=(r["identity"],origin.media_key(r["url"]))
   if key in unique:continue
   unique.add(key)
   h=(r["identity"],origin.origin_key(r["url"]))
   if h in hosts:continue
   hosts.add(h)
   results.append({"identity":r["identity"],"provider":h[1],"source":path})
   if len(tested)<8:
    checked=existing.ffmpeg_check(r["url"],12)
    tested.append({"identity":r["identity"],"provider":h[1],"decoded":checked["passed"]})
 return {"round":index+1,"sources":FAMILIES[index],"new_origin_rows":results,"initial_media_tests":tested}
if __name__=="__main__":
 ap=argparse.ArgumentParser()
 ap.add_argument("--round",type=int,required=True)
 opts=ap.parse_args()
 if not 1<=opts.round<=6:raise SystemExit("round must be 1..6")
 r=run(opts.round-1)
 dest=Path("research/diagnostics/five-min-wide")
 dest.mkdir(parents=True,exist_ok=True)
 (dest/("round-"+str(opts.round)+".json")).write_text(json.dumps(r,indent=2)+"\n")
 print("DISCOVERY_ROUND",json.dumps({"round":opts.round,"new_origins":len(r["new_origin_rows"]),"media_tested":len(r["initial_media_tests"]),"initial_decoded":sum(x["decoded"] for x in r["initial_media_tests"])}),flush=True)
