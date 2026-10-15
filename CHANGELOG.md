# Changelog

## 0.9.0 — unreleased draft

Release remains blocked. This section describes implemented engineering work;
it does not certify 95-channel coverage or stable playback.

- Add a read-only audit of actual scheduled production runs and their artifacts.
  Failed attempts remain in the three-build evidence window; manual and PR runs
  do not count. Local overrides are excluded from normal decoder coverage.
- Bind local approvals to each exact manual channel, URL, family and headers.
  Observed repeat, freeze and stall defects cannot use an override.
- Preserve underlying CI failures and match TVNow diagnostics by channel and URL.
- Add per-channel readiness evidence and protect staging with the existing
  production coverage and critical-identity guard.
- Document credential-free fork setup, local testing, source removal and rollback.
- Retain normalized channel logos and the refined FOX 29 wordmark.

Exact EPG mappings proposed in PR #118 remain pending validation/merge. Add them
here only after completion. Channel recoveries and final coverage must be written
from the final verified production artifacts before release.

## Configured baseline

The working addon configuration before this draft reports 0.7.0. No published
GitHub releases were returned by the repository releases API on 2026-10-15.
This does not establish that all historical development used a single version.
