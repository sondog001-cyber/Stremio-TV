# Redundancy-guided exact-identity source hunt — 2026-10-12

**Baseline:** successful GitHub Actions run [38260260633](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38260260633), commit `e35e61e`. Published 86/111, missing 25; published single-stream channels: 62, with alternate provider hosts: 20 (host differences are an **estimate**, not definitive upstream-provider independence).

## Ranked recovery and backup work

- **Recent losses (recovery before new breadth):** `DisneyChannel.us` and `NationalGeographic.us`; each appears `runner_or_geo_blocked` in this run, so compare with local playback or find a new authorized upstream rather than interpreting HTTP 403 as an actual content failure. `History.us` recovered in this build, so leave it on continuity watch instead of forcing another Primary.
- **Top independent-provider backup targets:** `FoxSports2.us`, `MLBNetwork.us`, `NBCSportsPhiladelphia.us` (all single-stream, TVNow local-override, sports); then `DiscoveryChannel.us`, `FX.us`, `FXMovieChannel.us`, `FXX.us`, `HGTV.us`, `InvestigationDiscovery.us`, `Reelz.us`, `Showtime.us`, `TLC.us`, `TVLand.us`, `TravelChannel.us`, `WeatherChannel.us`. The exact top-10 list now regenerates on each production build via `diagnostics/resilience-hunt-queue.json`.
- **Philadelphia backup candidates:** `Fox.us@WTXFTV`, `Telemundo.us@WCAU`, and `WHYY.us` each have one published stream (despite stable playback), so should receive independent-provider alternatives when available.
- **High blast-radius upstream hosts:** `23.237.104.106` appeared on 26 published channels; `wonvt.st` on 17; `amagi.tv` and `198.58.104.90` each on 7 in this baseline. Hostname co-occurrence is **not proof** that two brands share an origin or that two addresses are independent; test provider relationships before crediting backups.

## Exact missing categories (25)

- **Failed actual probes (1):** `RFDTV.us`.
- **No candidates (1):** `CinemaxClassics.us`.
- **Cooldown (7):** `HBOMovies.us`, `StarzCinema.us`, `StarzEncoreSpanish.us`, `KYW.us`, `WCAU.us`, `WPHL.us`, `WPVI.us`.
- **Runner/access/geo blocked (14):** `BET.us`, `CBSSportsNetwork.us`, `CNBC.us`, `DisneyChannel.us`, `ESPNews.us`, `HallmarkFamily.us`, `HallmarkMystery.us`, `MSNOW.us`, `NationalGeographic.us`, `Nicktoons.us`, `SmithsonianChannel.us`, `StarzComedy.us`, `StarzEdge.us`, `SundanceTV.us`.
- **Private connector (2; exclude from public hunt):** `NBCSportsPhiladelphiaPlus.us`, `WPSG.us`.

## Source-hunt findings and triage

The following are **research leads only**. None was newly verified here for current live identity, independent operation, publication permission, 60-second burn-in, segment repetition, or FFmpeg playback. None should enter `manual_sources.json` on this evidence alone.

| Exact target | Discovery | Triage |
|---|---|---|
| `DisneyChannel.us` (East variant must match) | IPTV-org [issue #43877](https://github.com/iptv-org/iptv/issues/43877), approved July 2026 | Historic source is hosted at `212.5.144.156`; test if *independent* of existing candidates and re-check exact East identity. Approval in an issue is not current playback or rebroadcast authorization. |
| `Nicktoons.us` (East) | IPTV-org [issue #48485](https://github.com/iptv-org/iptv/issues/48485), check:passed Aug 2026 | Host `tvsen7.aynascope.net`; compare to existing 23 discovery candidates and cooldown reports; do not count another mirror as a backup. |
| `CinemaxClassics.us` | IPTV-org [issue #50689](https://github.com/iptv-org/iptv/issues/50689), check:passed Sep 2026 | Host `23.237.104.106` already supplies 26 published channels; unsupported public rebroadcast rights and origin concentration. Keep unpromoted. |
| `CNBC.us` | IPTV-org [issue #45926](https://github.com/iptv-org/iptv/issues/45926) July 2026, and [#30112](https://github.com/iptv-org/iptv/issues/30112) Dec 2025 | Exact channel label is useful but sources are third-party; must verify independence, feed identity and authorization. **Do not reuse** the 4.30 stream from [rejected issue #45918](https://github.com/iptv-org/iptv/issues/45918), labeled short-lived/cuts out. |
| `WPVI.us` | [6abc official 24/7 Action News feed](https://6abc.com/streaming/) | Official, free news/AccuWeather/Localish streaming channel; **not full WPVI linear broadcast**, so reject as an exact replacement. |
| `WCAU.us` | [NBC10 official 24/7 streaming channel](https://www.nbcphiladelphia.com/on_air_promotion/nbc10-philadelphia-hour-7pm-newscast-local-tv/4462879/) | News channel is not necessarily the full WCAU/NBC 10 broadcast; do not alias without schedule/identity proof. |
| `KYW.us` | [CBS News Philadelphia live](https://www.cbsnews.com/philadelphia/live/) | CBS's local 24/7 news streaming offering is distinct from the full CBS 3 linear affiliate; keep out of KYW exact ID. |
| `RFDTV.us` | [RFD-TV schedule](https://www.rfdtv.com/watch/schedule) / [RFD+](https://www.rfdtv.com/) | Official schedule/pay offerings are not themselves a verified open HLS feed for exact linear RFD-TV. |

### Next QA for any new viable lead

1. Verify exact aired channel `tvg-id`, including East/West variant; no generic FAST/news replacement.
2. Check origin/provider attribution **and authorization**. Reject login, DRM, paywall, embedded credentials, relay/restream, and unsupported private access.
3. Separate *new upstream* from a distinct URL on the same family. Record existing host avoidance from the live queue.
4. Test HLS manifest + fresh segments, codec decode, continuity, repeat/stall detection, and promotion burn-in. Leave the candidate unpromoted if GitHub runner cannot establish playback.
5. Preserve production sources, existing local overrides, per-source kill switches, and existing QA gates. No automatic promotion is warranted by these notes alone.

## Automated follow-through

PR for this hunt adds a read-only `diagnostics/resilience-hunt-queue.json` on every build. The queue recomputes missing/recently lost targets together with independent backup exposure, highlights current shared upstream concentration, excludes private-connector-only channels and makes **no playback selection or source publication changes**.
