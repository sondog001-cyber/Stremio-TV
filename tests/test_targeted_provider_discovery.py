import copy
import datetime as dt
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import targeted_provider_discovery as discovery

NOW = dt.datetime(2026, 10, 22, 14, tzinfo=dt.timezone.utc)
CONFIG = {'curation': {'philly_allow': ['Fox.us@WTXFTV'],
                      'national_allow': ['USANetwork.us', 'CBSSportsNetwork.us', 'MSNOW.us'],
                      'canonical_id_aliases': {'MSNBC.us': 'MSNOW.us', 'CBS.Sports.Network.USA.us': 'CBSSportsNetwork.us'}},
          'sources': {'playlists': []}}


def snapshot():
    status = {'built_at': '2026-10-22T13:30:00Z', 'channels': 2}
    changes = {'built_at': '2026-10-22T13:50:00Z', 'source_state_built_at': '2026-10-22T07:00:00Z',
               'present_channels': 2, 'missing_channels': 2,
               'lost_this_build': [{'channel_id': 'USANetwork.us'}],
               'still_missing': [{'channel_id': 'CBS.Sports.Network.USA.us'}]}
    channels = [{'tvg_id': 'MSNBC.us@HD'}, {'tvg_id': 'Fox.us@WTXFTV'}]
    return status, changes, channels


class TargetSelectionTests(unittest.TestCase):
    def test_current_missing_only_aliases_and_affiliates(self):
        status, changes, channels = snapshot()
        self.assertEqual(discovery.missing_targets(CONFIG, status, changes, channels, NOW),
                         ['CBSSportsNetwork.us', 'USANetwork.us'])
        self.assertNotEqual(discovery.canonical('Fox.us@OTHER', CONFIG),
                            discovery.canonical('Fox.us@WTXFTV', CONFIG))
        self.assertNotEqual(discovery.canonical('USANetwork.us@West', CONFIG),
                            discovery.canonical('USANetwork.us', CONFIG))

    def test_missing_stale_or_inconsistent_diagnostics_fail_closed(self):
        for change in ('stale', 'count', 'ids', 'timestamp', 'empty'):
            s, c, rows = snapshot()
            rows[0]['tvg_id'] = 'MSNBC.us'
            if change == 'stale': s['built_at'] = '2026-10-20T13:30:00Z'
            if change == 'count': s['channels'] = 3
            if change == 'ids': c['still_missing'] = []
            if change == 'timestamp': c['built_at'] = '2026-10-22T07:00:00Z'
            if change == 'empty': rows = []
            with self.subTest(change=change), self.assertRaises(ValueError):
                discovery.missing_targets(CONFIG, s, c, rows, NOW)


