import datetime as dt
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import provider_discovery as discovery
import playlist_scrub as scrub

NOW = dt.datetime(2026, 10, 18, tzinfo=dt.timezone.utc)


def repo(name='fresh/catalog', **kw):
    return {'full_name': name, 'default_branch': 'main', 'pushed_at': '2026-10-18T00:00:00Z', **kw}


class ProviderDiscoveryTests(unittest.TestCase):
    def test_new_catalogs_are_bounded_deduplicated_and_retained(self):
        calls = []
        def api(path):
            calls.append(path)
            if path.startswith('search/'):
                return {'items': [repo('known/list'), repo(), repo('skip/fork', fork=True)]}
            return {'tree': [
                {'type': 'blob', 'path': 'us.m3u', 'size': 500},
                {'type': 'blob', 'path': 'all.m3u8', 'size': 500},
                {'type': 'blob', 'path': 'other.m3u', 'size': 500},
                {'type': 'blob', 'path': 'run.py', 'size': 500},
                {'type': 'blob', 'path': 'large.m3u', 'size': 3_000_000}]}
        selected, state, report = discovery.discover({}, [
            {'url': 'https://raw.githubusercontent.com/known/list/main/us.m3u'}], NOW, api)
        self.assertEqual(report['repositories_inspected'], 1)
        self.assertEqual(report['new_playlist_documents'], 2)
        self.assertEqual(len(selected), 2)
        self.assertTrue(all(x['url'].startswith('https://raw.githubusercontent.com/fresh/catalog/') for x in selected))
        self.assertEqual(len(calls), 2)
        again, updated, replay = discovery.discover({'provider_discovery': state}, [{'url': 'https://raw.githubusercontent.com/known/list/main/us.m3u'}], NOW, api)
        self.assertEqual(replay['new_playlist_documents'], 0)
        self.assertEqual(len(again), 2)
        self.assertEqual(updated['cursor'], 2)
        self.assertNotEqual(report['query'], replay['query'])

    def test_missing_channel_search_rotates_with_broad_exploration(self):
        reports = []
        previous = {}
        for _ in range(4):
            _, state, report = discovery.discover(previous, [], NOW, lambda p: {},
                                                  missing_ids=["TeenNick.us", "CNBC.us"])
            reports.append(report)
            previous = {"provider_discovery": state}
        self.assertEqual(reports[0]["target_channel"], "CNBC.us")
        self.assertIn('"CNBC"', reports[0]["query"])
        self.assertIsNone(reports[2]["target_channel"])
        self.assertEqual(reports[3]["target_channel"], "TeenNick.us")

    def test_measured_host_priority_preserves_exploration_slots(self):
        catalogs = {f"https://raw.githubusercontent.com/o/r/main/{i:02}.m3u": {
            "url": f"https://raw.githubusercontent.com/o/r/main/{i:02}.m3u",
            "missing_unfamiliar_host_count": 3 if i == 19 else 0}
            for i in range(20)}
        selected, _, _ = discovery.discover({"provider_discovery": {"catalogs": catalogs}},
                                             [], NOW, lambda p: {})
        self.assertEqual(len(selected), 12)
        self.assertTrue(any(x["url"].endswith("19.m3u") for x in selected))
        self.assertEqual([x["url"] for x in selected[:6]], sorted(catalogs)[:6])

    def test_failed_search_preserves_retained_catalogs_and_advances_cursor(self):
        url = 'https://raw.githubusercontent.com/old/catalog/main/us.m3u'
        state = {'cursor': 8, 'catalogs': {url: {'url': url, 'discovered_at': NOW.isoformat()}}}
        def fail(path):
            raise urllib.error.HTTPError('https://api.github.com', 403, 'limited', {}, None)
        selected, updated, report = discovery.discover({'provider_discovery': state}, [], NOW, fail)
        self.assertEqual(selected[0]['url'], url)
        self.assertEqual(updated['cursor'], 9)
        self.assertEqual(report['stop_reason'], 'search-unavailable')
        self.assertEqual(report['new_playlist_documents'], 0)

    def test_repository_budget_and_time_budget(self):
        def api(path):
            return {'items': [repo(f'owner/r{i}') for i in range(30)]} if path.startswith('search/') else {'tree': []}
        _, _, report = discovery.discover({}, [], NOW, api)
        self.assertEqual(report['repositories_inspected'], 6)
        self.assertEqual(report['stop_reason'], 'repository-limit')
        _, _, report = discovery.discover({}, [], NOW, api, seconds=0)
        self.assertEqual(report['repositories_inspected'], 0)
        self.assertEqual(report['stop_reason'], 'discovery-time-budget')

    def test_catalog_rotation_does_not_keep_scanning_same_first_twelve(self):
        catalogs = {f'https://raw.githubusercontent.com/o/r/main/{i}.m3u': {
            'url': f'https://raw.githubusercontent.com/o/r/main/{i}.m3u'} for i in range(20)}
        selected, state, _ = discovery.discover({'provider_discovery': {'catalogs': catalogs}}, [], NOW, lambda p: {})
        again, _, _ = discovery.discover({'provider_discovery': state}, [], NOW, lambda p: {})
        self.assertEqual(len({x['url'] for x in selected + again}), 20)

    def test_api_token_only_goes_to_fixed_github_api_and_redirects_are_disabled(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return b'{"items": []}'
        with patch.dict('os.environ', {'GITHUB_TOKEN': 'test-secret'}), patch.object(
                discovery.urllib.request, 'build_opener') as opener:
            opener.return_value.open.return_value = Response()
            discovery.api_get('search/repositories?q=iptv')
            request = opener.return_value.open.call_args.args[0]
            self.assertTrue(request.full_url.startswith('https://api.github.com/'))
            self.assertEqual(request.get_header('Authorization'), 'Bearer test-secret')
            self.assertIs(opener.call_args.args[0], discovery.NoRedirect)
        with self.assertRaises(ValueError):
            discovery.api_get('https://attacker.invalid')

    def test_scrub_persists_discovery_and_scans_new_catalog_before_configured_lists(self):
        source = {'url': 'https://raw.githubusercontent.com/new/catalog/main/us.m3u', 'name': 'New'}
        state = {'cursor': 1, 'catalogs': {source['url']: source}}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            previous = Path(tmp) / 'previous.json'
            previous.write_text('{"version": 1, "seen": {}}')
            with patch('sys.argv', ['playlist_scrub.py', '--discover-providers', '--previous',
                                    str(previous), '--out', str(out)]), patch.dict(
                    'os.environ', {'GITHUB_STEP_SUMMARY': ''}), patch.object(
                    discovery, 'discover', return_value=([source], state, {
                        'repositories_inspected': 1, 'new_playlist_documents': 1})), patch.object(
                    scrub, 'scan_until_target', return_value=([], {'new_stream_links': 0})) as scan, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(scrub.main(), 0)
            self.assertEqual(scan.call_args.args[4][0], source)
            self.assertEqual(json.loads((out / scrub.STATE_FILE).read_text())['provider_discovery'], state)
            report = json.loads((out / 'playlist-scrub.json').read_text())
            self.assertEqual(report['summary']['new_playlist_documents'], 1)
            self.assertEqual(report['summary']['new_stream_links'], 0)
            self.assertEqual(report['summary']['promotions'], 0)


if __name__ == '__main__':
    unittest.main()
