#!/usr/bin/env python3
import json, subprocess, time, concurrent.futures

candidates = [
    {"channel":"CBS Sports Network","url":"http://scafroglia93-ua.hf.space/proxy/m3u?url=https%3A%2F%2Fthedaddy.click%2Fstream%2Fstream-308.php"},
    {"channel":"Discovery Channel","url":"http://scafroglia93-ua.hf.space/proxy/m3u?url=https%3A%2F%2Fthedaddy.click%2Fstream%2Fstream-313.php"},
    {"channel":"FXX","url":"http://scafroglia93-ua.hf.space/proxy/m3u?url=https%3A%2F%2Fthedaddy.click%2Fstream%2Fstream-298.php"},
    {"channel":"Fox Sports 2","url":"http://scafroglia93-ua.hf.space/proxy/m3u?url=https%3A%2F%2Fthedaddy.click%2Fstream%2Fstream-758.php"},
    {"channel":"HGTV","url":"http://scafroglia93-ua.hf.space/proxy/m3u?url=https%3A%2F%2Fthedaddy.click%2Fstream%2Fstream-382.php"},
    {"channel":"Investigation Discovery","url":"http://scafroglia93-ua.hf.space/proxy/m3u?url=https%3A%2F%2Fthedaddy.click%2Fstream%2Fstream-324.php"},
    {"channel":"Magnolia Network","url":"http://scafroglia93-ua.hf.space/proxy/m3u?url=https%3A%2F%2Fthedaddy.click%2Fstream%2Fstream-299.php"},
    {"channel":"MLB Network","url":"http://scafroglia93-ua.hf.space/proxy/m3u?url=https%3A%2F%2Fthedaddy.click%2Fstream%2Fstream-399.php"},
    {"channel":"NBC Sports Philadelphia","url":"http://scafroglia93-ua.hf.space/proxy/m3u?url=https%3A%2F%2Fthedaddy.click%2Fstream%2Fstream-777.php"},
    {"channel":"OWN","url":"http://scafroglia93-ua.hf.space/proxy/m3u?url=https%3A%2F%2Fthedaddy.click%2Fstream%2Fstream-331.php"},
    {"channel":"Reelz","url":"http://scafroglia93-ua.hf.space/proxy/m3u?url=https%3A%2F%2Fthedaddy.click%2Fstream%2Fstream-293.php"},
    {"channel":"Smithsonian Channel","url":"http://scafroglia93-ua.hf.space/proxy/m3u?url=https%3A%2F%2Fthedaddy.click%2Fstream%2Fstream-603.php"},
    {"channel":"SundanceTV","url":"http://scafroglia93-ua.hf.space/proxy/m3u?url=https%3A%2F%2Fthedaddy.click%2Fstream%2Fstream-658.php"},
    {"channel":"TLC","url":"http://scafroglia93-ua.hf.space/proxy/m3u?url=https%3A%2F%2Fthedaddy.click%2Fstream%2Fstream-337.php"},
    {"channel":"Travel Channel","url":"http://scafroglia93-ua.hf.space/proxy/m3u?url=https%3A%2F%2Fthedaddy.click%2Fstream%2Fstream-340.php"},
    {"channel":"Weather Channel","url":"http://scafroglia93-ua.hf.space/proxy/m3u?url=https%3A%2F%2Fthedaddy.click%2Fstream%2Fstream-394.php"}
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
