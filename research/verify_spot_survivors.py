#!/usr/bin/env python3
"""Three independent 60-second decoder windows and visible identity samples."""
import concurrent.futures
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build


def verify(entry, output):
    channel = re.sub(r"[^A-Za-z0-9_-]", "-", entry["tvg_id"])
    directory = output / channel
    directory.mkdir(parents=True, exist_ok=True)
    report = {"tvg_id": entry["tvg_id"], "url": entry["url"], "windows": [],
              "identity_verified": False, "production_approved": False}
    for number in range(1, 4):
        before = build._probe_stream(entry, timeout=6, verify_segment=True)
        command = [shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin",
                   "-user_agent", build.USER_AGENT, "-rw_timeout", "10000000"]
        if entry.get("headers"):
            command += ["-headers", "".join(f"{k}: {v}\r\n" for k, v in entry["headers"].items())]
        command += ["-i", entry["url"], "-filter_complex",
                    "[0:v]fps=2,split=2[h0][j0];[h0]scale=160:-2[h];"
                    "[j0]select='not(mod(n,40))',scale=640:-2[j]",
                    "-map", "[h]", "-t", "60", "-an", "-f", "framemd5", "-",
                    "-map", "[j]", "-t", "60", "-an", "-fps_mode", "vfr", "-frames:v", "3",
                    str(directory / f"window-{number}-%02d.jpg")]
        row = {"number": number, "health_before": before, "passed": False}
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, timeout=85, check=False)
            hashes = build._framemd5_hashes(result.stdout)
            repeat = build._find_repeated_frame_clip(hashes, 2, 2, 4)
            row.update(exit_code=result.returncode, decoded_frames=len(hashes),
                       decoded_seconds=len(hashes) / 2, repeat=repeat,
                       frozen=bool(hashes) and len(set(hashes)) == 1,
                       error=build._sanitize_ffmpeg_error(result.stderr, entry["url"]))
            row["passed"] = (result.returncode == 0 and len(hashes) >= 110
                             and repeat is None and not row["frozen"] and before.get("status") == "ok")
        except subprocess.TimeoutExpired:
            row.update(failure="timeout")
        row["health_after"] = build._probe_stream(entry, timeout=6, verify_segment=True)
        after = row["health_after"]
        row["live_window_advanced"] = bool(before.get("hls_is_live") and after.get("hls_is_live") and (
            before.get("hls_media_sequence") != after.get("hls_media_sequence")
            or before.get("hls_tail_sha256") != after.get("hls_tail_sha256")))
        row["passed"] = row["passed"] and after.get("status") == "ok" and row["live_window_advanced"]
        report["windows"].append(row)
        (directory / "evidence.json").write_text(json.dumps(report, indent=2))
    report["repeated_media_passed"] = all(w["passed"] for w in report["windows"])
    report["snapshots"] = [p.name for p in directory.glob("*.jpg")]
    (directory / "evidence.json").write_text(json.dumps(report, indent=2))
    return report


def main():
    entries = json.loads((ROOT / "research/new-spot-survivors.json").read_text())["candidates"]
    out = ROOT / "survivor-results"
    out.mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        reports = list(pool.map(lambda entry: verify(entry, out), entries))
    report = {"run_id": os.environ.get("GITHUB_RUN_ID"), "candidates": reports,
              "production_changes": False}
    (out / "summary.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({r["tvg_id"]: r["repeated_media_passed"] for r in reports}, indent=2))


if __name__ == "__main__":
    main()
