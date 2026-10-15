#!/usr/bin/env python3
"""Independent-source recovery for the 15 identities behind a net 13-channel loss.

READ-ONLY. Nothing in this file writes to config, source order, published
streams or the deployment guard. A decoder PASS alone does not certify the
channel/programme identity, and no result automatically promotes a stream.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import json
import re
import shutil
import subprocess
import time

# 89->76 is NET -13: 15 baseline feed IDs lost, while Tennis and truTV
# appeared under alternate published IDs. IDs are intentionally exact.
LOST_IDS = [
    "BET.us", "BigTenNetwork.us@SD", "CMT.us@East",
    "CinemaxHits.us@East", "CookingChannel.us@SD", "E.us@East",
    "History.us@East", "MLBStrikeZone.us@SD",
    "OneAmericaNewsNetwork.us@SD", "SECNetwork.us@SD",
    "ScienceChannel.us", "StarzKidsFamily.us@East",
    "TennisChannel.us@SD", "WeTV.us@East", "truTV.us@East",
]
BASELINE = [
    ("BET.us", "jmp2-pluto-proxy", "https://jmp2.uk/plu-61dd5bf8db0b8e00080804ff.m3u8"),
    ("BigTenNetwork.us@SD", "legacy-shared-ip", "http://23.237.104.106:8080/USA_BTN/index.m3u8"),
    ("CMT.us@East", "legacy-shared-ip", "http://23.237.104.106:8080/USA_CMT/index.m3u8"),
    ("CinemaxHits.us@East", "legacy-shared-ip", "http://23.237.104.106:8080/USA_MOREMAX/index.m3u8"),
    ("CookingChannel.us@SD", "legacy-shared-ip", "http://23.237.104.106:8080/USA_COOKING/index.m3u8"),
    ("E.us@East", "legacy-shared-ip", "http://23.237.104.106:8080/USA_E/index.m3u8"),
    ("History.us@East", "legacy-history-ip", "http://212.5.144.156:8080/history/index.m3u8"),
    ("MLBStrikeZone.us@SD", "legacy-shared-ip", "http://23.237.104.106:8080/USA_MLB_STRIKE_ZONE/index.m3u8"),
    ("OneAmericaNewsNetwork.us@SD", "legacy-shared-ip", "http://23.237.104.106:8080/USA_OAN/index.m3u8"),
    ("SECNetwork.us@SD", "legacy-shared-ip", "http://23.237.104.106:8080/USA_SEC_NETWORK/index.m3u8"),
    ("ScienceChannel.us", "legacy-shared-ip", "http://23.237.104.106:8080/USA_SCIENCE/index.m3u8"),
    ("StarzKidsFamily.us@East", "legacy-shared-ip", "http://23.237.104.106:8080/USA_STARZ_FAMILY/index.m3u8"),
    ("TennisChannel.us@SD", "legacy-shared-ip", "http://23.237.104.106:8080/USA_TENNIS/index.m3u8"),
    ("WeTV.us@East", "legacy-shared-ip", "http://23.237.104.106:8080/USA_WE_TV/index.m3u8"),
    ("truTV.us@East", "legacy-shared-ip", "http://23.237.104.106:8080/USA_TRUTV/index.m3u8"),
]
# New media hosts sourced from doms9/iptv refreshed on Oct 14, plus
# AynaScope/AynaOTT and KlowdTV. Host-independent ≠ operator-independent.
ALTERNATES = [
    ("BET.us", "wonvt-tvnow", "https://cache0.wonvt.st/live/1a3of01189opd41qnda9f/master.m3u8", "https://tvnow.st/", "needs-network-bug-and-schedule-check"),
    ("BigTenNetwork.us@SD", "wonvt-tvnow", "https://cache0.wonvt.st/live/12ttivn0fhm14f0yr8ber/master.m3u8", "https://tvnow.st/", "needs-network-bug-and-schedule-check"),
    ("E.us@East", "wonvt-tvnow", "https://cache0.wonvt.st/live/15a0cd61f3w7um0229g5g/master.m3u8", "https://tvnow.st/", "needs-network-bug-and-east-schedule-check"),
    ("ScienceChannel.us", "wonvt-tvnow", "https://cache0.wonvt.st/live/1qy87o21k84k1r0zek1wt/master.m3u8", "https://tvnow.st/", "needs-network-bug-and-schedule-check"),
    ("SECNetwork.us@SD", "wonvt-tvnow", "https://cache0.wonvt.st/live/0wvobh902biwzw08m7trv/master.m3u8", "https://tvnow.st/", "needs-network-bug-and-schedule-check"),
    ("OneAmericaNewsNetwork.us@SD", "klowdtv-cdn-chunks", "https://a-cdn.klowdtv.com/live1/oan_720p/chunks.m3u8", "", "verify-network-bug"),
    ("OneAmericaNewsNetwork.us@SD", "klowdtv-cdn-playlist", "https://a-cdn.klowdtv.com/live1/oan_720p/playlist.m3u8", "", "verify-network-bug"),
    ("History.us@East", "aynascope-english", "https://tvsen5.aynascope.net/historyen/index.m3u8", "", "parity-matched-36-frames-across-74s-still-needs-schedule-check"),
    ("History.us@East", "aynaott-history-alt", "https://tvsen3.aynaott.com/np3JstRE/index.m3u8", "", "needs-east-programme-check"),
    ("CookingChannel.us@SD", "aynascope-cooking-tv-unverified", "https://tvsen7.aynascope.net/cooking/index.m3u8", "", "COOKING-TV-label-not-confirmed-as-US-Cooking-Channel"),
    ("truTV.us@East", "warner-east-slate", "https://turnerlive.warnermediacdn.com/hls/live/2023176/trueast/slate/VIDEO_0_3564000.m3u8", "", "SLATE-path-do-not-treat-as-live-programming"),
    ("TennisChannel.us@SD", "reseller-feed-unverified", "http://138.59.177.78:9999/play/a0gl/index.m3u8", "", "needs-same-US-programming-verification"),
    # Secondary-origin feeds published in InsolenceWillow/insolencetvgo.
    # Distinct media hosts, not independent providers until verified.
    ("BigTenNetwork.us@SD", "insolence-btn-direct", "http://212.102.60.231/BIG_TEN_NETWORK/index.m3u8", "", "exact-BTN-label-unverified"),
    ("CMT.us@East", "insolence-cmt-direct", "http://212.102.60.231/CMT/index.m3u8", "", "US-East-CMT-label-unverified"),
    ("CookingChannel.us@SD", "insolence-cooking-direct", "http://212.102.60.231/COOKING_CHANNEL/index.m3u8", "", "Cooking-Channel-USA-label-unverified"),
    ("WeTV.us@East", "insolence-wetv-direct", "http://212.102.60.231/WE_TV/index.m3u8", "", "US-East-WEtv-label-unverified"),
    ("MLBStrikeZone.us@SD", "insolence-mlb-strike-direct", "http://74.48.44.156:1234/stream/asd/474/master.m3u8", "", "US-MLB-Strike-Zone-label-unverified"),
    ("CinemaxHits.us@East", "insolence-moremax-east-direct", "http://74.48.44.156:1234/stream/asd/343/master.m3u8", "", "MoreMAX-East-not-all-Cinemax-feeds"),
    ("StarzKidsFamily.us@East", "insolence-starz-kids-east-direct", "http://74.48.44.156:1234/stream/asd/468/master.m3u8", "", "Starz-Kids-and-Family-East-label-unverified"),
    # Direct origins from arquerido TV247 and judy-gotv refreshed playlists,
    # all identity-unverified until visual/programme QA.
    ("BET.us", "tv247-bet-memfs", "https://ft.fbcdntv247.cfd/memfs/bet.m3u8", "", "BET-US-identity-unverified"),
    ("BigTenNetwork.us@SD", "tv247-big-ten-memfs", "https://ft.fbcdntv247.cfd/memfs/a9fac2ae-4feb-4765-aded-46b61277a09b_output_0.m3u8", "", "BTN-exact-network-unverified"),
    ("History.us@East", "tv247-history-memfs", "https://ft.fbcdntv247.cfd/memfs/7ba806d9-3ae3-4425-a46d-90db0b27988a_output_0.m3u8", "", "History-US-East-unverified"),
    ("SECNetwork.us@SD", "espnfree-sec-channel", "https://cdn.espnfreenew.xyz/channel/sec.m3u8", "", "SEC-Network-identity-unverified"),
    ("CMT.us@East", "moveonjoy-fl2-cmt", "https://fl2.moveonjoy.com/CMT/index.m3u8", "", "CMT-US-East-unverified"),
    ("History.us@East", "moveonjoy-fl7-history", "https://fl7.moveonjoy.com/history_channel/index.m3u8", "", "History-US-East-unverified"),
    ("WeTV.us@East", "moveonjoy-fl12-wetv", "http://fl12.moveonjoy.com/WE_TV/index.m3u8", "", "WEtv-US-East-unverified"),
]


def single_probe(url, referer, *, seconds, ordinal):
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
           "-rw_timeout", "15000000", "-user_agent", "Mozilla/5.0"]
    if referer:
        cmd += ["-headers", "Referer: " + referer + "\r\n"]
    cmd += ["-i", url, "-map", "0:v:0", "-an", "-t", str(seconds),
            "-vf", "fps=2,scale=160:-2", "-f", "framemd5", "-"]
    started = time.monotonic()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=max(38, seconds+32))
        frames = []
        for line in p.stdout.splitlines():
            if line.startswith("#"):
                continue
            parts = line.split(",")
            if len(parts) >= 6 and re.fullmatch("[0-9a-f]{32}", parts[-1].strip()):
                frames.append(parts[-1].strip())
        # Short frozen repeating video is not a valid linear feed.
        windows = [tuple(frames[i:i+4]) for i in range(0, len(frames)-3, 4)]
        repeated = len(windows) >= 3 and len(set(windows)) < len(windows)
        passed = (p.returncode == 0 and len(frames) >= int(seconds*1.4)
                  and len(set(frames)) >= 4 and not repeated)
        return {
            "ordinal": ordinal, "seconds": seconds, "passed": passed,
            "decoded_frames": len(frames), "unique_frames": len(set(frames)),
            "short_repeat": repeated, "return_code": p.returncode,
            "elapsed": round(time.monotonic()-started, 1),
            "first_12_fingerprint": hashlib.sha256(",".join(frames[:12]).encode()).hexdigest()[:14],
            "error": p.stderr[-400:],
        }
    except subprocess.TimeoutExpired:
        return {"ordinal": ordinal, "seconds": seconds, "passed": False,
                "decoded_frames": 0, "error": "FFmpeg probe timed out"}
    except Exception as e:
        return {"ordinal": ordinal, "seconds": seconds, "passed": False,
                "decoded_frames": 0, "error": f"{type(e).__name__}: {str(e)[:180]}"}


def check(row):
    tvg_id, label, url, referer, identity = row
    a = single_probe(url, referer, seconds=12, ordinal=1)
    results = [a]
    if a.get("passed"):
        time.sleep(5)
        b = single_probe(url, referer, seconds=12, ordinal=2)
        results.append(b)
    qualified = len(results)==2 and all(x.get("passed") for x in results)
    if qualified and results[0]["first_12_fingerprint"] == results[1]["first_12_fingerprint"]:
        qualified = False
        results[1]["identical_restart_warning"] = True
    return {
        "tvg_id": tvg_id, "label": label, "url": url,
        "host": urlsplit(url).hostname, "identity_verification": identity,
        "referer": referer, "two_probe_media_pass": qualified,
        "media_probes": results, "extended_media_pass": False,
    }


def main():
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg required")
    candidates = [(tvg, label, url, "", "baseline-source") for tvg,label,url in BASELINE]
    candidates += ALTERNATES
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=8) as pool:
        tested = list(pool.map(check, candidates))
    viable = [r for r in tested if r["two_probe_media_pass"]]
    with ThreadPoolExecutor(max_workers=6) as pool:
        extended = list(pool.map(
            lambda row: single_probe(
                row["url"], row["referer"], seconds=65, ordinal=3
            ), viable,
        ))
    for row, result in zip(viable, extended):
        row["extended_probe"] = result
        row["extended_media_pass"] = result["passed"]
    overview = {}
    for id in LOST_IDS:
        rows = [r for r in tested if r["tvg_id"] == id]
        # A video test alone MUST NOT count as exact network recovery.
        overview[id] = {
            "tested": len(rows),
            "two_probe_pass": [x["label"] for x in rows if x["two_probe_media_pass"]],
            "extended_media_pass": [x["label"] for x in rows if x["extended_media_pass"]],
            "identity_verified": False,
            "promoted": False,
            "final_QA_passed": False,
        }
    summary = {
        "identity_gaps": len(LOST_IDS), "original_net_loss": 13,
        "candidates_checked": len(tested),
        "two_probe_media_pass": sum(r["two_probe_media_pass"] for r in tested),
        "extended_media_pass": sum(r["extended_media_pass"] for r in tested),
        "identity_confirmed": 0, "production_sources_changed": 0,
        "elapsed_seconds": round(time.monotonic()-t0, 1),
    }
    data = {"version": 1, "built_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary, "identity_gaps": overview, "candidates": tested}
    dst = Path("research/diagnostics/lost-13-source-probe.json")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(data, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    for id, r in overview.items():
        print(f"{id}: {r['extended_media_pass'] or '(no qualified 65s source yet)'}")
    print("Results:", dst)

if __name__ == "__main__":
    main()
