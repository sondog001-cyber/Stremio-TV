#!/usr/bin/env python3
"""90-100s isolated direct-HLS playback QA for FS2 and CBS Sports Network.

NEVER publishes or persists signed URLs, headers, live keys, TS bytes or
provider credentials. The sole purpose is diagnosis on an ephemeral PR runner.
An FFmpeg decode pass does not establish exact channel identity or authority
to distribute the stream.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import urllib.parse
from collections import Counter

from qa_daddylive_players import (
    get_resolver, referer_from_vlc, manifest_info, get_media, safe_public_url,
    USER_AGENT,
)

CHANNELS = ("FoxSports2.us", "CBSSportsNetwork.us")
SERVER = "player"
TARGET_SECONDS = 100
MAX_WALL_SECONDS = 150
SAMPLE_EVERY_SECONDS = 11
STALL_THRESHOLD_SECONDS = 27
MAX_SEGMENT_BYTES = 9500000
OUTDIR = Path("qa-results")
THUMBS = OUTDIR / "identity-thumbnails"
REPORT = OUTDIR / "daddylive-player6-sustained.json"


def parse_clock(text):
    try:
        a = str(text).split(":")
        if len(a) != 3:
            return 0.
        return 3600 * float(a[0]) + 60 * float(a[1]) + float(a[2])
    except (ValueError, TypeError):
        return 0.


def save_thumb(segment, path):
    if not segment:
        return False
    # No stream URLs, TS media, tokens, or headers are persisted.
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
         "-f", "mpegts", "-i", "pipe:0", "-frames:v", "1", "-vf",
         "scale=384:-2", "-q:v", "12", "-y", str(path)],
        input=segment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=20, check=False,
    )
    return result.returncode == 0 and path.exists() and path.stat().st_size > 100


def inspect_segment(url, referer):
    safe_public_url(url)
    path = urllib.parse.urlsplit(url).path.lower()
    if not path.endswith((".ts", ".mpegts", ".m2ts")):
        raise ValueError("non-TS/image-wrapped segments excluded")
    blob, effective, status = get_media(url, referer=referer, limit=MAX_SEGMENT_BYTES)
    if blob.startswith((b"\x89PNG\r\n\x1a\n", b"RIFF")) or blob.lstrip().lower().startswith((b"<html", b"<!doctype")):
        raise ValueError("non-video wrapper or HTML")
    return {
        "digest": hashlib.sha256(blob).hexdigest()[:20],
        "host": urllib.parse.urlsplit(effective).hostname,
        "bytes": len(blob),
        "segment": blob,
    }


def monitor_manifest(direct_url, referer, begun, halt, data):
    while not halt.is_set():
        elapsed = time.monotonic() - begun
        if elapsed > TARGET_SECONDS + 8:
            break
        snap = {"second": round(elapsed, 1)}
        try:
            m = manifest_info(direct_url, referer)
            snap["sequence"] = m.get("sequence")
            snap["media_host"] = m.get("final_host")
            snap["window_segment_count"] = len(m["segments"])
            snap["endlist"] = m["endlist"]
            if m["endlist"]:
                snap["error"] = "media playlist ended"
                data["endlist_seen"] = True
            last = m["segments"][-1]
            v = inspect_segment(last, referer)
            snap["fingerprint"] = v["digest"]
            snap["segment_host"] = v["host"]
            snap["segment_size"] = v["bytes"]
            # Keep no more than two brief frame samples for identity review.
            if not data.get("first_segment"):
                data["first_segment"] = v["segment"]
            if elapsed > 70:
                data["last_segment"] = v["segment"]
        except Exception as e:
            snap["error"] = type(e).__name__
            if hasattr(e, "code"):
                snap["http_status"] = e.code
        data["snapshots"].append(snap)
        halt.wait(SAMPLE_EVERY_SECONDS)


def run_ffmpeg(url, referer):
    safe_public_url(url)
    cmd = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-stats_period", "4", "-progress", "pipe:1",
        "-rw_timeout", "15000000",
        "-user_agent", USER_AGENT,
    ]
    if referer:
        safe_public_url(referer)
        cmd += ["-referer", referer]
    cmd += ["-protocol_whitelist", "http,https,tcp,tls,crypto",
            "-i", url, "-map", "0:v:0", "-an", "-t",
            str(TARGET_SECONDS), "-f", "null", "-"]
    prog = []
    errors = []
    started = time.monotonic()
    state = {"frame": 0, "duration": 0., "last_advance": started}
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    except (FileNotFoundError, OSError) as e:
        return {"ffmpeg_launch_failed": type(e).__name__}

    def stdout_reader():
        stage = {}
        for line in p.stdout:
            if "=" not in line:
                continue
            key, _, val = line.strip().partition("=")
            stage[key] = val
            if key == "progress":
                frame = int(stage.get("frame", "0") or 0)
                dur = parse_clock(stage.get("out_time", ""))
                wall = time.monotonic() - started
                prog.append({"wall_s": round(wall, 1), "frame": frame,
                             "duration_s": round(dur, 1)})
                if frame > state["frame"] or dur > state["duration"]:
                    state.update(frame=frame, duration=dur, last_advance=time.monotonic())
                stage = {}
    def stderr_reader():
        # Save error categories, never raw stderr: it can include signed URLs.
        for line in p.stderr:
            low = line.lower()
            if "403" in low: errors.append("http_403")
            elif "404" in low: errors.append("http_404")
            elif "429" in low: errors.append("http_429")
            elif "timed out" in low: errors.append("timeout")
            elif "invalid data" in low: errors.append("invalid_media")
            elif "error" in low: errors.append("ffmpeg_error")
    ta = threading.Thread(target=stdout_reader, daemon=True)
    tb = threading.Thread(target=stderr_reader, daemon=True)
    ta.start()
    tb.start()
    stall = False
    while p.poll() is None:
        wall = time.monotonic() - started
        if wall > MAX_WALL_SECONDS or (wall > 40 and
                                      time.monotonic() - state["last_advance"] > STALL_THRESHOLD_SECONDS):
            stall = wall <= MAX_WALL_SECONDS
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
            break
        time.sleep(1.0)
    ta.join(timeout=5)
    tb.join(timeout=5)
    # Track the longest gap between actual increasing decoded-frame counters.
    increases = [pt for i, pt in enumerate(prog)
                 if pt["frame"] > (prog[i-1]["frame"] if i else 0)]
    elapsed_gaps = [b["wall_s"] - a["wall_s"] for a, b in zip(increases, increases[1:])]
    return {
        "ffmpeg_exit": p.returncode,
        "wall_seconds": round(time.monotonic() - started, 1),
        "decoded_duration_seconds": round(state["duration"], 1),
        "decoded_video_frames": state["frame"],
        "max_frame_progress_gap_seconds": round(max(elapsed_gaps, default=0.), 1),
        "ffmpeg_stall_aborted": stall,
        "ffmpeg_error_types": dict(Counter(errors)),
        "ffmpeg_progress_points": prog,
    }


def check(target):
    row = {
        "tvg_id": target["tvg_id"], "channel_id": target["channel_id"],
        "player": SERVER, "technical_sustained_pass": False,
        "exact_content_identity_verified": False, "source_authorization_verified": False,
        "independently_owned_upstream_verified": False, "approved_for_production": False,
    }
    try:
        resolution = get_resolver(target, SERVER)
        direct = str(resolution.get("direct") or "")
        if not direct.startswith(("http://", "https://")) or not resolution.get("isHls"):
            raise ValueError("resolver did not return direct HLS")
        if "/api/live" in direct or "/api/proxy" in direct:
            raise ValueError("resolver proxy/live endpoint excluded")
        safe_public_url(direct)
        ref = referer_from_vlc(resolution.get("vlc"))
        media = manifest_info(direct, ref)
        if media["endlist"]:
            raise ValueError("not a live HLS playlist")
        if any(not urllib.parse.urlsplit(u).path.lower().endswith((".ts", ".m2ts", ".mpegts"))
               for u in media["segments"][-2:]):
            raise ValueError("nonstandard wrapped media segments")
        for u in media["segments"][-2:]:
            safe_public_url(u)
        row["playlist_host"] = media["final_host"]
        row["has_referer"] = bool(ref)
        row["has_expiry_metadata"] = bool(resolution.get("expiresAt"))
        row["direct_manifest_verified"] = True
        begun = time.monotonic()
        halt = threading.Event()
        data = {"snapshots": [], "endlist_seen": False}
        probe = threading.Thread(target=monitor_manifest,
                                 args=(direct, ref, begun, halt, data), daemon=True)
        probe.start()
        video = run_ffmpeg(direct, ref)
        halt.set()
        probe.join(timeout=15)
        row.update(video)
        snapshots = data["snapshots"]
        # Each repeat sample is compared only when the URL/sequence may change.
        pairs = [(s.get("sequence"), s.get("fingerprint")) for s in snapshots if s.get("fingerprint")]
        seqs = {s for s, v in pairs}
        fingerprints = {v for s, v in pairs}
        repeated_advancing_media = []
        for i, (seq, digest) in enumerate(pairs):
            if any(prev_digest == digest and prev_seq != seq
                   for prev_seq, prev_digest in pairs[:i]):
                repeated_advancing_media.append({"sequence": str(seq), "fingerprint": digest})
        row["samples_observed"] = len(snapshots)
        row["unique_sequences"] = len(seqs)
        row["unique_segment_fingerprints"] = len(fingerprints)
        row["repeated_content_on_new_sequence"] = bool(repeated_advancing_media)
        row["snapshot_errors"] = sum(1 for s in snapshots if "error" in s)
        row["snapshots"] = snapshots
        row["endlist_seen"] = data["endlist_seen"]
        row["technical_sustained_pass"] = bool(
            video.get("ffmpeg_exit") == 0
            and video.get("decoded_duration_seconds", 0) >= 90
            and video.get("wall_seconds", 0) >= 75
            and video.get("decoded_video_frames", 0) >= 900
            and len(seqs) >= 3
            and len(fingerprints) >= 3
            and not repeated_advancing_media
            and not data["endlist_seen"]
            and video.get("max_frame_progress_gap_seconds", 100) < STALL_THRESHOLD_SECONDS
            and row["snapshot_errors"] <= 1
        )
        label = "FS2" if target["tvg_id"].startswith("Fox") else "CBSSN"
        THUMBS.mkdir(parents=True, exist_ok=True)
        files = []
        for suffix, blob in (("early", data.get("first_segment")),
                             ("late", data.get("last_segment"))):
            path = THUMBS / (label + "-" + suffix + ".jpg")
            if save_thumb(blob, path):
                files.append(path.name)
        row["identity_thumbnails"] = files
        row["status"] = "sustained_technical_pass_only" if row["technical_sustained_pass"] else "sustained_technical_inconclusive_or_failed"
    except Exception as e:
        row["status"] = "probe_unavailable"
        row["failure_type"] = type(e).__name__
        if hasattr(e, "code"):
            row["http_status"] = e.code
        else:
            row["failure_description"] = str(e)[:145]
    return row


def main():
    config = json.loads(Path("config.json").read_text())
    targets = {t["tvg_id"]: t for t in config["discovery"]["daddylive_resolver"]["targets"]}
    rows = []
    for id in CHANNELS:
        print("BEGIN sustained direct-HLS test for", id, flush=True)
        r = check(targets[id])
        rows.append(r)
        print("END", id, json.dumps({
            k: r.get(k) for k in (
                "status", "playlist_host", "ffmpeg_exit", "wall_seconds",
                "decoded_duration_seconds", "decoded_video_frames", "samples_observed",
                "unique_sequences", "unique_segment_fingerprints",
                "repeated_content_on_new_sequence", "technical_sustained_pass",
                "identity_thumbnails", "snapshot_errors"
            )}), flush=True)
        time.sleep(2)
    OUTPUT = REPORT
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "scope": "isolated direct-playback technical QA, not content authorization or production approval",
        "test_target_seconds": TARGET_SECONDS,
        "channels": rows,
        "production_modified": False,
        "authorization_note": "Third-party DaddyLive-derived streaming host has no independently verified public distribution permission; authorization stays false.",
        "identity_note": "JPEG thumbnails for limited human visual review only; never infer identity from playlist names alone."
    }, indent=2) + "\n")
    print("SUMMARY", json.dumps({r["tvg_id"]: r["status"] for r in rows}), flush=True)


if __name__ == "__main__":
    main()
