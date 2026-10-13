#!/usr/bin/env python3
"""Research-only Nicktoons *on-screen evidence* audit (no video artifacts).

Samples a single unmodified public HLS feed directly into an in-memory JPEG
buffer. Runs OCR locally on the runner, emits ONLY boolean/keyword evidence,
never captures/repackages screenshots, video, subtitles or dialog to artifacts.

Channel bug or the word SpongeBob is suggestive, not evidence of exact U.S.
East episode/clock alignment; therefore no automatic provenance/identity pass.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess

from research import nicktoons_aynascope_repeat as nick

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = pathlib.Path("research-results/identity/nicktoons-visual-metadata.json")
UPSTREAM = "http://tvsen7.aynascope.net/nicktoons/index.m3u8"
MAX_JPEG_BYTES = 5_000_000
MAX_FRAMES = 6
TARGET_KEYWORDS = {
    "nicktoons": re.compile(r"nick[\s-]*toons", re.I),
    "nickelodeon": re.compile(r"nickelodeon", re.I),
    "spongebob": re.compile(r"sponge[\s-]*bob", re.I),
    "spongebob_squarepants": re.compile(r"sponge[\s-]*bob[\s-]*square[\s-]*pants", re.I),
    "commercial_or_ad": re.compile(r"ad(?:vertisement)?\s+break", re.I),
}
REFERENCE = {
    "source": "https://americatvlistings.com/en/us/nicktoons",
    "source_title": "Nicktoons US day-by-day guide",
    "date_eastern": "2026-10-13",
    "expected_series": "SpongeBob SquarePants",
    "precision": "series-level only; does not establish episode/version/time-delay",
}

def split_jpegs(content: bytes) -> list[bytes]:
    """Bounded in-memory split of FFmpeg MJPEG stdout, no disk writes."""
    frames = []
    start = 0
    while len(frames) < MAX_FRAMES:
        a = content.find(b"\xff\xd8", start)
        if a < 0:
            break
        b = content.find(b"\xff\xd9", a + 2)
        if b < 0:
            break
        img = content[a:b+2]
        if len(img) <= MAX_JPEG_BYTES:
            frames.append(img)
        start = b + 2
    return frames

def safe_ffprobe(url: str):
    cmd = ["ffprobe", "-v", "error", "-print_format", "json",
           "-show_entries", "format=format_name:stream=index,codec_name,codec_type,width,height,closed_captions",
           url]
    try:
        done = subprocess.run(cmd, capture_output=True, timeout=22, check=False)
        if done.returncode != 0:
            return {"status": "unavailable", "returncode": done.returncode}
        data = json.loads(done.stdout.decode("utf-8","replace"))
        return {"status": "ok", "streams": [
            {key: st.get(key) for key in ("codec_name","codec_type","width","height","closed_captions")
             if key in st}
            for st in data.get("streams", [])][:6]}
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unavailable", "error_type": type(exc).__name__}

def ocr_frame(image_bytes: bytes):
    """Only emit presence of target words, never raw caption or program text."""
    matches = {}
    for psm in ("11","6"):
        try:
            cmd = ["tesseract", "stdin", "stdout", "-l", "eng", "--psm", psm]
            out = subprocess.run(cmd, input=image_bytes, capture_output=True, timeout=8, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if out.returncode:
            continue
        text = out.stdout.decode("utf-8","replace")[:2500]
        for key, pattern in TARGET_KEYWORDS.items():
            matches[key] = matches.get(key, False) or bool(pattern.search(text))
    return matches

def analyze_frames(frame_bytes):
    seen = []
    for index, payload in enumerate(frame_bytes):
        presence = ocr_frame(payload)
        seen.append({"frame_index":index, "matched_keywords":[k for k,v in presence.items() if v]})
    channel_bug_suggested = sum("nicktoons" in row["matched_keywords"] for row in seen)>=2
    series_text_seen = any("spongebob" in row["matched_keywords"] for row in seen)
    return {
        "frames_sampled":len(seen), "samples":seen,
        "nicktoons_text_seen_on_2_frames":channel_bug_suggested,
        "expected_series_text_seen":series_text_seen,
        "possible_identity_evidence":channel_bug_suggested or series_text_seen,
        "exact_us_east_episode_verified":False,
        "on_screen_program_schedule_verified":False,
        "on_screen_logo_verified_by_human":False,
    }

def audit(registry):
    candidate = nick.read_candidate(registry)
    if candidate["entry_url"] != UPSTREAM:
        raise ValueError("The reviewed AynaScope candidate changed; refuse unreviewed source")
    result = {
        "tvg_id":"Nicktoons.us", "candidate_host":"tvsen7.aynascope.net",
        "captured_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "reference_epg":REFERENCE,
        "ffprobe":safe_ffprobe(UPSTREAM),
        "ffmpeg_status":"not-attempted",
        "capture_frames_saved":False,
        "no_proxy_or_restream":True,
    }
    args=["ffmpeg","-nostdin","-hide_banner","-loglevel","error",
          "-i",UPSTREAM,"-t","57","-map","0:v:0","-an",
          "-vf","fps=1/12,scale=960:540","-q:v","5",
          "-f","image2pipe","-vcodec","mjpeg","pipe:1"]
    try:
        done=subprocess.run(args, capture_output=True, timeout=115, check=False)
        result["ffmpeg_status"]="ok" if done.returncode==0 else "decoder-or-network-failed"
        result["ffmpeg_return_code"]=done.returncode
        frames=split_jpegs(done.stdout[:MAX_JPEG_BYTES])
        result.update(analyze_frames(frames))
    except (OSError,subprocess.TimeoutExpired) as exc:
        result["ffmpeg_status"]=type(exc).__name__
        result.update(analyze_frames([]))
    result.update({
        "exact_us_nicktoons_east_identity_confirmed":False,
        "broadcaster_owned_upstream_confirmed":False,
        "permission_to_embed_in_public_addon_confirmed":False,
        "eligible_for_local_test":False,
        "eligible_for_production":False,
        "recommendation":"No change until actual US East episode/time-slot and permitted use are independently confirmed",
        "limitations":"OCR results are weak indicators; non-detection does not prove wrong channel. No frame was saved; no episode ID or broadcaster logo has been independently reviewed.",
    })
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry",type=pathlib.Path,default=ROOT/"research/disney_nicktoons_replacements_20261013.json")
    parser.add_argument("--output",type=pathlib.Path,default=REPORT)
    args=parser.parse_args()
    registry=json.loads(args.registry.read_text())
    result=audit(registry)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
