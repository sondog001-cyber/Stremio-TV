# Net-13 recovery investigation — October 14, 2026

## Actual comparison: successful 89 vs failed 76

Baseline production: successful GitHub Pages run [38501765821](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38501765821). Failed logo-update build: run [38600341353](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38600341353).

The 76 build lost **15 previously published exact feed identities**, gaining two alternate identities instead: `TennisChannel.us` and `truTV.us@West`, resulting in **net -13**. Do not count these as full recoveries before the new Tennis and truTV programme identities match the originals.

| Previously published exact ID | Failure from failed build |
| --- | --- |
| BET.us | Network health returned OK for `jmp2.uk`, but final FFmpeg playback QA decoded zero video frames |
| BigTenNetwork.us@SD | `23.237.104.106:8080` timed out |
| CMT.us@East | Same shared host timed out |
| CinemaxHits.us@East | Same shared host timed out |
| CookingChannel.us@SD | Same shared host timed out |
| E.us@East | Same shared host timed out |
| History.us@East | Independent `212.5.144.156:8080` host returned HTTP 404 |
| MLBStrikeZone.us@SD | `23.237.104.106:8080` timed out |
| OneAmericaNewsNetwork.us@SD | Same shared host timed out |
| SECNetwork.us@SD | Same shared host timed out |
| ScienceChannel.us | Same shared host timed out; other listed sources returned DNS/403/timeouts |
| StarzKidsFamily.us@East | Same shared host timed out |
| TennisChannel.us@SD | `23.237.104.106` timed out; other Tennis Channel entries remain but may differ in country/programming |
| WeTV.us@East | Shared host timed out |
| truTV.us@East | Shared host timed out; new West slate is not automatically equivalent to the East feed |

The last logo-change production attempt generated 76/76 normalized logos with zero fallbacks. The unchanged deployment guard blocked publishing a reduced lineup: 76 is below the minimum 86, and the previously published essential `History.us` was absent.

## Original-media discovery (new hosts, not copied playlists)

Current [doms9/iptv base.m3u8](https://github.com/doms9/iptv/blob/default/M3U8/base.m3u8) provides five separately-hosted media-origin leads via `cache0.wonvt.st`: BET, Big Ten Network, E! East, Science Channel, and SEC Network. These require public page referer `https://tvnow.st/`. Any HLS validation must use public player headers; do not use embedded account credentials.

Current AynaScope/AynaOTT public media URLs provide additional label-based History East and Cooking TV leads; the Cooking TV programme identity **must not** be assumed to be Cooking Channel US. The KlowdTV CDNs expose a separately-hosted **One America News** label via `a-cdn.klowdtv.com`. Other candidates include the prior original feeds, a Tennis Channel feed needing country identity check, and an East-labelled truTV Warner slate that may not carry programme footage. None is approved for production solely from its label.

Older MoveOnJoy mirrors and duplicate IPTV-org entries pointing to the failing `23.237.104.106` are **not redundancy**. Avoid Latin American/FAST/alternate network programming under the requested US East IDs.

## Promotion gate

1. Two separated decoder attempts and a 65-second FFmpeg continuity pass on each fresh media origin; inspect original video/network bug for exact identity.
2. If a lead qualifies, stage it with explicit exact `tvg-id` on an isolated PR and run the same full transport, FFmpeg, repeat, channel-count, and essential-ID guards used by production. Confirm normal primary/fallback selection and feed schedule.
3. Never edit production URLs, `deployment_guard.py`, local-pass status, or widen regional ID aliases for convenience. The current task must remain isolated until successful full QA and a genuine 86+ channel build.
4. Report both **exact identities missing** (15) and **net channel difference** (-13) to avoid hiding East-versus-West substitutions.

Read-only diagnostic script: `research/recover_lost_13_probe.py`; workflow `recover-13-source-probe.yml`. This branch cannot deploy or change working streams.
