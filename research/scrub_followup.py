#!/usr/bin/env python3
"""Retest scraper leads with normal burn-in/decoder checks; never approve sources."""
import concurrent.futures
from collections import defaultdict
import datetime as dt
import json
import os
from pathlib import Path
import sys
import threading
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build
import playlist_scrub
from research.fifteen_new_spots import probe_candidate
from research.verify_spot_survivors import verify


def main():
    config = json.loads((ROOT / 'config.json').read_text())
    inputs = json.loads((ROOT / 'research/scrub-followup-inputs.json').read_text())
    out = ROOT / 'scrub-followup-results'
    out.mkdir(exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    excluded, selected = [], []
    for entry in inputs['candidates']:
        if entry['review'] != 'test' or not playlist_scrub.safe_entry(entry, config, now):
            excluded.append({'tvg_id': entry['tvg_id'], 'reason': entry['review_reason']})
        else:
            selected.append(entry)
    locks = defaultdict(threading.Lock)
    def check(entry):
        with locks[urllib.parse.urlsplit(entry['url']).hostname]:
            row = probe_candidate(entry, config['stream_health']['direct_media_survival'])
            row['eligible_for_long_check'] = bool(row.get('burn_in_passed')
                and row.get('live_window_advanced') and row['decoder'].get('status') == 'ok')
            return row
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(check, selected))
    report = {'run_id': os.environ.get('GITHUB_RUN_ID'), 'advisory_only': True,
              'production_approved': False, 'excluded': excluded, 'media_results': rows}
    (out / 'summary.json').write_text(json.dumps(report, indent=2))
    survivors = [r for r in rows if r['eligible_for_long_check']]
    # Bound the research job; every remaining survivor stays explicitly pending.
    report['long_check_pending'] = [r['tvg_id'] for r in survivors[4:]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        report['long_checks'] = list(pool.map(lambda r: verify(r, out), survivors[:4]))
    (out / 'summary.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'tested': len(rows), 'excluded': len(excluded),
                      'normal_media_survivors': len(survivors), 'promotions': 0}))


if __name__ == '__main__':
    main()
