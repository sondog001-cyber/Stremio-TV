#!/usr/bin/env python3
import json, subprocess, time, concurrent.futures

candidates = [
    {"channel":"CBS Sports Network","url":"https://arquerido-piggy.hf.space/watch/aHR0cHM6Ly96ZWtvbmV3Lm5ld2tzby5ydS96ZWtvL3ByZW1pdW0zMDgvbW9uby5tM3U4.m3u8"},
    {"channel":"Discovery Channel","url":"https://arquerido-piggy.hf.space/watch/aHR0cHM6Ly96ZWtvbmV3Lm5ld2tzby5ydS96ZWtvL3ByZW1pdW0zMTMvbW9uby5tM3U4.m3u8"},
    {"channel":"FXX","url":"https://arquerido-piggy.hf.space/watch/aHR0cHM6Ly9kZHk2bmV3Lm5ld2tzby5ydS9kZHk2L3ByZW1pdW0yOTgvbW9uby5tM3U4.m3u8"},
    {"channel":"Fox Sports 2","url":"https://arquerido-piggy.hf.space/watch/aHR0cHM6Ly96ZWtvbmV3Lm5ld2tzby5ydS96ZWtvL3ByZW1pdW03NTgvbW9uby5tM3U4.m3u8"},
    {"channel":"HGTV","url":"https://arquerido-piggy.hf.space/watch/aHR0cHM6Ly96ZWtvbmV3Lm5ld2tzby5ydS96ZWtvL3ByZW1pdW0zODIvbW9uby5tM3U4.m3u8"},
    {"channel":"Investigation Discovery","url":"https://arquerido-piggy.hf.space/watch/aHR0cHM6Ly93aW5kbmV3Lm5ld2tzby5ydS93aW5kL3ByZW1pdW0zMjQvbW9uby5tM3U4.m3u8"},
    {"channel":"MLB Network","url":"https://arquerido-piggy.hf.space/watch/aHR0cHM6Ly93aW5kbmV3Lm5ld2tzby5ydS93aW5kL3ByZW1pdW0zOTkvbW9uby5tM3U4.m3u8"},
    {"channel":"Magnolia Network","url":"https://arquerido-piggy.hf.space/watch/aHR0cHM6Ly9kZHk2bmV3Lm5ld2tzby5ydS9kZHk2L3ByZW1pdW0yOTkvbW9uby5tM3U4.m3u8"},
    {"channel":"NBC Sports Philadelphia","url":"https://arquerido-piggy.hf.space/watch/aHR0cHM6Ly96ZWtvbmV3Lm5ld2tzby5ydS96ZWtvL3ByZW1pdW03NzcvbW9uby5tM3U4.m3u8"},
    {"channel":"OWN","url":"https://arquerido-piggy.hf.space/watch/aHR0cHM6Ly93aW5kbmV3Lm5ld2tzby5ydS93aW5kL3ByZW1pdW0zMzEvbW9uby5tM3U4.m3u8"},
    {"channel":"Reelz","url":"https://arquerido-piggy.hf.space/watch/aHR0cHM6Ly96ZWtvbmV3Lm5ld2tzby5ydS96ZWtvL3ByZW1pdW0yOTMvbW9uby5tM3U4.m3u8"},
    {"channel":"Smithsonian Channel","url":"https://arquerido-piggy.hf.space/watch/aHR0cHM6Ly9kb2trbzFuZXcubmV3a3NvLnJ1L2Rva2tvMS9wcmVtaXVtNjAzL21vbm8ubTN1OA==.m3u8"},
    {"channel":"SundanceTV","url":"https://arquerido-piggy.hf.space/watch/aHR0cHM6Ly9kb2trbzFuZXcubmV3a3NvLnJ1L2Rva2tvMS9wcmVtaXVtNjU4L21vbm8ubTN1OA==.m3u8"},
    {"channel":"TLC","url":"https://arquerido-piggy.hf.space/watch/aHR0cHM6Ly93aW5kbmV3Lm5ld2tzby5ydS93aW5kL3ByZW1pdW0zMzcvbW9uby5tM3U4.m3u8"},
    {"channel":"Weather Channel","url":"https://arquerido-piggy.hf.space/watch/aHR0cHM6Ly96ZWtvbmV3Lm5ld2tzby5ydS96ZWtvL3ByZW1pdW0zOTQvbW9uby5tM3U4.m3u8"},
    {"channel":"Travel Channel","url":"https://arquerido-piggy.hf.space/watch/aHR0cHM6Ly93aW5kbmV3Lm5ld2tzby5ydS93aW5kL3ByZW1pdW0zNDAvbW9uby5tM3U4.m3u8"},
]
def check(item):
    started=time.time()
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-rw_timeout","12000000","-i",item["url"],"-t","12","-map","0:v:0","-vf","fps=2,scale=160:-2","-an","-f","framemd5","-"]
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=28)
        frames=sum(1 for line in p.stdout.splitlines() if line and not line.startswith("#") and "," in line)
        return {**item,"frames":frames,"decoded_seconds":round(frames/2,1),"exit":p.returncode,"elapsed":round(time.time()-started,2),"stderr":p.stderr[-500:],"passed":frames>=20}
    except subprocess.TimeoutExpired:
        return {**item,"frames":0,"decoded_seconds":0,"exit":None,"elapsed":round(time.time()-started,2),"stderr":"timeout","passed":False}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
    rows=list(ex.map(check,candidates))
with open("replacement-candidates.json","w") as f: json.dump(rows,f,indent=2)
print(json.dumps(rows,indent=2))
