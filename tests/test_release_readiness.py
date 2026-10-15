import copy
import json
from pathlib import Path
import unittest
from unittest import mock
import urllib.request

import release_readiness as release

ROOT = Path(__file__).resolve().parents[1]


class ReleaseReadinessTests(unittest.TestCase):
    def setUp(self):
        self.roster = json.loads((ROOT / 'research/v0.9.0-original-lineup.json').read_text())
        self.config = json.loads((ROOT / 'config.json').read_text())
        self.runs = []
        self.evidence = {}
        for n in range(1, 4):
            sha = str(n) * 40
            run = {'id': n, 'event': 'schedule', 'head_branch': 'main',
                   'path': release.WORKFLOW, 'head_sha': sha, 'run_attempt': 1,
                   'created_at': f'2026-10-15T0{n}:00:00Z',
                   'run_started_at': f'2026-10-15T0{n}:00:00Z',
                   'updated_at': f'2026-10-15T0{n}:40:00Z',
                   'status': 'completed', 'conclusion': 'success'}
            self.runs.append(run)
            channels = [{'tvg_id': k} for k in self.roster['channel_ids'][:95]]
            info = {'source_revision': sha, 'build_id': f'v0.7.0-test-{sha[:12]}',
                    'built_at': f'2026-10-15T0{n}:01:00Z', 'version': '0.7.0',
                    'workflow_run_id': str(n), 'workflow_run_attempt': '1'}
            status = {k: info[k] for k in ('source_revision', 'build_id', 'built_at')}
            status.update(addon_version='0.7.0', channels=95,
                          channel_logos={'normalized': 95, 'fallback': 0, 'failed': 0})
            rows, health = [], []
            for index, channel in enumerate(channels):
                url = f'https://media.example.test/{index}/index.m3u8'
                qa = {'passed': True, 'attempts': [{'passed': True,
                      'decoded_frames': 20, 'decoded_seconds': 10, 'repeat': None}]}
                rows.append({**channel, 'passing_index': 0, 'passing_qa': qa,
                             'attempts': [{'stream_index': 0, 'status': 'ok', 'url': url, 'qa': qa}]})
                health.append({**channel, 'url': url, 'health': {'status': 'ok'}})
            self.evidence[str(n)] = {'artifact': {'id': n + 100, 'expired': False,
                'workflow_run': {'id': n, 'head_sha': sha},
                'created_at': f'2026-10-15T0{n}:30:00Z'},
                'config': copy.deepcopy(self.config),
                'jobs': [{'name': 'build', 'conclusion': 'success', 'steps': [{
                    'name': 'Guard against channel coverage and identity regression',
                    'conclusion': 'success'}]}, {'name': 'deploy', 'conclusion': 'success'}],
                'files': {'status.json': status, 'diagnostics/build-info.json': info,
                          'diagnostics/channels.json': channels,
                          'diagnostics/primary-playback-qa.json': {'enabled': True,
                              'summary': {'channels_published': 95}, 'channels': rows},
                          'diagnostics/stream-health.json': health,
                          'diagnostics/logo-normalization.json': {}}}

    def report(self):
        return release.audit(self.runs, self.evidence, self.roster, 'main')

    def test_three_schedules_can_pass_automated_gate_without_approving_release(self):
        report = self.report()
        self.assertTrue(report['automated_schedule_gate_passed'], report)
        self.assertFalse(report['release_approved'])
        self.assertEqual([x['run_id'] for x in report['scheduled_attempts_newest_first']], [3, 2, 1])

    def test_manual_and_pr_builds_cannot_fill_window(self):
        for event in ('workflow_dispatch', 'pull_request', 'push'):
            with self.subTest(event=event):
                self.runs[0]['event'] = event
                self.assertFalse(self.report()['automated_schedule_gate_passed'])

    def test_failed_cancelled_or_running_schedule_breaks_streak(self):
        for status, conclusion in [('completed', 'failure'), ('completed', 'cancelled'), ('in_progress', None)]:
            self.runs[1].update(status=status, conclusion=conclusion)
            self.assertFalse(self.report()['automated_schedule_gate_passed'])

    def test_retry_is_not_independent_scheduled_success(self):
        self.runs[2]['run_attempt'] = 2
        self.assertFalse(self.report()['automated_schedule_gate_passed'])

    def test_other_workflow_and_branch_cannot_count(self):
        self.runs[0]['head_branch'] = 'staging'
        self.assertFalse(self.report()['automated_schedule_gate_passed'])
        self.runs[0]['head_branch'] = 'main'
        self.runs[0]['path'] = '.github/workflows/research.yml'
        self.assertFalse(self.report()['automated_schedule_gate_passed'])

    def test_missing_or_foreign_artifact_fails_closed(self):
        evidence = self.evidence.pop('3')
        self.assertFalse(self.report()['automated_schedule_gate_passed'])
        self.evidence['3'] = evidence
        evidence['artifact']['workflow_run']['id'] = 2
        self.assertFalse(self.report()['automated_schedule_gate_passed'])

    def test_stale_build_or_mismatched_sha_fails_closed(self):
        files = self.evidence['3']['files']
        files['status.json']['source_revision'] = 'a' * 40
        self.assertFalse(self.report()['automated_schedule_gate_passed'])

    def test_local_override_does_not_count_as_normal_decode(self):
        qa = self.evidence['3']['files']['diagnostics/primary-playback-qa.json']
        qa['channels'][0]['attempts'][0]['qa']['local_verified_override'] = True
        report = self.report()
        self.assertFalse(report['automated_schedule_gate_passed'])
        self.assertEqual(report['scheduled_attempts_newest_first'][0]['normal_decoded_original'], 94)

    def test_false_aggregate_decoder_pass_and_failed_health_do_not_count(self):
        files = self.evidence['3']['files']
        files['diagnostics/primary-playback-qa.json']['channels'][0]['attempts'][0]['qa']['attempts'][0]['decoded_frames'] = 0
        files['diagnostics/stream-health.json'][1]['health']['status'] = 'failed'
        self.assertEqual(self.report()['scheduled_attempts_newest_first'][0]['normal_decoded_original'], 93)

    def test_duplicate_channel_cannot_inflate_coverage(self):
        channels = self.evidence['3']['files']['diagnostics/channels.json']
        channels[-1] = channels[-2]
        self.assertFalse(self.report()['automated_schedule_gate_passed'])

    def test_west_foreign_affiliate_and_fast_substitution_do_not_count(self):
        for identity in ('Bravo.us@West', 'Fox.us@WNYW', 'USAFAST.us', 'NationalGeographicLatinAmerica.us'):
            with self.subTest(identity=identity):
                files = self.evidence['3']['files']
                files['diagnostics/channels.json'][-1] = {'tvg_id': identity}
                self.assertFalse(self.report()['automated_schedule_gate_passed'])

    def test_expanded_curation_or_weakened_qa_blocks(self):
        config = self.evidence['3']['config']
        config['curation']['national_allow'].append('ExtraFAST.us')
        self.assertFalse(self.report()['automated_schedule_gate_passed'])
        config['curation']['national_allow'].pop()
        config['stream_health']['primary_playback_qa']['detect_repeated_clips'] = False
        self.assertFalse(self.report()['automated_schedule_gate_passed'])

    def test_missing_deploy_guard_and_logos_fail_closed(self):
        self.evidence['3']['jobs'][1]['conclusion'] = 'skipped'
        self.assertFalse(self.report()['automated_schedule_gate_passed'])
        self.evidence['3']['jobs'][1]['conclusion'] = 'success'
        self.evidence['3']['files']['status.json']['channel_logos']['fallback'] = 1
        self.assertFalse(self.report()['automated_schedule_gate_passed'])

    def test_affiliate_key_preserved_and_east_quality_variants_supported(self):
        self.assertEqual(release.channel_key('NationalGeographic.us@HDEast'), 'nationalgeographic.us')
        self.assertEqual(release.channel_key('Fox.us@WTXFTV'), 'fox.us@wtxftv')
        self.assertNotEqual(release.channel_key('Fox.us@WNYW'), release.channel_key('Fox.us@WTXFTV'))
        self.assertNotEqual(release.channel_key('Bravo.us@West'), release.channel_key('Bravo.us@East'))

    def test_artifact_redirect_does_not_forward_api_bearer_token(self):
        request = urllib.request.Request('https://api.github.com/repos/owner/repo/actions/artifacts/1/zip',
                                         headers={'Authorization': 'Bearer test-only'})
        redirected = release.ArtifactRedirect().redirect_request(request, None, 302, 'Found', {},
                                                                  'https://storage.example.test/artifact.zip')
        self.assertFalse(redirected.has_header('Authorization'))

    def test_repository_api_root_uses_canonical_endpoint(self):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"default_branch":"main"}'
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.object(release.urllib.request, 'build_opener', return_value=opener):
            self.assertEqual(release.GitHub('owner/fork').get('')['default_branch'], 'main')
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.github.com/repos/owner/fork')


if __name__ == '__main__':
    unittest.main()
