#!/usr/bin/env python3
import json, re, subprocess, time

UA_IOS="Mozilla/5.0 (iPhone; CPU iPhone OS 17_6_0 like Mac OS X) AppleWebKit/605.2.10 (KHTML, like Gecko) Version/17.6.0 Mobile/16F152 Safari/605.2"
DADDY_HEADERS={"Referer":"https://ilovetoplay.xyz/","Origin":"https://ilovetoplay.xyz","User-Agent":UA_IOS}

CANDIDATES=[
 {"channel":"CBS Sports Network","tvg_id":"CBSSportsNetwork.us","label":"MoveOnJoy 212.102","url":"http://212.102.60.231/CBS_SPORTS_NETWORK/index.m3u8"},
 {"channel":"CBS Sports Network","tvg_id":"CBSSportsNetwork.us","label":"DaddyLive premium308","url":"https://xyzdddd.mizhls.ru/lb/premium308/index.m3u8","headers":DADDY_HEADERS},
 {"channel":"Discovery Channel","tvg_id":"DiscoveryChannel.us","label":"MoveOnJoy 212.102","url":"http://212.102.60.231/Discovery_Channel/index.m3u8"},
 {"channel":"Discovery Channel","tvg_id":"DiscoveryChannel.us","label":"DaddyLive premium313","url":"https://xyzdddd.mizhls.ru/lb/premium313/index.m3u8","headers":DADDY_HEADERS},
 {"channel":"Investigation Discovery","tvg_id":"InvestigationDiscovery.us","label":"MoveOnJoy 212.102","url":"http://212.102.60.231/INVESTIGATION_DISCOVERY/index.m3u8"},
 {"channel":"Investigation Discovery","tvg_id":"InvestigationDiscovery.us","label":"DaddyLive premium324","url":"https://xyzdddd.mizhls.ru/lb/premium324/index.m3u8","headers":DADDY_HEADERS},
 {"channel":"TLC","tvg_id":"TLC.us","label":"Nexgen streamer1","url":"https://streamer1.nexgen.bz/TLC/index.m3u8"},
 {"channel":"TLC","tvg_id":"TLC.us","label":"TV247 fbcdntv","url":"https://ft.fbcdntv247.cfd/memfs/5281d7f6-3ffb-4b38-b273-f1bad18ddcbb_output_0.m3u8"},
 {"channel":"TLC","tvg_id":"TLC.us","label":"DaddyLive premium337","url":"https://xyzdddd.mizhls.ru/lb/premium337/index.m3u8","headers":DADDY_HEADERS},
 {"channel":"Smithsonian Channel","tvg_id":"SmithsonianChannel.us","label":"MoveOnJoy fl31","url":"https://fl31.moveonjoy.com/SMITHSONIAN_CHANNEL/index.m3u8"},
 {"channel":"Smithsonian Channel","tvg_id":"SmithsonianChannel.us","label":"MoveOnJoy fl7","url":"https://fl7.moveonjoy.com/SMITHSONIAN_CHANNEL/index.m3u8"},
 {"channel":"SundanceTV","tvg_id":"SundanceTV.us","label":"MoveOnJoy fl1","url":"https://fl1.moveonjoy.com/SUNDANCE/index.m3u8"},
 {"channel":"SundanceTV","tvg_id":"SundanceTV.us","label":"DaddyLive premium658","url":"https://xyzdddd.mizhls.ru/lb/premium658/index.m3u8","headers":DADDY_HEADERS},
 {"channel":"The Weather Channel","tvg_id":"WeatherChannel.us","label":"Akamai historical","url":"https://weather-lh.akamaihd.net/i/twc_1@92006/master.m3u8"},
 {"channel":"The Weather Channel","tvg_id":"WeatherChannel.us","label":"DaddyLive premium394","url":"https://xyzdddd.mizhls.ru/lb/premium394/index.m3u8","headers":DADDY_HEADERS},
 {"channel":"FX Movie Channel","tvg_id":"FXMovieChannel.us","label":"MoveOnJoy fl1","url":"https://fl1.moveonjoy.com/FX_MOVIE/index.m3u8"},
 {"channel":"FX Movie Channel","tvg_id":"FXMovieChannel.us","label":"DaddyLive premium381","url":"https://xyzdddd.mizhls.ru/lb/premium381/index.m3u8","headers":DADDY_HEADERS},
 {"channel":"FX Movie Channel","tvg_id":"FXMovieChannel.us","label":"TheTVApp v1","url":"https://v1.thetvapp.to/hls/FXMovieChannel/index.m3u8"},
 {"channel":"FX Movie Channel","tvg_id":"FXMovieChannel.us","label":"Damitv","url":"https://messi.damitv.st/papi/ts2/fxm-usa.m3u8","headers":{"User-Agent":"Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"}},
 {"channel":"FXX","tvg_id":"FXX.us","label":"MoveOnJoy fl2","url":"http://fl2.moveonjoy.com/FXX/index.m3u8"},
 {"channel":"Fox Sports 2","tvg_id":"FoxSports2.us","label":"MoveOnJoy fl2","url":"http://fl2.moveonjoy.com/FOX_Sports_2/index.m3u8"},
 {"channel":"MLB Network","tvg_id":"MLBNetwork.us","label":"Nexgen tx2","url":"https://tx2.nexgen.bz/MLB/index.m3u8"},
 {"channel":"MLB Network","tvg_id":"MLBNetwork.us","label":"MoveOnJoy fl7","url":"https://fl7.moveonjoy.com/MLB_NETWORK/index.m3u8"},
 {"channel":"MLB Network","tvg_id":"MLBNetwork.us","label":"DaddyLive premium399","url":"https://xyzdddd.mizhls.ru/lb/premium399/index.m3u8","headers":DADDY_HEADERS},
 {"channel":"NBC Sports Philadelphia","tvg_id":"NBCSportsPhiladelphia.us","label":"Damitv","url":"https://messi.damitv.st/papi/ts/nbc-sports-philly/playlist.m3u8"},
 {"channel":"NBC Sports Philadelphia","tvg_id":"NBCSportsPhiladelphia.us","label":"DaddyLive premium777","url":"https://xyzdddd.mizhls.ru/lb/premium777/index.m3u8","headers":DADDY_HEADERS},
 {"channel":"HGTV","tvg_id":"HGTV.us","label":"DaddyLive premium382","url":"https://xyzdddd.mizhls.ru/lb/premium382/index.m3u8","headers":DADDY_HEADERS},
 {"channel":"HGTV","tvg_id":"HGTV.us","label":"AynaScope East","url":"https://tvsen7.aynascope.net/hgtv/index.m3u8"}
]

