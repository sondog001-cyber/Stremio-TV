#!/usr/bin/env python3
from urllib.request import Request, urlopen
from pathlib import Path
import re

SOURCES = [
    ("US National", "https://iptv-org.github.io/iptv/countries/us.m3u"),
    ("Philadelphia Local", "https://iptv-org.github.io/iptv/cities/usphl.m3u"),
]

EPG_URL = "https://vcicio.github.io/US-EPG/states/PA.xml.gz"
OUT = Path("combined.m3u")

def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8-sig", errors="replace")

def parse_entries(text: str):
    lines = [x.rstrip("\r") for x in text.splitlines()]
    entries = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            block = [lines[i]]
            i += 1
            while i < len(lines):
                nxt = lines[i].strip()
                if not nxt:
                    i += 1
                    continue
                if nxt.startswith("#EXTINF:"):
                    break
                block.append(lines[i])
                i += 1
                if not nxt.startswith("#"):
                    break
            if len(block) >= 2 and not block[-1].lstrip().startswith("#"):
                entries.append(block)
            continue
        i += 1
    return entries

def tvg_id(extinf: str):
    m = re.search(r'\btvg-id="([^"]*)"', extinf, flags=re.I)
    return (m.group(1).strip().lower() if m else "")

all_entries = []
seen_urls = set()

for source_name, source_url in SOURCES:
    data = fetch(source_url)
    for block in parse_entries(data):
        url = block[-1].strip()
        if url in seen_urls:
            continue
        seen_urls.add(url)
        all_entries.append(block)

header = f'#EXTM3U x-tvg-url="{EPG_URL}" url-tvg="{EPG_URL}"'
output = [header]
for block in all_entries:
    output.extend(block)

OUT.write_text("\n".join(output) + "\n", encoding="utf-8")
print(f"Wrote {OUT} with {len(all_entries)} stream entries")
