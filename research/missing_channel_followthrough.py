#!/usr/bin/env python3
"""Bounded exact-ID discovery and normal media evidence; never promotes sources."""
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build
import playlist_scrub

OUT = ROOT / 'targeted-results'
DOCS = []


def fetch(url, limit=8_000_000):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': build.USER_AGENT}), timeout=18) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError('document-too-large')
    return data


def inspect(entry):
    directory = OUT / hashlib.sha256(entry['url'].encode()).hexdigest()[:12]
    directory.mkdir(parents=True, exist_ok=True)
    row = {**entry, 'started_at': dt.datetime.now(dt.timezone.utc).isoformat(),
           'identity_verified': False, 'production_approved': False, 'windows': []}
    health = build._probe_stream(entry, timeout=8, verify_segment=True)
    row['health'] = health
    # Full five-probe burn-in remains separate from final-primary QA.
    probes = [health]
    if health.get('status') == 'ok':
        for _ in range(4):
            time.sleep(15)
            probes.append(build._probe_stream(entry, timeout=8, verify_segment=True))
            if probes[-1].get('status') != 'ok':
                break
    row['burn_in_passed'] = len(probes) == 5 and all(p.get('status') == 'ok' for p in probes)
    row['burn_in'] = probes
    if row['burn_in_passed']:
        row['decoder'] = build._validate_direct_media_survival(entry, SETTINGS)
        if row['decoder'].get('status') == 'ok':
            for number in range(1, 4):
                before = build._probe_stream(entry, timeout=8, verify_segment=True)
                cmd = [shutil.which('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-nostdin',
                       '-user_agent', build.USER_AGENT, '-rw_timeout', '10000000']
                if entry.get('headers'):
                    cmd += ['-headers', ''.join(f'{k}: {v}\r\n' for k,v in entry['headers'].items())]
                cmd += ['-i', entry['url'], '-filter_complex',
                        "[0:v]fps=2,split=2[h0][j0];[h0]scale=160:-2[h];[j0]select='not(mod(n,40))',scale=640:-2[j]",
                        '-map', '[h]', '-t', '60', '-an', '-f', 'framemd5', '-',
                        '-map', '[j]', '-t', '60', '-an', '-fps_mode', 'vfr', '-frames:v', '3',
                        str(directory / f'window-{number}-%02d.jpg')]
                window = {'number': number, 'captured_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'passed': False}
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=85)
                    hashes = build._framemd5_hashes(result.stdout)
                    repeat = build._find_repeated_frame_clip(hashes, 2, 2, 4)
                    after = build._probe_stream(entry, timeout=8, verify_segment=True)
                    advance = bool(before.get('hls_is_live') and after.get('hls_is_live') and
                                   (before.get('hls_media_sequence') != after.get('hls_media_sequence') or
                                    before.get('hls_tail_sha256') != after.get('hls_tail_sha256')))
                    window.update(decoded_frames=len(hashes), exit_code=result.returncode, repeat=repeat,
                                  live_window_advanced=advance, health_before=before, health_after=after,
                                  error=build._sanitize_ffmpeg_error(result.stderr, entry['url']))
                    window['passed'] = (result.returncode == 0 and len(hashes) >= 110 and repeat is None
                                        and len(set(hashes)) > 1 and advance
                                        and before.get('status') == after.get('status') == 'ok')
                except subprocess.TimeoutExpired:
                    window['failure'] = 'timeout'
                row['windows'].append(window)
                if not window['passed']:
                    break
    row['media_passed'] = len(row['windows']) == 3 and all(w['passed'] for w in row['windows'])
    (directory / 'evidence.json').write_text(json.dumps(row, indent=2))
    return row


def main():
    global SETTINGS
    OUT.mkdir(exist_ok=True)
    config = json.loads((ROOT / 'config.json').read_text())
    SETTINGS = config['stream_health']['direct_media_survival']
    inputs = json.loads((ROOT / 'research/missing-followthrough-inputs.json').read_text())
    now = dt.datetime.now(dt.timezone.utc)
    aliases = config['curation'].get('canonical_id_aliases', {})
    target = {x.casefold(): x for x in inputs['missing_ids']}
    inventory = json.loads((ROOT / '.research-inventory/playlist-scrub-state.json').read_text())
    known = {hashlib.sha256(v['url'].encode()).hexdigest() for v in inventory['seen'].values()}
    candidates = {x['url']: x for x in inputs['priority_candidates'] if playlist_scrub.safe_entry(x, config, now)}
    documents = []
    for url in DOCS:
        doc = {'url': url}
        try:
            data = fetch(url)
            doc.update(status='ok', bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            for entry in build.parse_m3u(data.decode('utf-8', errors='replace'), {'name': url, 'family': 'research-exact-id'}):
                raw = entry.get('tvg_id', '')
                mapped = aliases.get(raw, raw)
                tid = target.get(mapped.casefold())
                if not tid or hashlib.sha256(entry['url'].encode()).hexdigest() in known:
                    continue
                entry.update(tvg_id=tid, source_tvg_id=raw, provenance=url, review_reason='Fresh exact-ID catalog URL absent from last production baseline; no approval implied')
                if playlist_scrub.safe_entry(entry, config, now):
                    candidates.setdefault(entry['url'], entry)
        except Exception as exc:
            doc.update(status='failed', error_type=type(exc).__name__)
        documents.append(doc)
    selected = list(candidates.values())[:32]
    (OUT / 'discovery.json').write_text(json.dumps({'documents': documents, 'selected': selected,
        'pending': list(candidates.values())[32:], 'production_changes': False}, indent=2))
    # Serial per provider avoids artificial request bursts against a shared origin.
    from urllib.parse import urlsplit
    from collections import defaultdict
    import threading
    locks = defaultdict(threading.Lock)
    def locked(entry):
        with locks[urlsplit(entry['url']).hostname]:
            return inspect(entry)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(locked, selected))
    report = {'run_id': os.environ.get('GITHUB_RUN_ID'), 'head': os.environ.get('GITHUB_SHA'),
              'production_changes': False, 'tested': len(rows), 'results': rows}
    (OUT / 'summary.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'tested': len(rows), 'media_passed': sum(r['media_passed'] for r in rows), 'promoted': 0}))


if __name__ == '__main__':
    main()