class DiscoveryTests(unittest.TestCase):
    def api(self, path):
        if path.startswith('search/'):
            return {'items': [{'full_name': 'fresh/catalog', 'default_branch': 'main',
                               'pushed_at': '2026-10-22T12:00:00Z'}]}
        if '/commits/' in path:
            return {'sha': 'abc123'}
        return {'sha': 'tree456', 'tree': [{'path': 'us.m3u', 'type': 'blob', 'size': 100}]}

    def playlist(self, url):
        return ('#EXTM3U\n#EXTINF:-1 tvg-id="USANetwork.us",USA Network\n'
                'https://a.newmedia.example/usa/index.m3u8?st=abcdefghijklmnop&e=1999999999\n'
                '#EXTINF:-1 tvg-id="ESPN.us",ESPN\nhttps://other.example/espn.m3u8\n', url)

    def run_discovery(self, previous=None, fetch=None, targets=None, **kwargs):
        with patch.object(discovery.scrub, 'safe_entry', return_value=True):
            return discovery.discover(CONFIG, targets or ['USANetwork.us'], [], previous or {}, NOW,
                                      get=self.api, fetch=fetch or self.playlist, **kwargs)

    def test_real_target_queries_and_exact_filtering(self):
        rows, state, report = self.run_discovery()
        self.assertEqual({r['tvg_id'] for r in rows}, {'USANetwork.us'})
        self.assertIn('"USA Network"', report['queries'][0]['query'])
        self.assertIn('"USANetwork.us"', report['queries'][2]['query'])
        self.assertEqual(report['distinct_provider_leads'], 1)
        self.assertEqual(report['exact_channel_candidates'], 1)
        self.assertTrue(rows[0]['unfamiliar_provider'])
        self.assertEqual(rows[0]['provenance'][0]['revision'], 'abc123')
        self.assertIn('/abc123/us.m3u', rows[0]['provenance'][0]['url'])
        self.assertNotIn('/tree456/', rows[0]['provenance'][0]['url'])
        self.assertEqual(state['cursor'], 3)

    def test_alias_queries_rotate_beyond_first_names(self):
        reports = []
        previous = {}
        for _ in range(3):
            _, state, report = self.run_discovery(previous, targets=['CBSSportsNetwork.us'])
            reports.extend(x['query'] for x in report['queries'])
            previous = {'targeted_discovery': state}
        self.assertTrue(any('CBSSN' in q for q in reports))
        self.assertTrue(any('CBS.Sports.Network.USA.us' in q for q in reports))

    def test_mirrors_and_tokens_group_without_inflating_source_count(self):
        self.assertEqual(discovery.endpoint('https://instreams.pro/live3/F191/index.m3u8?st=aaa&e=1'),
                         discovery.endpoint('https://instreams.xyz/live3/F191/index.m3u8?st=bbb&e=2'))
        self.assertEqual(discovery.family('gate4.st'), discovery.family('instreams.live'))
        for token in ('access_token', 'hdnea', 'hmac', 'jwt'):
            self.assertEqual(discovery.endpoint('https://a.example/usa.m3u8?' + token + '=old'),
                             discovery.endpoint('https://a.example/usa.m3u8?' + token + '=new'))
        text = ('#EXTM3U\n#EXTINF:-1 tvg-id="USANetwork.us",USA\n'
                'https://instreams.pro/live3/F191/index.m3u8?st=aaa&e=1999999999\n'
                '#EXTINF:-1 tvg-id="USANetwork.us",USA\n'
                'https://instreams.xyz/live3/F191/index.m3u8?st=bbb&e=1999999999\n')
        rows, _, report = self.run_discovery(fetch=lambda u: (text, u))
        self.assertEqual(len(rows), 1)
        self.assertEqual(report['distinct_provider_leads'], 1)
        self.assertNotEqual(discovery.endpoint('https://a.example/live?id=1'),
                            discovery.endpoint('https://a.example/live?id=2'))

    def test_failure_history_survives_and_token_rotation_does_not_reset_it(self):
        rows, state, _ = self.run_discovery()
        row = rows[0]
        row['outcomes'] = [{'evidence': row['evidence'], 'status': 'failed', 'tested_at': NOW.isoformat()}]
        changed = lambda u: (self.playlist(u)[0].replace('abcdefghijklmnop', 'otherpublictoken'), u)
        replay, _, report = self.run_discovery({'targeted_discovery': state}, fetch=changed)
        self.assertFalse(replay[0]['needs_probe'])
        self.assertEqual(report['probe_skipped_unchanged_failures'], 1)
        material = lambda u: (self.playlist(u)[0].replace('/usa/', '/usa-new/'), u)
        revised, _, _ = self.run_discovery({'targeted_discovery': state}, fetch=material)
        self.assertTrue(revised[0]['needs_probe'])

    def test_scrub_failure_import_does_not_turn_into_current_pass(self):
        e = {'tvg_id': 'USANetwork.us', 'url': 'https://fresh.example/a.m3u8', 'headers': {},
             'probe': {'tested_at': NOW.isoformat(), 'health': {'status': 'failed'}}}
        old = discovery.prior_candidates({'seen': {'old': e}})
        row = discovery.candidate(e, {'url': 'https://page.example/watch'}, old, NOW, set())
        self.assertFalse(row['needs_probe'])
        self.assertEqual(len(row['outcomes']), 1)
        e['probe']['health']['status'] = 'ok'
        old = discovery.prior_candidates({'seen': {'old': e}})
        row = discovery.candidate(e, {'url': 'https://page.example/watch'}, old, NOW, set())
        self.assertTrue(row['needs_probe'])
        self.assertEqual(row['outcomes'][0]['status'], 'pending')

    def test_public_player_following_is_bounded_and_never_executes_scripts(self):
        def fetch(url):
            if url.endswith('.m3u'):return ('USA Network https://player.example/watch', url)
            return ('<title>USA Network Live</title><script>location.href="/login";</script>'
                    'file="https://delivery.example/live.m3u8"', url)
        rows, _, report = self.run_discovery(fetch=fetch)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['headers']['Referer'], 'https://player.example/watch')
        self.assertEqual(report['documents_reviewed'], 2)

    def test_reporting_never_promotes_document_or_id_matches(self):
        _, _, report = self.run_discovery()
        for k in ('manifest_and_segment_passes', 'sustained_decoder_passes',
                  'identity_confirmed_feeds', 'staging_published_recoveries', 'backup_candidates'):
            self.assertEqual(report[k], 0)

    def test_structured_json_requires_exact_id_not_display_name(self):
        text = json.dumps({'channels': [
            {'tvg_id': 'USANetwork.us', 'url': 'https://a.example/usa.m3u8'},
            {'name': 'USA Network', 'url': 'https://b.example/name-only.m3u8'},
            {'tvg_id': 'ESPN.us', 'url': 'https://c.example/espn.m3u8'}]})
        rows, _, _ = self.run_discovery(fetch=lambda u: (text, u))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['url'], 'https://a.example/usa.m3u8')

    def test_player_change_is_material_but_unrelated_text_is_not(self):
        original = '<title>USA Network</title><script src="https://cdn.example/hls-v1.js"></script>'
        same = original + '<p>A new advertisement</p>'
        self.assertEqual(discovery.player_evidence(original), discovery.player_evidence(same))
        changed = original.replace('hls-v1.js', 'hls-v2.js')
        self.assertNotEqual(discovery.player_evidence(original), discovery.player_evidence(changed))
        entry = {'tvg_id': 'USANetwork.us', 'url': 'https://a.example/usa.m3u8'}
        source = {'url': 'https://watch.example/', 'player_evidence': discovery.player_evidence(original)}
        row = discovery.candidate(entry, source, {}, NOW, set())
        row['outcomes'] = [{'evidence': row['evidence'], 'status': 'failed'}]
        source['player_evidence'] = discovery.player_evidence(changed)
        revised = discovery.candidate(entry, source, {row['key']: row}, NOW, set())
        self.assertTrue(revised['needs_probe'])

    def test_account_shaped_player_routes_are_rejected(self):
        self.assertFalse(discovery.safe_document_url('https://a.example/play/user/pass/123.m3u8'))
        self.assertFalse(discovery.safe_document_url('https://a.example/stream/user/pass/123'))
        self.assertFalse(discovery.safe_document_url('https://a.example/user/pass/123.m3u8'))
        self.assertFalse(discovery.safe_document_url('http://127.0.0.1/live'))
        self.assertTrue(discovery.safe_document_url('https://a.example/player?id=public'))

    def test_no_name_only_playlist_matching_or_west_substitution(self):
        text = ('#EXTM3U\n#EXTINF:-1 tvg-id="",USA Network\nhttps://a.example/a.m3u8\n'
                '#EXTINF:-1 tvg-id="USANetwork.us@West",USA Network\nhttps://a.example/w.m3u8\n')
        rows, _, _ = self.run_discovery(fetch=lambda u: (text, u))
        self.assertEqual(rows, [])

    def test_alias_playlist_id_matches_the_exact_target(self):
        text = ('#EXTM3U\n#EXTINF:-1 tvg-id="CBS.Sports.Network.USA.us",CBS Sports Network\n'
                'https://a.example/cbssn.m3u8\n')
        rows, _, _ = self.run_discovery(fetch=lambda u: (text, u), targets=['CBSSportsNetwork.us'])
        self.assertEqual(rows[0]['tvg_id'], 'CBSSportsNetwork.us')

    def test_zero_budget_or_no_targets_never_search(self):
        calls = []
        for targets, seconds in [([], 120), (['USANetwork.us'], 0)]:
            rows, _, report = discovery.discover(CONFIG, targets, [], {}, NOW,
                get=lambda p: calls.append(p), seconds=seconds)
            self.assertEqual(rows, [])
        self.assertEqual(calls, [])

    def test_api_failure_preserves_history(self):
        rows, state, _ = self.run_discovery()
        def fail(path):raise OSError('offline')
        _, retained, report = discovery.discover(CONFIG, ['USANetwork.us'], [],
            {'targeted_discovery': state}, NOW, get=fail)
        self.assertEqual(set(retained['candidates']), set(state['candidates']))
        self.assertTrue(report['errors'])


if __name__ == '__main__':
    unittest.main()
