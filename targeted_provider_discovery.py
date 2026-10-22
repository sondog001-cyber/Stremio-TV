"""Bounded missing-channel research. Never writes a production source or approves feeds."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import ipaddress
import json
from pathlib import Path
import re
import time
import urllib.parse as urlparse
import urllib.request

import build
import playlist_scrub as scrub
import provider_discovery as github

ROOT = Path(__file__).resolve().parent
PUBLIC = 'https://sondog001-cyber.github.io/Stremio-TV'
TOKEN_KEYS = {'st', 'e', 'exp', 'expires', 'expiry', 'token', 'access_token', 'signature',
              'sig', 'auth', 'authorization', 'jwt', 'hdnts', 'hdnea', 'hmac',
              'policy', 'key-pair-id'}
# Verified related delivery hosts, not assertions of independent infrastructure.
RELATED_HOSTS = {'instreams.xyz': 'instreams', 'instreams.live': 'instreams',
                 'instreams.pro': 'instreams', 'gate4.st': 'instreams',
                 'moveonjoy.com': 'moveonjoy'}
LABELS = {'USANetwork.us': ['USA Network'], 'CBSSportsNetwork.us': ['CBS Sports Network', 'CBSSN'],
          'HallmarkMystery.us': ['Hallmark Mystery', 'Hallmark Movies & Mysteries'],
          'StarzEncoreSpanish.us': ['Starz Encore Spanish', 'Starz Encore Español'],
          'NBCSportsPhiladelphiaPlus.us': ['NBC Sports Philadelphia Plus'],
          'RFDTV.us': ['RFD-TV']}
COUNTERS = ('search_results_reviewed', 'distinct_provider_leads', 'exact_channel_candidates',
            'manifest_and_segment_passes', 'sustained_decoder_passes',
            'identity_confirmed_feeds', 'staging_published_recoveries')


def canonical(value, config):
    value = str(value or '').strip()
    aliases = {k.lower(): v for k, v in config.get('curation', {}).get('canonical_id_aliases', {}).items()}
    seen = set()
    while value.lower() not in seen:
        seen.add(value.lower())
        # A West or distinct affiliate feed cannot satisfy an exact East/national target.
        if re.search(r'@west(?:hd|4k)?$', value, re.I):
            return value.lower()
        base = build.canonical_tvg_id(value)
        mapped = aliases.get(value.lower(), aliases.get(base.lower()))
        if mapped is None:
            return base.lower()
        value = mapped
    return value.lower()


def missing_targets(config, status, changes, channels, now):
    """Fail closed on absent, stale, inconsistent, or empty production snapshots."""
    stamp = dt.datetime.fromisoformat(status['built_at'].replace('Z', '+00:00'))
    if not dt.timedelta(0) <= now - stamp <= dt.timedelta(hours=24):
        raise ValueError('production snapshot must be no more than 24 hours old')
    if not channels or len(channels) != status['channels'] or changes['present_channels'] != len(channels):
        raise ValueError('inconsistent production snapshot')
    completed = dt.datetime.fromisoformat(changes['built_at'].replace('Z', '+00:00'))
    # source_state_built_at describes the PREVIOUS build, not this snapshot.
    if not dt.timedelta(0) <= completed - stamp <= dt.timedelta(minutes=90):
        raise ValueError('diagnostics and status come from different builds')
    roster = {}
    for group in ('philly_allow', 'national_allow'):
        for value in config['curation'][group]:
            value = build._desired_id(value, config['curation'])
            roster.setdefault(canonical(value, config), value)
    present = {canonical(x.get('tvg_id'), config) for x in channels}
    declared = {canonical(x['channel_id'], config)
                for kind in ('lost_this_build', 'still_missing') for x in changes[kind]}
    missing = set(roster) - present
    if missing != declared or len(missing) != changes['missing_channels']:
        raise ValueError('missing-channel diagnostics do not match curated production coverage')
    return [roster[k] for k in sorted(missing)]


def names(channel, config):
    stem = channel.split('.')[0]
    readable = re.sub(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', ' ', stem)
    aliases = [k for k in config.get('curation', {}).get('canonical_id_aliases', {})
               if canonical(k, config) == canonical(channel, config)]
    return list(dict.fromkeys([*LABELS.get(channel, []), readable, stem, channel, *aliases]))


def family(host):
    host = (host or '').lower().rstrip('.')
    for suffix, group in RELATED_HOSTS.items():
        if host == suffix or host.endswith('.' + suffix):
            return group
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        parts = host.split('.')
        n = 3 if '.'.join(parts[-2:]) in {'co.uk', 'com.au', 'co.nz', 'com.br'} else 2
        return '.'.join(parts[-n:])


def endpoint(url):
    """Token refreshes and mirrors do not manufacture a new channel source."""
    p = urlparse.urlsplit(url)
    query = sorted((k, v) for k, v in urlparse.parse_qsl(p.query)
                   if k.lower() not in TOKEN_KEYS)
    return [family(p.hostname), p.path, query]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def public_text(url):
    if not safe_document_url(url):
        raise ValueError('unsafe public document URL')
    class PublicRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not safe_document_url(newurl):
                raise ValueError('unsafe public document redirect')
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    request = urllib.request.Request(url, headers={'User-Agent': 'Stremio-TV-discovery',
                                                  'Accept-Encoding': 'identity'})
    with urllib.request.build_opener(PublicRedirect).open(request, timeout=8) as response:
        body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError('public document exceeds byte limit')
        return body.decode('utf-8', 'replace'), response.geturl()


def safe_document_url(url):
    path = urlparse.unquote(urlparse.urlsplit(url).path)
    parts = [p for p in path.split('/') if p]
    if len(parts) == 3 and re.fullmatch(r'\d+(?:\.[A-Za-z0-9]+)?', parts[-1]):
        return False  # Common prefix-free username/password/numeric-stream layout.
    return scrub.valid_public_url(url) and not re.search(
        r'/(?:play|stream)/[^/]+/[^/]+/\d+(?:\.[A-Za-z0-9]+)?$', path, re.I)


def player_evidence(text):
    """Track player delivery changes, excluding unrelated page text and token refreshes."""
    scripts = re.findall(r'<script[^>]+src=["\x27]([^"\x27]+)', text, re.I)
    scripts = [endpoint(u) for u in scripts if re.search(r'hls|player|clappr', u, re.I)]
    return digest(scripts)


def page_mentions(text, terms):
    title = re.search(r'<title[^>]*>(.*?)</title>', text, re.I | re.S)
    heading = re.findall(r'<h1[^>]*>(.*?)</h1>', text, re.I | re.S)
    label = html.unescape(re.sub('<[^>]+>', ' ', ' '.join(([title[1]] if title else []) + heading)))
    # Whole label boundaries prevent Starz from matching Starz Comedy, etc.
    label = re.sub(r'\s+', ' ', label).strip().lower()
    return any(re.search(r'(?<!\w)' + re.escape(n.lower()) + r'(?!\w)', label) for n in terms)


def entries_from_document(text, source, target, config):
    if '#EXTINF' in text:
        entries = build.parse_m3u(text, source)
    elif text.lstrip().startswith(('{', '[')) and source.get('channel_context') != target:
        entries = []
        try:
            def visit(value, depth=0):
                if depth > 5:
                    return
                if isinstance(value, list):
                    for child in value[:2000]:visit(child, depth + 1)
                elif isinstance(value, dict):
                    cid = value.get('tvg_id') or value.get('tvg-id') or value.get('id')
                    url = value.get('url') or value.get('stream_url') or value.get('hls')
                    if isinstance(cid, str) and isinstance(url, str) and re.search(r'\.m3u8(?:\?|$)', url):
                        entries.append({'tvg_id': cid, 'url': url, 'headers': {}})
                    for child in value.values():visit(child, depth + 1)
            visit(json.loads(text))
        except ValueError:
            return []
    else:
        # A titled public page is a declared-channel lead, never verified identity.
        if source.get('channel_context') != target and not page_mentions(text, names(target, config)):
            return []
        urls = re.findall(r'https?[^\s<>"\x27`]+\.m3u8(?:\?[^\s<>"\x27`\\]*)?',
                          html.unescape(text).replace('\\/', '/'))
        entries = [{'tvg_id': target, 'url': u, 'headers': {'Referer': source['url']}}
                   for u in dict.fromkeys(urls)]
    return [dict(e, tvg_id=target) for e in entries
            if canonical(e.get('tvg_id'), config) == canonical(target, config)]


def candidate(entry, source, old, now, known_families):
    key = digest([entry['tvg_id'], endpoint(entry['url'])])
    prior = old.get(key, {})
    # Relevant declaration only: an unrelated README edit is not new media evidence.
    evidence = digest([endpoint(entry['url']), entry.get('headers', {}),
                       source.get('player_evidence', '')])
    provenance = list(prior.get('provenance', []))
    attribution = {k: source[k] for k in ('url', 'repository', 'revision', 'pushed_at') if k in source}
    if attribution not in provenance:
        provenance.append(attribution)
    outcomes = prior.get('outcomes', [])
    failed_same_evidence = any(x.get('evidence') == evidence and
                               x.get('status') == 'failed' for x in outcomes)
    return dict(key=key, tvg_id=entry['tvg_id'], url=entry['url'], headers=entry.get('headers', {}),
                provider_family=endpoint(entry['url'])[0],
                unfamiliar_provider=endpoint(entry['url'])[0] not in known_families,
                first_seen=prior.get('first_seen', now.isoformat()), last_seen=now.isoformat(),
                evidence=evidence, outcomes=outcomes, provenance=provenance[-20:],
                needs_probe=not failed_same_evidence,
                identity_status='declared channel only; programming unverified', backup=False)


def prior_candidates(previous):
    """Also import existing scrub evidence, without treating old tests as current passes."""
    old = dict(previous.get('targeted_discovery', {}).get('candidates', {}))
    for row in previous.get('seen', {}).values():
        if not row.get('url') or not row.get('tvg_id'):
            continue
        key = digest([row['tvg_id'], endpoint(row['url'])])
        evidence = digest([endpoint(row['url']), row.get('headers', {}), ''])
        probe = row.get('probe') or {}
        health = probe.get('health', {})
        decoder = probe.get('decoder', {})
        status = ('failed' if 'failed' in {health.get('status'), decoder.get('status')}
                  else 'ok' if health.get('status') == decoder.get('status') == 'ok' else 'pending')
        outcome = {'evidence': evidence, 'tested_at': probe.get('tested_at'),
                   'status': status,
                   'health': health, 'decoder': decoder}
        old.setdefault(key, dict(row, outcomes=[outcome] if probe else []))
    return old


def discover(config, targets, baseline, previous, now, get=github.api_get,
             fetch=public_text, seconds=120, max_queries=3, max_repositories=6, max_documents=16):
    """Actual targeted searches and document inspection with bounded retained history."""
    started = time.monotonic()
    report = {k: 0 for k in COUNTERS}
    report.update(errors=[], queries=[], backup_candidates=0, probe_skipped_unchanged_failures=0,
                  provider_independence='grouped leads only; infrastructure independence unverified')
    state = previous.get('targeted_discovery', {})
    old = prior_candidates(previous)
    hints = state.get('project_hints', {})
    cursor = int(state.get('cursor', 0))
    current, repositories, documents = {}, set(), set()
    known = {family(urlparse.urlsplit(x.get('effective_url') or x.get('url') or '').hostname)
             for x in baseline}
    known.update(family(urlparse.urlsplit(x.get('url', '')).hostname)
                 for x in config.get('sources', {}).get('playlists', []))
    def budget():
        return time.monotonic() - started < seconds and len(documents) < max_documents
    def inspect(source, target, depth=0):
        u = source['url']
        if not budget() or (u, target) in documents:
            return
        documents.add((u, target))
        try:
            text, final = fetch(u)
            source = dict(source, url=final)
            if not safe_document_url(final):
                raise ValueError('unsafe document redirect')
            if source.get('channel_context') == target or page_mentions(text, names(target, config)):
                source['player_evidence'] = player_evidence(text)
            for e in entries_from_document(text, source, target, config):
                if not safe_document_url(e['url']) or not scrub.safe_entry(e, config, now):
                    continue
                row = candidate(e, source, old, now, known)
                if row['key'] in current:
                    row = candidate(e, source, {row['key']: current[row['key']]}, now, known)
                current[row['key']] = row
            if depth >= 2:
                return
            # Only links on channel-labelled lines or iframes on a labelled player.
            lines = [line for line in text.splitlines() if any(
                n.lower() in html.unescape(line).lower() for n in names(target, config))]
            links = []
            for line in lines:
                links.extend(re.findall(r'https?[^\s<>"\x27`)]+', line))
            if source.get('channel_context') == target or page_mentions(text, names(target, config)):
                links.extend(urlparse.urljoin(final, u) for u in re.findall(
                    r'<iframe[^>]+src=["\x27]([^"\x27]+)', text, re.I))
            for link in dict.fromkeys(links):
                if not budget():
                    break
                if link == final or re.search(r'\.(?:m3u8|mpd|png|jpg|svg)(?:\?|$)', link, re.I):
                    continue
                if safe_document_url(link):
                    inspect(dict(source, url=link, channel_context=target), target, depth + 1)
        except Exception as exc:
            report['errors'].append({'document': u.split('?')[0], 'type': type(exc).__name__})
    for offset in range(min(max_queries, len(targets) * 3)):
        if not budget() or not targets:
            break
        position = cursor + offset
        target = targets[(position // 3) % len(targets)]
        terms = names(target, config)
        rotation = position // max(1, len(targets) * 3)
        term = terms[(rotation * 2 + position % 3) % len(terms)] if position % 3 != 2 else target
        # GitHub repository search has no parenthesized boolean OR. Use one term.
        query = f'"{term}" in:name,description,readme fork:false archived:false'
        report['queries'].append({'target': target, 'query': query})
        try:
            result = get('search/repositories?' + urlparse.urlencode(
                {'q': query, 'sort': 'updated', 'order': 'desc', 'per_page': 12}))
            items = sorted(result.get('items', []), key=lambda x: x.get('pushed_at', ''), reverse=True)
            # Keep exploration slots; measured unfamiliar families improve later review priority.
            ranked = sorted(items, key=lambda x: hints.get(x.get('full_name'), 0), reverse=True)
            ordered = items[:2] + [x for x in ranked if x not in items[:2]]
            for repo in ordered:
                if not budget() or len(repositories) >= max_repositories:
                    break
                report['search_results_reviewed'] += 1
                name = str(repo.get('full_name', ''))
                if (not re.fullmatch(r'[\w.-]+/[\w.-]+', name) or repo.get('private')
                        or repo.get('fork') or repo.get('archived')):
                    continue
                if (name, target) in repositories:
                    continue
                repositories.add((name, target))
                branch = urlparse.quote(repo.get('default_branch', 'main'), safe='')
                # A Git tree SHA is not a raw-content revision. Pin a commit first.
                revision = get('repos/' + name + '/commits/' + branch)['sha']
                if not re.fullmatch(r'[A-Za-z0-9]+', revision):
                    raise ValueError('invalid upstream revision')
                tree = get('repos/' + name + '/git/trees/' + revision + '?recursive=1')
                paths = [x['path'] for x in tree.get('tree', []) if x.get('type') == 'blob'
                         and 0 < x.get('size', 0) <= 2_000_000
                         and re.search(r'\.(?:m3u8?|md|html?|json)$', x.get('path', ''), re.I)]
                paths.sort(key=lambda p: (not any(n.lower().replace(' ', '') in p.lower().replace(' ', '')
                                                for n in terms), not p.lower().endswith(('.m3u', '.m3u8')), p))
                for path in paths[:3]:
                    inspect({'url': 'https://raw.githubusercontent.com/' + name + '/' + revision + '/' +
                             urlparse.quote(path, safe='/'), 'repository': name,
                             'revision': revision, 'pushed_at': repo.get('pushed_at')}, target)
        except Exception as exc:
            report['errors'].append({'target': target, 'type': type(exc).__name__})
            if getattr(exc, 'code', None) in {401, 403, 429}:
                break
    rows = sorted(current.values(), key=lambda r: (not r['unfamiliar_provider'], r['provider_family'], r['tvg_id']))
    report.update(distinct_provider_leads=len({r['provider_family'] for r in rows}),
                  exact_channel_candidates=len(rows), documents_reviewed=len(documents),
                  repositories_reviewed=len(repositories),
                  probe_skipped_unchanged_failures=sum(not r['needs_probe'] for r in rows),
                  elapsed_seconds=round(time.monotonic() - started, 2))
    projects = {}
    for row in rows:
        for source in row['provenance']:
            if source.get('repository') and row['unfamiliar_provider']:
                projects.setdefault(source['repository'], set()).add(row['provider_family'])
    hints.update({repo: len(groups) for repo, groups in projects.items()})
    report['ranked_projects'] = sorted(hints.items(), key=lambda x: (-x[1], x[0]))[:100]
    retained = {**old, **current}
    retained = dict(sorted(retained.items(), key=lambda kv: kv[1].get('last_seen', ''), reverse=True)[:2000])
    return rows, {'cursor': cursor + len(report['queries']), 'candidates': retained,
                  'project_hints': dict(report['ranked_projects'])}, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot-dir', type=Path, help='Saved current published snapshot for replay')
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--out', type=Path, default=Path('targeted-provider-results'))
    parser.add_argument('--seconds', type=int, default=120, choices=range(0, 301), metavar='0..300')
    args = parser.parse_args()
    config = json.loads((ROOT / 'config.json').read_text())
    now = dt.datetime.now(dt.timezone.utc)
    snapshot = {}
    for name in ('status.json', 'channel-changes.json', 'channels.json', 'stream-health.json'):
        if args.snapshot_dir:
            text = (args.snapshot_dir / name).read_text()
        else:
            text, _ = public_text(PUBLIC + ('/' if name == 'status.json' else '/diagnostics/') + name)
        snapshot[name] = json.loads(text)
    if not args.snapshot_dir:
        after, _ = public_text(PUBLIC + '/status.json')
        if json.loads(after).get('build_id') != snapshot['status.json'].get('build_id'):
            raise ValueError('production changed while reading diagnostics; rerun with a fresh snapshot')
    targets = missing_targets(config, snapshot['status.json'], snapshot['channel-changes.json'],
                              snapshot['channels.json'], now)
    previous = json.loads(args.previous.read_text()) if args.previous else {}
    rows, state, report = discover(config, targets, snapshot['stream-health.json'], previous, now,
                                   seconds=args.seconds)
    report.update(advisory_only=True, production_build=snapshot['status.json']['built_at'],
                  targets=targets, candidates=rows, note='No media probes, identity approvals or promotions are performed.')
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'report.json').write_text(json.dumps(report, indent=2))
    (args.out / 'state.json').write_text(json.dumps({'targeted_discovery': state}, indent=2))
    print(json.dumps({k: report[k] for k in COUNTERS}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
