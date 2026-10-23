# Disney Channel resilience + Nicktoons replacement-origin hunt — October 13, 2026

**Scope:** purely research/CI diagnostics on [draft PR #88](https://github.com/sondog001-cyber/Stremio-TV/pull/88). Production `config.json`, `manual_sources.json`, source priority, deployment guard, per-source kill switches, and public Stremio addon remain unchanged.

## Motivation / previous diagnosis

- Disney Channel disappeared from one October 13 production build; the deployment guard correctly blocked publishing. The next successful published build retained Disney. Its **two matching stream-health entries share the same `212.5.144.156` URL**, so there is no independent passing fallback.
- Existing Nicktoons on `41.205.93.154` passed two 60-second decode windows, then the third produced **repeating two- and three-second clips and an eight-second freeze**. It remains classified as technically suspect; the evidence does not constitute an authorization or actual programming-identity verdict.

## Six historical/third-party direct HLS source candidates

All six are publicly documented on GitHub; the [machine-readable registry](disney_nicktoons_replacements_20261013.json) includes exact submitted URLs and source references. A distinct **entry host or gateway family is not proof of a distinct original broadcaster-owned CDN**.

| Target | Family / published source | Live HLS preflight | 60s decoder | Decision |
| --- | --- | --- | --- | --- |
| Disney Channel East | TheTVApp (iptv-org [issue #28387](https://github.com/iptv-org/iptv/issues/28387)) | Unavailable | Not started | No replacement |
| Disney Channel East | MoveOnJoy (judy-gotv/iptv) | Unavailable | Not started | No replacement; already common relay |
| Disney Channel | Airlink sibling `iptvcdn.airlinktt.co` | Unavailable | Not started | No replacement; **same Airlink family** as previously failed lead |
| Nicktoons East | Tier1Streams (iptv-org [issue #47917](https://github.com/iptv-org/iptv/issues/47917)) | HTTP 404 | Not started | Not usable |
| Nicktoons East | **AynaScope `tvsen7.aynascope.net`** (iptv-org [issue #48485](https://github.com/iptv-org/iptv/issues/48485)) | **HTTP 200, 2 advancing live HLS windows** | **Pass: 60/60 unique 1s frames** | **Best technical research candidate only** |
| Nicktoons East | Shared `206.212.244.63` relay (iptv-org [issue #45330](https://github.com/iptv-org/iptv/issues/45330)) | Unavailable | Not started | No replacement |

In the initial AynaScope HLS preflight, media sequence advanced **77600 → 77603** and a direct segment-prefix was readable. The entry host, HLS media host and segment host were all `tvsen7.aynascope.net`. This verifies the delivery gateway, **not the true broadcaster/original media host**. Initial bounded FFmpeg output showed **60 distinct frame hashes**, no 2–4-second clip repetition, longest identical-frame run 1 second, return code 0. [Initial two-job run #38412786788](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38412786788) with research-only JSON artifacts.

### Independent three-window AynaScope continuity tests

We ran **three distinct GitHub Actions workflow executions**, each requiring a new progressing HLS preflight, **three separate 60-second direct FFmpeg intervals**, and 15-second pauses between decoding attempts:

| GitHub Actions research run | 1st interval | 2nd interval | 3rd interval | Result |
| --- | --- | --- | --- | --- |
| [#38413345691](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38413345691) | 60/60 unique, pass | 60/60 unique, pass | 60/60 unique, pass | **3/3** |
| [#38413401537](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38413401537) | 60/60 unique, pass | 60/60 unique, pass | 60/60 unique, pass | **3/3** |
| [#38413435716](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38413435716) | 60/60 unique, pass | 60/60 unique, pass | 60/60 unique, pass | **3/3** |

**Total 9/9 clean 60-second intervals** across three separate short-window CI runs, no detected 2–4-second loops or freezes greater than one second in sampled frames. This is significantly stronger *technical* evidence than the current Nicktoons host, which repeated/froze in one of three intervals. It is **not** a nine-minute uninterrupted stream test (the intervals were separated), a multi-day longevity test, or a full on-screen channel-identity comparison.

## Critical identity and reuse caveats

- The public name/`tvg-id` submitted in the iptv-org issue supports *possible* US Nicktoons East identity, but the actual decoded programming, channel bug and current aired-order/EPG correspondence have **not** been independently confirmed.
- The site `aynascope.net` is still **explicitly excluded** by `config.local_test_catalog.exclude_provider_hosts`. We did **not** remove or bypass that exclusion for this research.
- The use/redistribution permission for an unauthenticated third-party gateway and actual original licensed media provenance are **unverified**; no direct Stremio production or Local Test link was created.
- AynaScope's `/disney/index.m3u8` was **excluded** as a Disney replacement because iptv-org's US list identifies that endpoint as **Disney Junior**, while another scraped playlist says Disney Channel. This is a wrong-channel trap, not a usable fallback.
- The sources require no embedded account credentials in the committed research registry. No DRM bypass, cookie extraction, TLS disabling, login/session scraping, proxy/restream, or signed token harvesting was done.

## Decision and next acceptance gates

**Disney:** 0/3 replacement preflights passed; keep deployment guard and treat Disney as **single-provider risk**. Continue *fresh original-origin* hunts; stop retesting same failed hosts as independent backups.

**Nicktoons:** one technically stable-looking **alternate gateway**, not yet eligible to promote. Before reviewing any Local Test exclusion exception or production backup, verify actual Nicktoons US East on-screen programming versus EPG at multiple times, establish permitted direct-link use/provenance, and perform repeated local-client playback if authorized. Only then test priority/fallback selection behind a separate reviewed PR.

**Published curated coverage is not changed by these research jobs.** The most recently established production baseline was 89/111; check separate successful deploy artifacts for newer changes before making claims.
