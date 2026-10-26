#!/usr/bin/env python3
"""Read-only public directory discovery. Labels are never channel identity proof.

Do not execute third-party scraper code, probe excluded links or promote results.
This examines two independently discovered public directory APIs, not old playlists.
"""
import argparse
import datetime as dt
import html
import json
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build
from research.fresh_origin_discovery import fetch, host, valid_public_url, OPENER

QUERIES = {
    'WPVI.us': 'WPVI', 'WCAU.us': 'WCAU', 'KYW.us': 'KYW', 'WPHL.us': 'WPHL',
    'WPSG.us': 'WPSG', 'ESPNews.us': 'ESPNews', 'CBSSportsNetwork.us': 'CBS Sports Network',
    'NBCSportsPhiladelphiaPlus.us': 'NBC Sports Philadelphia', 'USANetwork.us': 'USA Network',
    'SundanceTV.us': 'Sundance', 'MagnoliaNetwork.us': 'Magnolia',
    'HallmarkChannel.us': 'Hallmark Channel', 'HallmarkMystery.us': 'Hallmark Mystery',
    'SmithsonianChannel.us': 'Smithsonian', 'HallmarkFamily.us': 'Hallmark Family',
    'StarzCinema.us': 'Starz Cinema', 'StarzComedy.us': 'Starz Comedy',
    'StarzEdge.us': 'Starz Edge', 'StarzEncoreSpanish.us': 'Starz Encore',
    'CinemaxClassics.us': 'Cinemax', 'HBOMovies.us': 'HBO Movies', 'RFDTV.us': 'RFD',
    'History.us': 'History', 'CNBC.us': 'CNBC', 'TeenNick.us': 'TeenNick', 'HBOHits.us': 'HBO Hits',
}


def text(url, limit=1_500_000):
    return fetch(url, limit, timeout=8)['data'].decode('utf-8', 'replace')


def clean_title(value):
    return html.unescape(re.sub('<[^>]+>', '', str(value)))[:160]


def collect(baseline, config):
    known = {row.get('url') for row in baseline}
    report = {'built_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'research_only': True, 'automatic_promotion': False,
              'identity_status': 'all directory labels require independent programming review',
              'media_validation': 'not-tested; discovery only',
              'sources': [], 'candidates': [], 'rejected': [], 'errors': []}
    seen = set()

    def candidate(url, title, provenance, target_hint=None):
        if not isinstance(url, str) or not valid_public_url(url):
            report['rejected'].append({'provenance': provenance, 'reason': 'unsafe/nonpublic URL; omitted'})
            return
        entry = {'url': url, 'name': clean_title(title), 'tvg_id': target_hint or '',
                 'family': 'public-directory-research', 'headers': {}}
        safe, rejected = build.apply_safety_controls([entry], config)
        if not safe:
            report['rejected'].append({'provenance': provenance, 'reason': 'project safety controls; URL omitted'})
            return
        if url in seen:
            return
        seen.add(url)
        report['candidates'].append({**entry, 'target_hint': target_hint,
            'provenance': provenance, 'known_url': url in known, 'media_host': host(url),
            'identity_verified': False, 'media_validation': 'not-tested',
            'independent_origin_verified': False})

    # Both endpoints are documented as the same news wall; use one, not two origins.
    try:
        rows = json.loads(text('https://tvdata.jest.one/'))
        report['sources'].append({'directory': 'jest.one', 'entries': len(rows)})
        for row in rows:
            url = row.get('src')
            if isinstance(url, str) and '.m3u8' in url.lower():
                candidate(url, row.get('name'), 'https://tvdata.jest.one/')
    except Exception as exc:
        report['errors'].append({'directory': 'jest.one', 'error_type': type(exc).__name__})

    # Bounded exact-name searches: no broad full-directory scraping or recursion.
    resolutions = 0
    for target, query in QUERIES.items():
        api = 'https://vipotv.com/wp-json/wp/v2/posts?' + urllib.parse.urlencode({'search': query, 'per_page': 3})
        try:
            posts = json.loads(text(api))
            if not isinstance(posts, list):
                raise ValueError('unexpected directory response')
            report['sources'].append({'directory': 'vipotv', 'target_hint': target, 'posts': len(posts)})
            for post in posts:
                if resolutions >= 12:
                    break
                link = post.get('link', '')
                if urllib.parse.urlsplit(link).hostname not in {'vipotv.com', 'www.vipotv.com'}:
                    continue
                title = clean_title((post.get('title') or {}).get('rendered'))
                page = text(link)
                match = re.search(r'https://livetv\.work/fireplayer/video/([a-fA-F0-9]{32})', page)
                if not match:
                    continue
                resolutions += 1
                token = match.group(1)
                endpoint = f'https://livetv.work/fireplayer/video/{token}?do=getVideo'
                request = urllib.request.Request(endpoint, data=urllib.parse.urlencode(
                    {'hash': token, 'r': link, 's': ''}).encode(), headers={
                    'User-Agent': 'Stremio-TV-public-directory-research/1.0',
                    'X-Requested-With': 'XMLHttpRequest'})
                with OPENER.open(request, timeout=8) as response:
                    raw = response.read(300001)
                if len(raw) > 300000:
                    raise ValueError('descriptor size limit')
                result = json.loads(raw)
                for source in (result.get('videoSources') or [])[:5]:
                    url = source.get('file', '')
                    if '.m3u8' in url.lower():
                        candidate(url, title, link, target)
        except Exception as exc:
            report['errors'].append({'directory': 'vipotv', 'target_hint': target,
                                     'error_type': type(exc).__name__})
    report['summary'] = {'directory_queries': len(QUERIES) + 1,
        'descriptors_resolved': resolutions, 'unique_safe_urls': len(report['candidates']),
        'previously_known_urls': sum(c['known_url'] for c in report['candidates']),
        'identity_verified': 0, 'media_validated': 0, 'promoted': 0}
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path('provider-research/report.json'))
    args = p.parse_args()
    # Missing exact baseline is a blocker; never pretend recycled links are new.
    baseline = json.loads(args.baseline.read_text())
    config = json.loads(Path('config.json').read_text())
    report = collect(baseline, config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['summary']))
    print('Discovery finished; no source is identity-verified, media-qualified or promoted.')


if __name__ == '__main__':
    main()
