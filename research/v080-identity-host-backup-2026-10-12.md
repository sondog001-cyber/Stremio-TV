# v0.8.0 — Exact ID continuity and independent backup triage (2026-10-12)

**Production policy:** Keep the current 88-channel lineup and stream selections untouched. This report compares already downloaded GitHub Actions diagnostics; it does not establish a new playable or licensed source.

## Why Disney Channel and National Geographic changed published `tvg_id`

Compared run [38264295646](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38264295646) (128 streams) with [38269371687](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38269371687) (121 streams):

| Logical channel | Old public `tvg_id` | New public `tvg_id` | Stable internal channel ID | Old/new streams |
|---|---|---|---|---|
| Disney Channel | `DisneyChannel.us` | `DisneyChannel.us@East` | `stremiotv_94bf3af642e76c` | 3 -> 1 |
| National Geographic | `NationalGeographic.us` | `NationalGeographic.us@East` | `stremiotv_f1325fe734eba1` | 3 -> 1 |

The catalog IDs and EPG matches **did not change**. The merge algorithm chooses the base `tvg_id` if a passing source carries that literal ID; when the base entry disappears, it falls back to the variant ID. This is metadata drift **rather than a different catalog channel**.

The preceding run's `stream-health.json` contained 27 candidates labeled `DisneyChannel.us` and 24 labeled `NationalGeographic.us`; the later run contained **zero** for either base ID while retaining their IPTV-org `@East` streams. Therefore the missing base-ID sources were **not tested and failed in that later run**; they were not in its candidate set.

The targeted source-scanner summary shows the underlying discovery feedback: its national target set changed **32 -> 30**, dropping exactly `DisneyChannel.us` and `NationalGeographic.us`. In `_target_ids_for_source_hunt`, a channel with any current candidate and a previously-present state is not targeted; the available IPTV-org `@East` streams were sufficient to stop subsequent backup-family scans. This is a *coverage-based discovery blind spot*, **not proof** that the previously working base-ID feeds are still healthy.

### Safe identity fix in this PR

- Pin **only** curated public IDs `DisneyChannel.us` and `NationalGeographic.us`, and only when the entire logical bucket canonicalizes to that exact channel.
- Leave upstream stream-level `tvg_id`, HLS URL, decoder QA, favorites, source order, local override status, stream health and internal catalog ID **unchanged**.
- Do not strip affiliate-specific suffixes: `Fox.us@WTXFTV` is **not** a generic `Fox.us` channel.
- Do not automatically resurrect excluded or stale providers. A separate later change to scanner retention should be reviewed independently and exercised against QA before enabling it in production.

## Host exposure — first two independent-backup hunt clusters

The **last completed** build's `host-redundancy.json` reports:

| Observed media host | Published channels using host | Channels lacking a distinct-host alternative |
|---|---:|---:|
| `23.237.104.106` | 26 | 14 |
| `wonvt.st` | 17 | 14 |

These are hostname blast-radius estimates only. Different hosts, source-family names and playlist sources are **not proof of genuinely independent upstreams**, lawful distribution, or verified playback.

### Priority work on `wonvt.st`

1. `FoxSports2.us`, `MLBNetwork.us`, `NBCSportsPhiladelphia.us`: single published, locally verified TVNow primary; separate discovered candidate on `cowedd4855ws.sbs` failed for each. Fox Sports 2's `23.237.104.106` candidate was in cooldown. None is a confirmed independent backup.
2. `FX.us`, `FXX.us`, `HGTV.us`, `InvestigationDiscovery.us`, `TLC.us`, `WeatherChannel.us`, `TravelChannel.us`: start with real client playback evidence, then exact-feed verification. FX had only one probed candidate in the later health report; FXX/HGTV alternatives on `cowedd4855ws.sbs` failed. Keep all these candidates out of production unless authorization and QA independently succeed.
3. `DiscoveryChannel.us`, `IFC.us`, `OWN.us`: a second hostname exists, but its upstream ownership and resilience must be verified before calling it independent.

### Priority work on `23.237.104.106`

1. `BigTenNetwork.us@SD`, `SECNetwork.us@SD`, `MLBStrikeZone.us@SD`: multiple passing candidate entries still resolved through this **same host**, so they are not independent backups.
2. `FoodNetwork.us@East`: its other host `212.5.144.156` produced HTTP **404** in the later run; don't promote it.
3. `ScienceChannel.us`, `CookingChannel.us@SD`, `ParamountNetwork.us`, `CMT.us@East`: single published source or no distinct-host backup in this build, and therefore useful follow-up targets.
4. `AnimalPlanet.us@East`, `NBATV.us@SD`, `TennisChannel.us@SD`: different hostnames appeared, but host diversity does not prove independent upstream operation or distribution rights.

### Safe source-hunt workflow

For each exact channel, prioritize official station/network streams, authorized distributors, or approved user-private local/provider connectors. Inspect candidate identity evidence, ownership/provenance, and lawful access *before* investing in probes. An official 24/7 streaming news channel is not necessarily the exact linear affiliate; a FAST variant is not an exact premium linear feed. Do not use embedded account credentials, DRM bypass, paywall circumvention, relay/restreaming, or expired signed URLs.

A candidate can enter production only after normal HLS and sustained direct-media FFmpeg decode, progression/repeat detection, and no quality regression. A user's separate, explicit local verification may continue to use the existing local-verified override policy, reported independently from CI passes. No automatic candidate promotions or kill-switch changes are made in this task.

**Next:** After the already-running post-PR-69 deployment succeeds, inspect `diagnostics/upstream-exposure.json` and use its top-10 tables to refresh this queue. Never interrupt that deployment just to land an identity metadata-only change.
