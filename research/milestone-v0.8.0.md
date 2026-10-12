# Milestone v0.8.0 — Reliability before expansion

Current stable deployment version: **v0.7.0**. Do not increment the manifest version until the milestone is validated. No changes in this milestone may weaken direct-upstream playback, content identity, access restrictions, local-verified policy, per-channel/URL kill switches, or normal decoder QA.

## Measurable starting point (2026-10-12)

From Actions run 38264295646: 88/111 curated channels published, 128 streams, 58 single-stream channels, 27 with distinct-host alternatives (an estimate, not proof of upstream independence), 81/88 EPG matches, 10 experimental Local Test channels containing 22 streams. Final playback QA reported 88/88; normal decoder and locally overridden attempts must remain separately reported.

## Workstreams

1. **Monitor regressions automatically.** The read-only watchdog emits an Actions summary and site/diagnostics/v08-reliability-watchdog.json. Its thresholds are *warnings*, not deployment controls; a first fork build with no history is valid.
2. **Eliminate repeat, stall and decoder failures.** Use five-build reliability data and actual Stremio reports, not HLS HTTP status, to make decisions. Re-test after any probe or source-selection change.
3. **Protect vulnerable published channels.** Prioritize single-stream sports, Discovery/FX/HGTV/TLC family, Philadelphia locals and concentrated provider hosts using resilience-hunt-queue.json. Different hostnames alone do not prove independence.
4. **Recover missing exact IDs.** Keep private-connector-only IDs out of the public hunt. Reject FAST stand-ins, unlicensed rebroadcast, DRM/access bypass and URLs containing private credentials.
5. **Gather local playback confirmations.** Preserve explicit local-verified overrides without claiming these are GitHub-runner decoder passes. Record app/platform, source ID, continuous playback outcome and repetition defects.
6. **Observe several consecutive builds.** Avoid promoting a source based on one passing probe; release only after stability is demonstrated.

## Exit criteria proposed for v0.8.0

- Repeated production runs deploy without catastrophic coverage regressions; any large drop is investigated and fixed.
- No known reproducible 2–4-second looping defects remain in the tested primary lineup.
- High-blast-radius host/provider dependencies and single-stream channels are documented and prioritized for independent backups.
- Normal decoder results and local overrides are transparently separated in reports.
- Local client testing is completed for the highest-priority override channels (cannot be asserted from Actions).
- Repository unit tests and PR checks are passing; preserve ability to roll back.

v0.8.0 is a reliability milestone, not a promise of 111 accessible channels. See the existing private connector and authorization policies in README.md.
