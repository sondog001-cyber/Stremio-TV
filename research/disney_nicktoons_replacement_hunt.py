#!/usr/bin/env python3
"""Isolated replacement-media-hunt for Disney and Nicktoons; no publication.

No DRM, cookies, authentication, proxy, restreaming, or redirect tricks.
Candidate entry hosts are tested conservatively; only advancing live HLS and
segment readability qualify for a short read-only FFmpeg decoder sample.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
from urllib.parse import urlsplit

from research import fresh_origin_discovery as hls
from research import bravo_nicktoons_decoder_research as continuity

ROOT = pathlib.Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "research/disney_nicktoons_replacements_20261013.json"
TARGETS = {"DisneyChannel.us", "Nicktoons.us"}
SAMPLE_SECONDS = 60
ALLOWED_FAMILIES = {"thetvapp", "moveonjoy", "airlink", "tier1streams", "aynascope", "206.212.244.63"}


def redact_url(url):
    return {"entry_host": hls.host(url), "url_sha256_12": hashlib.sha256(url.encode()).hexdigest()[:12]}


def validate_registry(data):
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 6:
        raise ValueError("Expected exactly six reviewed source leads")
    fingerprints = set()
    for c in candidates:
        url = str(c.get("entry_url") or "")
        if (c.get("tvg_id") not in TARGETS or c.get("family") not in ALLOWED_FAMILIES
                or not c.get("source_ref", "").startswith("https://github.com/")
                or not hls.valid_public_url(url)
                or urlsplit(url).query or urlsplit(url).fragment
                or c.get("public_headers") or not url.lower().endswith(".m3u8")):
            raise ValueError("Unsafe or unreviewed source lead")
        key=(c["tvg_id"], c["family"])
        if key in fingerprints:
            raise ValueError("Duplicate channel/provider family must not masquerade as redundancy")
        fingerprints.add(key)


def direct_decoder_test(url, ffmpeg="ffmpeg"):
    """Run FFmpeg as decoder only; one-second frame hashes, no video saved."""
    if not hls.valid_public_url(url):
        raise ValueError("Only direct public network URLs permitted")
    args=[ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
          "-i", url, "-t", str(SAMPLE_SECONDS), "-map", "0:v:0", "-an",
          "-vf", "fps=1,scale=160:90,format=gray", "-f", "framemd5", "pipe:1"]
    output={"ffmpeg_decoded":False,"decoded_frames":0,"continuity_pass":False}
    try:
        proc=subprocess.run(args, text=True, capture_output=True,timeout=125,check=False)
        hashes=continuity.collect_hashes(proc.stdout)
        inspect=continuity.inspect_hashes(hashes)
        output.update({"ffmpeg_decoded":proc.returncode==0,
                       "decoded_frames":len(hashes),
                       "continuity_pass":proc.returncode==0 and inspect["decoder_continuity_pass"],
                       "distinct_frame_hashes":inspect["distinct_frame_hashes"],
                       "possible_short_loops":inspect["possible_short_loops"],
                       "longest_freeze":inspect["longest_identical_frame_run_seconds"],
                       "ffmpeg_return_code":proc.returncode})
    except (OSError, subprocess.TimeoutExpired) as exc:
        output["error_type"]=type(exc).__name__
    return output


def inspect_candidate(candidate, decode=False):
    url=candidate["entry_url"]
    result={"tvg_id":candidate["tvg_id"],"family":candidate["family"],
            **redact_url(url),"source_ref":candidate["source_ref"],
            "identity_evidence":candidate["identity_evidence"],
            "probed_at":dt.datetime.now(dt.timezone.utc).isoformat(),
            "independent_broadcaster_origin_confirmed":False,
            "exact_broadcast_identity_confirmed":False,
            "authorization_confirmed":False,"local_test_eligible":False,
            "production_eligible":False,"promoted":False}
    preflight=hls.probe_manifest(url)
    result["preflight"]={k:preflight.get(k) for k in
        ("stage","hls_kind","http_status","final_host","media_host",
         "sequence_before","sequence_after","media_bytes_readable")
         if k in preflight}
    if decode and preflight.get("stage")=="progressing-hls-readable-not-decoded":
        result["decoder"]=direct_decoder_test(url)
    else:
        result["decoder"]={"skipped":"not-progressing-or-direct-decoder-not-requested"}
    return result


def report_for(channel, data, decode=False):
    validate_registry(data)
    if channel not in TARGETS:
        raise ValueError("Unlisted channel")
    results=[inspect_candidate(c,decode=decode) for c in data["candidates"] if c["tvg_id"]==channel]
    return {"channel":channel,"attempts":len(results),"tested_at":dt.datetime.now(dt.timezone.utc).isoformat(),
            "progressing_hls":sum(c["preflight"].get("stage")=="progressing-hls-readable-not-decoded" for c in results),
            "decoder_continuity_passes":sum(c["decoder"].get("continuity_pass",False) for c in results),
            "verified_original_video_origins":0,"promotions":0,"candidates":results,
            "research_only":True,
            "warning":"Passing manifest and decoder QA is not license, broadcaster-owned CDN, final identity, or durable uptime proof."}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--channel",choices=sorted(TARGETS),required=True)
    p.add_argument("--registry",type=pathlib.Path,default=CANDIDATES)
    p.add_argument("--output",type=pathlib.Path,default=pathlib.Path("research-results/replacement"))
    p.add_argument("--decode",action="store_true",help="Run bounded direct FFmpeg only on HLS-positive entries")
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    data=json.loads(args.registry.read_text(encoding="utf-8"))
    report=report_for(args.channel,data,args.decode)
    outfile=args.output/(args.channel.replace(".","-")+".json")
    outfile.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"channel":report["channel"],"attempts":report["attempts"],
                      "progressing_hls":report["progressing_hls"],
                      "decoder_continuity_passes":report["decoder_continuity_passes"],
                      "promotions":0,"outcomes":[{
                          "provider_family":x["family"],"entry_host":x["entry_host"],
                          "preflight":x["preflight"].get("stage"),
                          "decoder":x["decoder"].get("continuity_pass")} for x in report["candidates"]]},indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
