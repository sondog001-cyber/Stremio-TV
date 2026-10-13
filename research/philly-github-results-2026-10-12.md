# GitHub-first software-only Philadelphia full-linear hunt — October 12, 2026

## Outcome

**17 public playlist URLs across four missing full-linear Philadelphia affiliates; 0 HLS preflight passes, 0 original video origins verified, 0 decoded/identity/authorization QA passes, 0 candidates approved for local tests, and 0 production changes.** WPSG has no eligible publicly accessible identity-consistent URL for this experiment.

This is a deliberate **hardware-free** search of public GitHub source files and unofficial historical HLS families: do not suggest the antenna/HDHomeRun prototype as a prerequisite. This work is isolated in [draft PR #85](https://github.com/sondog001-cyber/Stremio-TV/pull/85). Main/public addons and Stremio test catalogs are unchanged.

* Original GitHub Actions run (all five station jobs green **as research tasks**, NOT streams): [run #38337155060](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38337155060)
* Second confirmation after adding only public `Referer`, `Origin` and `User-Agent` from [nightah/daddylive](https://github.com/nightah/daddylive): [run #38337469086](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38337469086).
* PR unit tests: [successful validation run #38337469070](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38337469070).
* Structured candidates, exact published GitHub sources, and each entry hostname are in [the research-only registry](philly-github-candidates-2026-10-12.json). Per-URL HTTP errors/progression details are in five GitHub Actions artifacts, retained for 14 days.

## Station-by-station results

| Exact ID | Published candidates probed | Readable progressing HLS | Notes |
| --- | ---: | ---: | --- |
| `KYW.us` — full CBS 3 | 5 | **0** | MyBTV 2, legacy LocalBTV 1, MoveOnJoy 1, IPTVmate 1 |
| `WPVI.us` — full 6abc | 4 | **0** | MyBTV 1, legacy LocalBTV 1, MoveOnJoy 1, IPTVmate 1 |
| `WCAU.us` — full NBC 10 | 6 | **0** | MyBTV 2, legacy LocalBTV 1, MoveOnJoy 1, IPTVmate 1, DaddyLive 1 |
| `WPHL.us` — full PHL17 | 2 | **0** | MyBTV 1, legacy LocalBTV 1 |
| `WPSG.us` — full Philly57 | 0 eligible | **0** | Credentialed provider playlist hits and outdated CW57 labels; identity trap noted below |

### Actual network errors, grouped by source family

| Published entry origin / family | URLs | GitHub runner outcome | Interpretation |
| --- | ---: | --- | --- |
| `v-pi.mybtv.net` (old MyBTV) | 6 | `SSL: CERTIFICATE_VERIFY_FAILED` — unknown issuer chain | HTTPS not trusted; no manifest received. **Do not disable TLS verification** merely to force acceptance |
| `v-pi.theus6tv.tk` (old LocalBTV) | 4 | DNS resolution: `[Errno -2] Name or service not known` | Published hostname does not resolve in runner |
| `fl1.moveonjoy.com` | 3 | TCP connection refused: `[Errno 111]` | Known relay family; no present media origin from these exact paths |
| `ch.iptvmate.net` | 3 | `SSL: CERTIFICATE_VERIFY_FAILED` — unknown issuer chain | No redirects/final media host; entry hostname cannot be called an original origin |
| `zekonew.newkso.ru` / DaddyLive NBC10 #277 | 1 | HTTP **403**, still 403 with the GitHub playlist's documented public `Origin`/`Referer`/`User-Agent` | Public-header context alone does not supply usable media. No session/cookie/paywall bypass; no accessible HLS |

All **17** failed *before* a trustworthy HLS master/media playlist could be resolved. None reached the two-advancing-window plus segment-prefix gate. Thus every candidate remains **unverified**, not “0/5 decoded” or a local-playback-validated dead stream. A GitHub runner may be network/geo denied, but with these exact failure categories we should not ask the user to waste time on the same old links.

### Why MyBTV/LocalBTV is a particularly weak line of further investigation

This family isn't a fresh original host simply because cloned GitHub playlists still list station-specific IDs. The underlying LocalBTV service **paused in November 2023**, according to the [December 2023 company outage report](https://cordcuttersnews.com/free-streaming-service-localbtvs-website-is-back-but-everything-else-is-still-down/) and [third-party streaming service description](https://thestreamable.com/video-streaming/localbtv/devices/android-phone-tablet). `mybtv.net` and `theus6tv.tk` may use distinct hostnames, but they must be grouped as historical/related family until original-video independence is demonstrated. Conflicting archive numeric IDs for KYW (318 vs 418) and WCAU (345 vs 322) also need actual EPG/video proof before ever matching exact curated stations.

### New false-positive trap: “CW57/WPSG” isn't enough

[RedRobocon06's older Philadelphia OTA list](https://github.com/RedRobocon06/Live-TV-Stream-Files/blob/main/Local%20Broadcast%20TV.m3u) labels a DaddyLive `premium300` entry as **WPSG / CW57**. However, independent GitHub playlist entries identify the same `premium300` as **CW Plus Central** or **CW WUCW, St. Paul, MN** — [newguy20420/dlt](https://github.com/newguy20420/dlt/blob/main/dlhd.txt), [Josh9456/IPTV-m3u](https://github.com/Josh9456/IPTV-m3u/blob/main/all_channels/tivimate_playlist.m3u8). These disagree on affiliate identity, so this does **not** qualify as a WPSG source; no ad-hoc remapping, public test, or public WPSG search-policy exception. Account-bearing WPSG/CW57 listings are also rejected.

### Distinguish news FAST from full stations

GitHub results include an official [WPVI 24/7 Action News Uplynk](https://content.uplynk.com/channel/ext/10b98e7c615f43a98b180d51797e74aa/wpvi_24x7_news.m3u8), a [CBS News Philadelphia FAST feed](https://www.cbsnews.com/philadelphia/live/) and [NBC10 Philadelphia News FAST](https://www.nbcphiladelphia.com/watch/). These **do not provide ABC, CBS or NBC complete OTA prime-time/program schedules**. Keep them out of `WPVI.us`, `KYW.us`, and `WCAU.us`. They can only be separate channels with separate exact identities if ever deliberately curated.

## Coverage of the GitHub search

Searched exact/tolerant identifiers `KYWDT1`, `WPVIDT1`, `WCAUDT1`, `WPHLDT1`, `WPSGDT1`, `CW57WPSG`, `CBS3KYW`, `NBC10WCAU`, station names, and `m3u8`/HLS suffixes. Sources inspected included [RedRobocon06/Live-TV-Stream-Files](https://github.com/RedRobocon06/Live-TV-Stream-Files), [arkina1234-undenified/IPTV](https://github.com/arkina1234-undenified/IPTV), [eklins/FDTV](https://github.com/eklins/FDTV), [RichardBuet/EASYTVWEB](https://github.com/RichardBuet/EASYTVWEB), [nightah/daddylive](https://github.com/nightah/daddylive), [iptvmate/iptvchannels](https://github.com/iptvmate/iptvchannels), and many duplicate LocalBTV/IPTV clones.

Rejected Xtream/account-shaped stream paths and private TVNow subscriber URLs before testing or logging. Different scraped playlist repositories **do not equal different original media origin hosts**. No video relayed, no TLS bypass, no DRM or cookies obtained, no credential sharing. Direct upstream only remains the project rule.

## Next engineering guidance

1. **Retire MyBTV/old LocalBTV from repetitive hunts** unless a genuinely reactivated provider or new origin is evidenced. The hostname/cert failures and the service's post-2023 status make them low yield.
2. **Keep MoveOnJoy, DaddyLive NBC10 #277 and IPTVmate as research-only blocked candidates** until a legitimate, independently accessible final media endpoint emerges. Public referrer retry has already failed for #277; do not manually add it to Local Test.
3. **Focus GitHub searches on currently maintained resolvers that publish underlying *original segment/CDN origins* with exact affiliate identity**, not country-wide clones or new URLs with the same gateway. An unverified `premium300` must not be misclassified as Philadelphia WPSG.
4. Keep the hardware-free strategy for the user's current preference. Separately strengthen currently working channels and their independent backups; don't risk existing production coverage to force stalled Philadelphia sources.

**Status:** No confirmed recovered locals from this pass, and no modifications to `config.json`, `manual_sources.json`, public `local_test_catalog`, private tuner prototype, or production deployment.
