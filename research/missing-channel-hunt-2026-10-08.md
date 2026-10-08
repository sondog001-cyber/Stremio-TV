# Targeted exact-channel source hunt — 2026-10-08

Source of missing classifications: production build 37780013366, `diagnostics/missing-source-diagnostics.json`. These are **research targets**, not automatically approved or publishable streams. Re-evaluate against the latest build before adding anything.

## Public-source-research candidates (24)

- **Failed HLS/media probes:** `RFDTV.us`, `KYW.us`, `WCAU.us`. Prefer broadcasters' public authorization, exact full linear feeds or OTA before third-party mirrors.
- **No candidate:** `CinemaxClassics.us`. Lead: iptv-org issue #50689 (`CinemaxClassics.us@East`, `http://23.237.104.106:8080/USA_5STARMAX/index.m3u8`, dated 2026-09-05, issue labeled `approved`/`check:passed`). **Not verified by this project**, no rights/authorization established; do not add without identity, policy, continuous HLS segment and decoder/repeat QA.
- **Final playback decoder failed:** `CookingChannel.us`. Verify media decode and continuity before any promotion.
- **Quarantined/dead/cooldown:** `BET.us`, `HBOMovies.us`, `HallmarkFamily.us`, `NFLNetwork.us`, `StarzCinema.us`, `StarzComedy.us`, `StarzEncoreSpanish.us`, `WPVI.us`. Search exact-ID and alternative independent source families, avoid repeating dead links.
- **GitHub runner/geo blocked:** `CBSSportsNetwork.us`, `ESPN.us`, `ESPNews.us`, `HallmarkChannel.us`, `HallmarkMystery.us`, `MSNOW.us`, `SECNetwork.us`, `SmithsonianChannel.us`, `StarzEdge.us`, `SundanceTV.us`, `WPHL.us`. Treat runner failures as inconclusive; prioritize user-side verification or properly authorized alternates.

## Private connector required (2; do not public-hunt)
- `NBCSportsPhiladelphiaPlus.us`
- `WPSG.us`

## Early findings
- RFD-TV's official watch schedule and RFD+ pages point to scheduled and subscription offerings rather than a proven, open, full linear feed: https://www.rfdtv.com/watch/schedule and https://www.rfdtv.com/opry-live
- Cinemax's official service requires provider/subscription access: https://www.cinemax.com/order ; an openly listed third-party M3U8 does **not** establish rebroadcast permission.
- Exact Cinemax Classics lead: https://github.com/iptv-org/iptv/issues/50689

## Validation checklist for all candidates
1. Verify exact `tvg-id` and true linear identity (not similarly named FAST/event/news clips).
2. Reject embedded credentials, private keys, DRM/license bypass and unapproved rebroadcast sources.
3. Confirm public authorization and no access-control circumvention.
4. Record independent upstream family/host, variant quality and headers.
5. Pass two playlists with changing segments, 60-second burn-in and actual decoded playback with repeat/stall detection.
6. Only then add candidate via normal QA-gated staging/PR; retain kill-switch capability.