def hashes(text):
    out=[]
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith("#"): continue
        parts=[p.strip() for p in line.split(",")]
        if len(parts)>=6 and re.fullmatch(r"[0-9a-fA-F]{32}",parts[-1]):
            out.append(parts[-1].lower())
    return out

def repeat_clip(h,fps=2):
    for width in range(4,9):
        for start in range(0,len(h)-2*width+1):
            a=h[start:start+width]; b=h[start+width:start+2*width]
            if len(set(a))>=3 and a==b:
                return {"start_frame":start,"width_frames":width,"seconds":width/fps}
    return None

def one_attempt(item):
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-rw_timeout","10000000"]
    headers=item.get("headers") or {}
    ua=headers.get("User-Agent")
    if ua: cmd += ["-user_agent",ua]
    extra={k:v for k,v in headers.items() if k.lower()!="user-agent"}
    if extra:
        cmd += ["-headers","".join(f"{k}: {v}\\r\\n" for k,v in extra.items())]
    cmd += ["-i",item["url"],"-t","12","-map","0:v:0","-vf","fps=2,scale=160:-2","-an","-f","framemd5","-"]
    started=time.time()
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=22)
        h=hashes(p.stdout)
        rep=repeat_clip(h)
        return {
            "frames":len(h),
            "decoded_seconds":round(len(h)/2,1),
            "repeat":rep,
            "exit":p.returncode,
            "elapsed":round(time.time()-started,2),
            "stderr":p.stderr[-600:],
            "passed":len(h)>=20 and rep is None,
        }
    except subprocess.TimeoutExpired:
        return {"frames":0,"decoded_seconds":0.0,"repeat":None,"exit":None,"elapsed":round(time.time()-started,2),"stderr":"timeout","passed":False}

rows=[]
for item in CANDIDATES:
    attempts=[one_attempt(item),one_attempt(item)]
    passes=sum(1 for a in attempts if a["passed"])
    row={**item,"attempts":attempts,"passes":passes,"passed":passes>=1}
    rows.append(row)
    print(f"{item['channel']} | {item['label']} | passes={passes}/2 | frames={[a['frames'] for a in attempts]} | repeat={any(a['repeat'] for a in attempts)}",flush=True)

with open("recovery-candidate-sweep.json","w") as f:
    json.dump(rows,f,indent=2)
print("\nPASSING CANDIDATES")
for r in rows:
    if r["passed"]:
        print(f"{r['tvg_id']} | {r['label']} | {r['url']}")
