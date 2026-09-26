#!/usr/bin/env python3
import json, subprocess, concurrent.futures, time
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
candidates=[["CBS Sports Network","TheTVApp","https://v2.thetvapp.to/hls/CBSSportsNetworkUSA/tracks-v1a1/mono.m3u8","https://thetvapp.to","https://thetvapp.to/"],["CBS Sports Network","DaddyLive","https://zekonew.newkso.ru/zeko/premium308/mono.m3u8","https://jxoxkplay.xyz","https://jxoxkplay.xyz/"],["Discovery Channel","TheTVApp","https://v8.thetvapp.to/hls/DiscoveryChannelEast/tracks-v1a1/mono.m3u8","https://thetvapp.to","https://thetvapp.to/"],["Discovery Channel","DaddyLive","https://zekonew.newkso.ru/zeko/premium313/mono.m3u8","https://jxoxkplay.xyz","https://jxoxkplay.xyz/"],["FX Movie Channel","TheTVApp","https://v18.thetvapp.to/hls/FXMovieChannel/tracks-v1a1/mono.m3u8","https://thetvapp.to","https://thetvapp.to/"],["FX Movie Channel","DaddyLive","https://zekonew.newkso.ru/zeko/premium381/mono.m3u8","https://jxoxkplay.xyz","https://jxoxkplay.xyz/"],["FXX","TheTVApp","https://v12.thetvapp.to/hls/FXXEast/tracks-v1a1/mono.m3u8","https://thetvapp.to","https://thetvapp.to/"],["FXX","DaddyLive","https://ddy6new.newkso.ru/ddy6/premium298/mono.m3u8","https://jxoxkplay.xyz","https://jxoxkplay.xyz/"],["Fox Sports 2","TheTVApp","https://v2.thetvapp.to/hls/FoxSports2/tracks-v1a1/mono.m3u8","https://thetvapp.to","https://thetvapp.to/"],["Fox Sports 2","DaddyLive","https://zekonew.newkso.ru/zeko/premium758/mono.m3u8","https://jxoxkplay.xyz","https://jxoxkplay.xyz/"],["Investigation Discovery","TheTVApp","https://v5.thetvapp.to/hls/InvestigationDiscoveryEast/tracks-v1a1/mono.m3u8","https://thetvapp.to","https://thetvapp.to/"],["Investigation Discovery","DaddyLive","https://windnew.newkso.ru/wind/premium324/mono.m3u8","https://jxoxkplay.xyz","https://jxoxkplay.xyz/"],["MLB Network","TheTVApp","https://v13.thetvapp.to/hls/MLBNetwork/tracks-v1a1/mono.m3u8","https://thetvapp.to","https://thetvapp.to/"],["MLB Network","DaddyLive","https://windnew.newkso.ru/wind/premium399/mono.m3u8","https://jxoxkplay.xyz","https://jxoxkplay.xyz/"],["NBC Sports Philadelphia","TheTVApp","https://v18.thetvapp.to/hls/nbc-sports-philadelphia/tracks-v1a1/mono.m3u8","https://thetvapp.to","https://thetvapp.to/"],["NBC Sports Philadelphia","DaddyLive","https://zekonew.newkso.ru/zeko/premium777/mono.m3u8","https://jxoxkplay.xyz","https://jxoxkplay.xyz/"],["Smithsonian Channel","DaddyLive","https://dokko1new.newkso.ru/dokko1/premium603/mono.m3u8","https://jxoxkplay.xyz","https://jxoxkplay.xyz/"],["SundanceTV","TheTVApp","https://v13.thetvapp.to/hls/SundanceTVEast/tracks-v1a1/mono.m3u8","https://thetvapp.to","https://thetvapp.to/"],["SundanceTV","DaddyLive","https://dokko1new.newkso.ru/dokko1/premium658/mono.m3u8","https://jxoxkplay.xyz","https://jxoxkplay.xyz/"],["TLC","TheTVApp","https://v8.thetvapp.to/hls/TLCEast/tracks-v1a1/mono.m3u8","https://thetvapp.to","https://thetvapp.to/"],["TLC","DaddyLive","https://windnew.newkso.ru/wind/premium337/mono.m3u8","https://jxoxkplay.xyz","https://jxoxkplay.xyz/"],["Weather Channel","TheTVApp","https://v16.thetvapp.to/hls/TheWeatherChannel/tracks-v1a1/mono.m3u8","https://thetvapp.to","https://thetvapp.to/"]]
def test(row):
    channel,label,url,origin,referer=row
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-user_agent",UA,
         "-headers",f"Origin: {origin}\r\nReferer: {referer}\r\n",
         "-rw_timeout","10000000","-i",url,"-t","15","-map","0:v:0",
         "-vf","fps=2,scale=160:-2","-an","-f","framemd5","-"]
    started=time.time()
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=28)
        hashes=[]
        for line in p.stdout.splitlines():
            if not line or line.startswith("#"): continue
            parts=[x.strip() for x in line.split(",")]
            if len(parts)>=6: hashes.append(parts[-1])
        repeat=False
        repeat_width=None
        for w in range(4,9):
            for i in range(0,len(hashes)-2*w+1):
                if hashes[i:i+w] == hashes[i+w:i+2*w]:
                    repeat=True; repeat_width=w; break
            if repeat: break
        return {"channel":channel,"label":label,"url":url,"frames":len(hashes),
                "decoded_seconds":round(len(hashes)/2,1),"repeat":repeat,
                "repeat_seconds":round((repeat_width or 0)/2,1),
                "exit":p.returncode,"elapsed":round(time.time()-started,2),
                "stderr":p.stderr[-500:],"passed":len(hashes)>=24 and not repeat}
    except subprocess.TimeoutExpired:
        return {"channel":channel,"label":label,"url":url,"frames":0,"decoded_seconds":0,
                "repeat":False,"exit":None,"elapsed":round(time.time()-started,2),
                "stderr":"timeout","passed":False}
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    rows=list(ex.map(test,candidates))
rows.sort(key=lambda x:(x["channel"],x["label"]))
print(json.dumps(rows,indent=2))
with open("priority-recovery-candidates.json","w") as f: json.dump(rows,f,indent=2)
