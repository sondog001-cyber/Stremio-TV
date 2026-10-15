# Live-player origin assessment — October 14, 2026

This note captures research findings **without changing any source configuration**. Original full linear network identity and original FFmpeg QA are mandatory for promotion.

## NBCUniversal — Bravo, USA Network, E!

- Official watch experiences classify as TV Everywhere (TV-provider login required). The single unauthenticated page HTML inspection found **no standalone HLS manifests** for these three networks.
- NBCUniversal help: https://help.nbc.com/hc/en-us/articles/360033854593-TV-Provider-vs-Internet-Provider
- Existing implementations such as https://github.com/kineticman/FastChannels support NBCUniversal TVE using a subscriber identity / DRM bridge, **not** an anonymous direct upstream for this project. Do not bypass DRM, use credentials, or add a proxy/restreamer.
- TVE provider integration may be considered separately only if user explicitly changes architecture and access requirements. **Not a qualifying source for current public add-on.**

## WPVI / 6ABC

- Official watch page https://6abc.com/watch/video/ embedded a Uplynk HLS origin at `content.uplynk.com` with a path containing `wpvi_24x7_news.m3u8`.
- This is explicitly a 24/7 news channel, **not the full WPVI 6ABC OTA affiliate**. Do not alias it to WPVI.us.
- The ABC Watch Live page https://abc.com/watch-live/ceb5fbbb-c5db-4470-8f10-c1d98097bebd did not expose a standalone HLS manifest in public HTML. Its contents include TVE / DRM signals; requires investigation in an authorized session, not a parser-based adoption.

## WCAU / NBC10

- Official https://www.nbcphiladelphia.com/watch/ has two distinct `cloudfront.net` paths with `/11602/88889705/hls/master.m3u8` and `/11603/88889705/hls/master.m3u8` (query tokens deliberately redacted).
- Treat them as 24/7 local-news media, **not WCAU-DT1 broadcast**. Page also contains DRM-related wording; no network feed was authenticated or extracted.

## KYW / CBS3

- Official https://www.cbsnews.com/philadelphia/live/ exposes `phila5bcfb03.airspace-cdn.cbsivideo.com/live/manifest.m3u8` directly in publicly served HTML.
- This belongs to CBS News Philadelphia's 24/7 local news offering, **not full KYW-DT1 CBS3 programming**. Preserve as separate future catalog candidate only if lineup expressly includes local news FAST content; do not use to meet current 86.

## WPHL / PHL17

- https://phl17.com/ timed out/blocked in the runner. No direct playable origin established. Official page should be checked later with a browser, but a browser-required player is not evidence of a suitable direct HLS feed.

## WPSG / Philly57

- https://www.cbsnews.com/philadelphia/ exposed an HLS link at `prod.vodvideo.cbsnews.com` with a `/cbsnews/vr/hls/.../master.m3u8` VOD-style path.
- That does **not** establish a WPSG-DT1 or Philly57 live network. Reject it as unrelated video until proven otherwise.

## Overall

- Official watch pages checked: **9**; accessible from runner: **8**.
- Distinct media URLs embedded in public HTML: **5**.
- New exact full-live-channel identities verified: **0**.
- Keep source, source ordering, logo normalization, 86-channel floor, all QA thresholds, and production unchanged.
- Output artifact: https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38665105218/artifacts/11940672139
- Focus next exploration on *true full-affiliate OTA streams* and genuinely independent linear network origins, not 24/7 news products or TVE protected URLs.
