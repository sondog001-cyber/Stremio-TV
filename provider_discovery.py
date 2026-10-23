"""Bounded public GitHub catalog discovery. Reads data only; never promotes feeds."""
import datetime as dt
import json
import os
import re
import time
import urllib.parse
import urllib.request

QUERIES = (
    'iptv playlist USA fork:false archived:false',
    'iptv m3u channels fork:false archived:false',
    'live television playlist fork:false archived:false',
    'iptv scraper fork:false archived:false',
    'iptv sports playlist fork:false archived:false',
    'iptv United States fork:false archived:false',
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        # Never forward the Actions token to a redirected host.
        return None


def api_get(path):
    if not path.startswith(('search/repositories?', 'repos/')):
        raise ValueError('unsupported discovery endpoint')
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'Stremio-TV-discovery'}
    if os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    request = urllib.request.Request('https://api.github.com/' + path, headers=headers)
    with urllib.request.build_opener(NoRedirect).open(request, timeout=8) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('discovery response exceeds limit')
    return json.loads(raw)


def repository_of(url):
    p = urllib.parse.urlsplit(url)
    parts = p.path.strip('/').split('/')
    if p.hostname in {'github.com', 'raw.githubusercontent.com'} and len(parts) >= 2:
        return '/'.join(parts[:2]).lower()
    return None


def discover(previous, configured, now, get=api_get, seconds=120, missing_ids=()):
    """Rotate search/page and retained catalogs across runs, including empty searches.

    Repository discovery is a lead, not evidence of a new independent media origin.
    API failures preserve history and are reported rather than blocking deployment.
    """
    started = time.monotonic()
    state = previous.get('provider_discovery') or {}
    cursor = int(state.get('cursor', 0))
    missing = sorted(set(missing_ids))
    target = missing[(cursor // 3) % len(missing)] if missing and cursor % 3 != 2 else None
    # Two targeted runs, then one broad run: avoid permanently narrowing discovery.
    if target:
        name = re.sub(r"[^A-Za-z0-9 ]", " ", target.split(".")[0])
        query = f'"{name}" iptv in:name,description,readme fork:false archived:false'
        page = 1
    else:
        query = QUERIES[(cursor // 3 if missing else cursor) % len(QUERIES)]
        page = 1 + (cursor // len(QUERIES)) % 5
    stamp = now.isoformat()
    catalogs = dict(state.get('catalogs') or {})
    checked = dict(state.get('checked_repositories') or {})
    known_urls = {s['url'] for s in configured}
    known_repos = {repository_of(u) for u in known_urls}
    report = {'query': query, 'target_channel': target, 'missing_channel_count': len(missing), 'page': page, 'repositories_inspected': 0,
              'new_playlist_documents': 0, 'errors': [], 'stop_reason': 'search-exhausted'}
    try:
        result = get('search/repositories?' + urllib.parse.urlencode(
            {'q': query, 'sort': 'updated', 'order': 'desc', 'per_page': 30, 'page': page}))
        for repo in result.get('items', []):
            if time.monotonic() - started >= seconds:
                report['stop_reason'] = 'discovery-time-budget'
                break
            if report['repositories_inspected'] >= 6:
                report['stop_reason'] = 'repository-limit'
                break
            name = str(repo.get('full_name', ''))
            branch = str(repo.get('default_branch', ''))
            if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', name)
                    or not branch or repo.get('private') or repo.get('fork') or repo.get('archived')
                    or name.lower() in known_repos):
                continue
            # A changed upstream revision or seven days makes an inspected repo eligible again.
            old = checked.get(name.lower(), {})
            if old.get('pushed_at') == repo.get('pushed_at') and old.get('checked_at', '') > (
                    now - dt.timedelta(days=7)).isoformat():
                continue
            report['repositories_inspected'] += 1
            try:
                tree = get('repos/' + name + '/git/trees/' + urllib.parse.quote(branch, safe='') + '?recursive=1')
                paths = [r['path'] for r in tree.get('tree', [])
                         if r.get('type') == 'blob' and 0 < r.get('size', 0) <= 2_000_000
                         and re.search(r'\.(?:m3u|m3u8)$', r.get('path', ''), re.I)]
                # Prefer national/general lists; exact-ID matching later rejects other regions.
                paths.sort(key=lambda p: (not bool(re.search(r'usa?|united|all|playlist|index', p, re.I)), p))
                for path in paths[:2]:
                    url = ('https://raw.githubusercontent.com/' + name + '/' +
                           urllib.parse.quote(branch, safe='') + '/' + urllib.parse.quote(path, safe='/'))
                    if url in known_urls or url in catalogs:
                        continue
                    catalogs[url] = {'name': 'Discovered: ' + name + '/' + path,
                                     'url': url, 'format': 'm3u',
                                     'family': 'discovered-public-catalog',
                                     'repository': name, 'discovered_at': stamp}
                    report['new_playlist_documents'] += 1
                checked[name.lower()] = {'pushed_at': repo.get('pushed_at'), 'checked_at': stamp}
                if tree.get('truncated'):
                    report['errors'].append({'repository': name, 'type': 'truncated-tree'})
            except Exception as exc:
                report['errors'].append({'repository': name, 'type': type(exc).__name__})
                if getattr(exc, 'code', None) in {403, 429}:
                    report['stop_reason'] = 'api-rate-or-access-limit'
                    break
    except Exception as exc:
        report['errors'].append({'type': type(exc).__name__})
        report['stop_reason'] = 'search-unavailable'
    # Keep a bounded history; take the least recently scanned twelve next.
    catalogs = dict(sorted(catalogs.items(), key=lambda x: x[1].get('discovered_at', ''), reverse=True)[:128])
    available = [v for u, v in catalogs.items() if u not in known_urls]
    # Reserve half the catalog slots for exploration so past winners cannot starve
    # unscanned projects. Rank the remainder by measured safe missing-channel hosts.
    exploration = sorted(available, key=lambda x: (x.get('last_scan', ''), x['url']))[:6]
    chosen = {x['url'] for x in exploration}
    promising = sorted((x for x in available if x['url'] not in chosen),
                       key=lambda x: (-x.get('missing_unfamiliar_host_count', 0),
                                      x.get('last_scan', ''), x['url']))[:12-len(exploration)]
    selected = exploration + promising
    for row in selected:
        catalogs[row['url']] = {**row, 'last_scan': stamp}
    checked = dict(sorted(checked.items(), key=lambda x: x[1].get('checked_at', ''), reverse=True)[:500])
    report.update(retained_playlist_documents=len(catalogs), selected_playlist_documents=len(selected),
                  elapsed_seconds=round(time.monotonic() - started, 2))
    return selected, {'cursor': cursor + 1, 'catalogs': catalogs,
                      'checked_repositories': checked}, report
