#!/usr/bin/env python3
"""Read-only scheduled-production evidence audit. Never tags, merges or deploys.

Only the newest three scheduled attempts count; failed/cancelled attempts are
not skipped. Site-carried history and PR/manual builds cannot establish cadence.
An automated pass still requires programme identity and release review.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
from pathlib import Path
import re
import urllib.request
import zipfile

WORKFLOW = '.github/workflows/build-and-deploy.yml'
REQUIRED = ('DisneyChannel.us', 'NationalGeographic.us', 'History.us')
# Quality and national/East variants only. Keep affiliate suffixes and reject West.
VARIANTS = {'sd', 'hd', 'fhd', 'uhd', '4k', '720p', '1080p', '1440p',
            '2160p', 'east', 'easthd', 'hdeast', 'east4k', 'us', 'national', 'feed'}
FILES = ('status.json', 'diagnostics/build-info.json', 'diagnostics/channels.json',
         'diagnostics/primary-playback-qa.json', 'diagnostics/stream-health.json',
         'diagnostics/logo-normalization.json')


def channel_key(value):
    value = str(value or '').strip().lower()
    base, sep, variant = value.partition('@')
    return base if sep and variant in VARIANTS else value


def scheduled_window(runs, default_branch):
    unique = {r['id']: r for r in runs}
    selected = [r for r in unique.values() if r.get('event') == 'schedule'
                and r.get('head_branch') == default_branch
                and str(r.get('path', '')).split('@')[0] == WORKFLOW]
    # Run creation/ID, not completion time: a late retry cannot reorder cadence.
    return sorted(selected, key=lambda r: (r.get('created_at', ''), int(r['id'])),
                  reverse=True)[:3]


def policy_errors(config):
    h = config.get('stream_health') or {}
    burn = h.get('burn_in') or {}
    qa = h.get('primary_playback_qa') or {}
    direct = h.get('direct_media_survival') or {}
    errors = []
    if not all(h.get(k) is True for k in ('enabled', 'require_passed_only',
                                        'verify_segment_for_all_candidates', 'double_probe')):
        errors.append('normal upstream health/continuity requirements disabled')
    if not burn.get('enabled') or int(burn.get('duration_seconds', 0)) < 60 or not 0 < int(burn.get('interval_seconds', 0)) <= 15:
        errors.append('new-source five-probe 60-second burn-in weakened')
    if int(h.get('second_probe_delay_seconds', 0)) < 60:
        errors.append('established continuity window shortened')
    for label, settings, duration, minimum, attempts, passes in (
        ('primary', qa, 10, 8, 2, 1), ('direct', direct, 12, 10, 3, 2),
    ):
        if (not settings.get('enabled') or not settings.get('detect_repeated_clips')
                or int(settings.get('duration_seconds', 0)) < duration
                or int(settings.get('min_decoded_seconds', 0)) < minimum
                or int(settings.get('attempts', 0)) < attempts
                or int(settings.get('required_passes', 0)) < passes):
            errors.append(f'{label} decoder/repeat requirements weakened')
    guard = config.get('deployment_guard') or {}
    if not guard.get('enabled') or int(guard.get('minimum_channels', 0)) < 86:
        errors.append('established deployment floor weakened')
    if not {channel_key(x) for x in REQUIRED} <= {channel_key(x) for x in guard.get('required_channel_ids', [])}:
        errors.append('critical identity guard weakened')
    return errors


def assess_snapshot(run, evidence, roster):
    """Validate the original roster, run provenance, QA, and normal decoder count."""
    errors = []
    result = {'run_id': run['id'], 'url': run.get('html_url'),
              'source_revision': run.get('head_sha'), 'published_original': None,
              'normal_decoded_original': None, 'local_override_ids': [], 'errors': errors}
    if run.get('status') != 'completed' or run.get('conclusion') != 'success':
        errors.append('scheduled production attempt has not completed successfully')
        return result
    if int(run.get('run_attempt', 0)) != 1:
        errors.append('manual retry is not a fresh scheduled build')
    if not evidence:
        errors.append('run artifact/evidence unavailable')
        return result
    if evidence.get('error'):
        errors.append(evidence['error'])
        return result
    artifact = evidence['artifact']
    if (artifact.get('expired') or (artifact.get('workflow_run') or {}).get('id') != run['id']
            or (artifact.get('workflow_run') or {}).get('head_sha') != run.get('head_sha')):
        errors.append('artifact is expired or belongs to another run/revision')
    if artifact.get('created_at', '') < run.get('run_started_at', run.get('created_at', '')):
        errors.append('artifact predates this run attempt')
    jobs = evidence.get('jobs') or []
    for name in ('build', 'deploy'):
        if not any(j.get('name') == name and j.get('conclusion') == 'success' for j in jobs):
            errors.append(f'{name} job success not established')
    guard_step = 'Guard against channel coverage and identity regression'
    if not any(s.get('name') == guard_step and s.get('conclusion') == 'success'
               for j in jobs if j.get('name') == 'build' for s in j.get('steps', [])):
        errors.append('production guard step success not established')
    files = evidence['files']
    status = files['status.json']
    info = files['diagnostics/build-info.json']
    channels = files['diagnostics/channels.json']
    qa = files['diagnostics/primary-playback-qa.json']
    health = files['diagnostics/stream-health.json']
    for field in ('source_revision', 'build_id', 'built_at'):
        if not status.get(field) or status.get(field) != info.get(field):
            errors.append(f'build identity mismatch or missing: {field}')
    if not status.get('addon_version') or status.get('addon_version') != info.get('version'):
        errors.append('build identity mismatch or missing: addon version')
    if str(info.get('workflow_run_id')) != str(run['id']) or str(info.get('workflow_run_attempt')) != str(run.get('run_attempt')):
        errors.append('build provenance differs from scheduled run/attempt')
    if status.get('source_revision') != run.get('head_sha'):
        errors.append('status revision differs from scheduled run SHA')
    if not str(status.get('build_id', '')).endswith(str(run.get('head_sha', ''))[:12]):
        errors.append('build ID not bound to run SHA')
    if status.get('built_at', '') < run.get('run_started_at', run.get('created_at', '')) or status.get('built_at', '') > run.get('updated_at', ''):
        errors.append('build timestamp outside scheduled attempt')
    keys = [channel_key(c.get('tvg_id')) for c in channels]
    if len(keys) != len(set(keys)) or status.get('channels') != len(channels):
        errors.append('duplicate identities or inconsistent published count')
    original = {channel_key(x) for x in roster['channel_ids']}
    if roster.get('expected_count') != 111 or len(original) != 111:
        errors.append('original 111-channel roster is invalid')
    unexpected = set(keys) - original
    if unexpected:
        errors.append('non-original or wrong-feed identities: ' + ', '.join(sorted(unexpected)))
    present = set(keys) & original
    result['published_original'] = len(present)
    if not {channel_key(x) for x in REQUIRED} <= present:
        errors.append('critical original identities missing')
    config = evidence['config']
    errors.extend(policy_errors(config))
    configured = [*(config.get('curation') or {}).get('philly_allow', []),
                  *(config.get('curation') or {}).get('national_allow', [])]
    aliases = (config.get('curation') or {}).get('canonical_id_aliases') or {}
    if {channel_key(aliases.get(x, x)) for x in configured} != original:
        errors.append('configured curation differs from frozen original lineup')
    if not qa.get('enabled') or qa.get('summary', {}).get('channels_published') != len(channels):
        errors.append('final Primary QA disabled or publication count inconsistent')
    qmap = {}
    for q in qa.get('channels', []):
        k = channel_key(q.get('tvg_id'))
        if k in qmap:
            errors.append('duplicate channel in Primary QA evidence')
        qmap[k] = q
    normal = set()
    for k in present:
        q = qmap.get(k, {})
        index = q.get('passing_index')
        attempts = [a for a in q.get('attempts', []) if a.get('stream_index') == index
                    and index is not None and a.get('status') == 'ok']
        if len(attempts) != 1:
            continue
        a = attempts[0]
        detail = a.get('qa') or {}
        if detail.get('local_verified_override'):
            result['local_override_ids'].append(k)
            continue
        decoded = detail.get('attempts') or []
        # A claimed aggregate pass cannot substitute for actual frame evidence.
        if not detail.get('passed') or not any(t.get('passed') is True
                and float(t.get('decoded_seconds', 0)) >= 8
                and int(t.get('decoded_frames', 0)) >= 16
                and t.get('repeat') is None for t in decoded):
            continue
        reachable = any(channel_key(h.get('tvg_id')) == k and h.get('url') == a.get('url')
                        and (h.get('health') or {}).get('status') == 'ok'
                        and not (h.get('health') or {}).get('local_verified_override')
                        for h in health)
        if reachable:
            normal.add(k)
    result['normal_decoded_original'] = len(normal)
    result['unqualified_published_ids'] = sorted(present - normal)
    if len(normal) < 95:
        errors.append(f'only {len(normal)} original channels have normal health and decoded Primary QA; need 95')
    logos = status.get('channel_logos') or {}
    if logos.get('fallback') != 0 or logos.get('failed') != 0 or logos.get('normalized') != len(channels):
        errors.append('zero-fallback normalized logo gate not established')
    result['artifact_id'] = artifact['id']
    result['build_id'] = status.get('build_id')
    result['missing_original_ids'] = sorted(original - present)
    return result


def audit(runs, evidence_by_run, roster, default_branch):
    window = scheduled_window(runs, default_branch)
    rows = [assess_snapshot(r, evidence_by_run.get(str(r['id'])), roster) for r in window]
    errors = [] if len(window) == 3 else ['fewer than three scheduled production attempts available']
    gate = len(rows) == 3 and not errors and all(not r['errors'] for r in rows)
    return {'schema_version': 1, 'target': 'v0.9.0', 'minimum_original_channels': 95,
            'scheduled_attempts_required': 3, 'automated_schedule_gate_passed': gate,
            'release_approved': False, 'no_mutations': True, 'errors': errors,
            'manual_release_requirements': [
                'Exact full-linear US East/local programme identity and source provenance review',
                'Repeated stability, burn-in, cooldown, primary/backup promotion and no-loop review for new/replaced sources',
                'All remaining user release acceptance criteria and review before raising the floor/tagging'],
            'scheduled_attempts_newest_first': rows}


class ArtifactRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None:
            # GitHub's signed artifact storage URL needs no API bearer token.
            redirected.remove_header('Authorization')
        return redirected


class GitHub:
    def __init__(self, repository):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('expected owner/repository')
        self.repository = repository

    def get(self, path, binary=False):
        url = 'https://api.github.com/repos/' + self.repository + ('/' + path if path else '')
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'Stremio-TV-release-audit'}
        token = os.environ.get('GITHUB_TOKEN')
        if token:
            headers['Authorization'] = 'Bearer ' + token
        opener = urllib.request.build_opener(ArtifactRedirect)
        with opener.open(urllib.request.Request(url, headers=headers), timeout=30) as response:
            data = response.read(25_000_001)
        if len(data) > 25_000_000:
            raise ValueError('evidence response exceeds 25 MB')
        return data if binary else json.loads(data)

    def collect(self):
        branch = self.get('')['default_branch']
        runs = []
        for page in range(1, 11):
            batch = self.get('actions/runs?event=schedule&per_page=100&page=' + str(page))['workflow_runs']
            runs.extend(batch)
            if len(scheduled_window(runs, branch)) >= 3 or len(batch) < 100:
                break
        evidence = {}
        for run in scheduled_window(runs, branch):
            if run.get('status') != 'completed' or run.get('conclusion') != 'success':
                continue
            try:
                artifacts = self.get(f"actions/runs/{run['id']}/artifacts?per_page=100")['artifacts']
                matches = [a for a in artifacts if a['name'] == 'stremio-tv-diagnostics' and not a['expired']]
                if len(matches) != 1:
                    raise ValueError('exactly one unexpired diagnostics artifact required')
                artifact = matches[0]
                raw = self.get(f"actions/artifacts/{artifact['id']}/zip", binary=True)
                files = {}
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    for name in FILES:
                        member = archive.getinfo(name)
                        if member.file_size > 20_000_000:
                            raise ValueError('uncompressed diagnostic exceeds size limit')
                        files[name] = json.loads(archive.read(member))
                config_file = self.get('contents/config.json?ref=' + run['head_sha'])
                config = json.loads(base64.b64decode(config_file['content']))
                jobs = self.get(f"actions/runs/{run['id']}/jobs?filter=latest&per_page=100")['jobs']
                evidence[str(run['id'])] = {'artifact': artifact, 'jobs': jobs, 'files': files, 'config': config}
            except Exception as exc:
                # Never include request headers, authorization, or signed download URLs.
                evidence[str(run['id'])] = {'error': 'could not verify artifact: ' + type(exc).__name__}
        return {'runs': runs, 'evidence_by_run': evidence, 'default_branch': branch}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', default=os.environ.get('GITHUB_REPOSITORY'))
    parser.add_argument('--evidence-index', type=Path, help='Offline captured API/artifact input')
    parser.add_argument('--roster', type=Path, default=Path(__file__).parent / 'research/v0.9.0-original-lineup.json')
    parser.add_argument('--output', type=Path, default=Path('release-audit'))
    args = parser.parse_args()
    data = json.loads(args.evidence_index.read_text()) if args.evidence_index else GitHub(args.repository or '').collect()
    report = audit(data['runs'], data['evidence_by_run'], json.loads(args.roster.read_text()), data['default_branch'])
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'v0.9.0-release-readiness.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# v0.9.0 scheduled-production evidence', '',
             '**Automated schedule gate: ' + ('PASS' if report['automated_schedule_gate_passed'] else 'BLOCKED') + '**. Release approval still requires programme identity and acceptance review.', '',
             '| Scheduled run | Original published | Normal decoded | Blockers |', '|---|---:|---:|---|']
    for row in report['scheduled_attempts_newest_first']:
        published = row['published_original'] if row['published_original'] is not None else 'unassessed'
        normal = row['normal_decoded_original'] if row['normal_decoded_original'] is not None else 'unassessed'
        lines.append(f"| {row['run_id']} | {published} | {normal} | {'; '.join(row['errors']) or 'none'} |")
    lines += ['', *report['errors'], '', 'Manual/PR builds and carried site history do not count. No tags, releases, merges, floor changes or deployments are performed.']
    text = '\n'.join(lines) + '\n'
    (args.output / 'v0.9.0-release-readiness.md').write_text(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
            summary.write(text)
    print(text)
    # A blocked release is a valid audit result, not a production workflow failure.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
