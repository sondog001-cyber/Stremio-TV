# Broad source-family hunt — 2026-10-12 (research only)

## Scope and status
Objective: find **new and independent candidate source families** for the exact curated 111 US-channel lineup, prioritizing Bravo, CBS Sports Network, Smithsonian Channel, ESPNews and the remaining missing IDs. Search expanded beyond trusted repos into smaller GitHub/gist playlists, IPTV issue histories, generator implementations, commercial-TV/TVE research and public FAST source directories.

**Critical:** No candidate in this document is approved for production, verified playable by our Stremio installation, or established as authorized to redistribute. A different playlist host is **not** a distinct video-origin family. No production config, QA, source promotion or kill switch was changed by this research.

Last confirmed successful live deployment #38316450648: **87/111** channels. Post-PR81 run #38321378327 **failed its release guard** and was not deployed. Production remains last successful Pages publish.

## Promising *new discovery systems* (distinct projects; not necessarily distinct origins)

| Rank | Discovery system | URL | Unique angle | Limitation / next test |
| --- | --- | --- | --- | --- |
| 1 | IPTV Nexus, dearbulut/iptv | https://github.com/dearbulut/iptv | Recently pushed 2026-10-12; JSON per-channel feeds, recent health observations, status-based filtered playlists, crawler + discovery proposals. | Initially built on iptv-org; **must inspect concrete upstream URLs against existing iptv-org and kill switch**, not call it a new upstream automatically. Research use: /api/v1/by-country/us.json, /playlists/online.m3u, /api/v1/health.json. |
| 2 | doms9/iptv | https://github.com/doms9/iptv | Active Oct 12 and publishes automatic stream-health log (158 working, 48 dead at 09:39 UTC). | CBS Sports Network and Smithsonian Channel are explicitly **HTTP 503** at `cdnlivetv.tv`, so not working recoveries; its health log is directly useful for eliminating both rather than repeating them. Extract any other missing exact-ID streams only if underlying hosts are new. No broad ingestion. |
| 3 | rebeliptv/iptv | https://github.com/rebeliptv/iptv | Hourly generation, multi-provider scraper architecture, fallback, stable channel IDs and health checking. | Need inspect provider list and returned **direct-origin** links. Dynamic gateway, paid account or credential paths are disallowed. |
| 4 | kineticman/FastChannels | https://github.com/kineticman/FastChannels | Distinct service-scraper implementations incl Xumo, LG, Roku, broadcast TVE, user OTA tuner; can help identify exact-lineage channels and official providers. | **Incompatible as a stream source** for TVE: TV-provider authentication + Widevine/bridge. Also M3U playback uses a local proxy/302 resolver. Useful for official access/identity and public FAST only, without DRM or restreaming. |
| 5 | xnxixi/iptv-two | https://github.com/xnxixi/iptv-two | Alternative curated OTT source scanner + guide for comparing families. | Appears older than rebeliptv and similar architecture. Verify independent source identities; high likelihood of mirrored origins. |
| 6 | IPTV-Scraper-Zilla | https://github.com/abusaeeidx/IPTV-Scraper-Zilla | Public continuously aggregated playlist via `combined-playlist.m3u`. May expose a new root playlist/generator family. | Unknown recency/rights/lineage; only research exact missing-ID matches and reject unsupported/credentialed upstreams. |

## Specific channel findings worth *not* confusing with recovered streams

- **Bravo:** iptv-org [issue #45915](https://github.com/iptv-org/iptv/issues/45915) offered `4.30.180.36:8420/bravo/index.m3u8?token=test`, **rejected: stream_cuts_out**. This is not a new viable candidate. The current iptv-org USA URL `41.205.93.154/BRAVO/index.m3u8` has already failed our final decoder gate. The alternate `fl3.moveonjoy.com/BRAVO` appears in multiple playlists (same family).
- **CBS Sports Network:** doms9 health log explicitly **503**; old iptv-org [issue #16032](https://github.com/iptv-org/iptv/issues/16032) references `livex.pop-app.live/s4n/poplive/ch325/playlist.m3u8`, a **historical unverified** source, not newly qualified. We excluded the user-tested failing `89.187.175.143:80/4073`. Other search hits are MoveOnJoy/TVpass copies; CBS Sports HQ is a different channel.
- **Smithsonian Channel:** `fl3.moveonjoy.com/SMITHSONIAN_CHANNEL` appears on TocsinData and other aggregators but belongs to the existing excluded MoveOnJoy family. User tested three different origins and none connected; do not repackage mirrors as new test links. Smithsonian Selects is a distinct FAST channel, not exact linear.
- **ESPNews:** contemporary search hits repeatedly use `fl2/fl3.moveonjoy.com/ESPN_NEWS`; no fresh distinct-origin direct stream verified. `SPxMM3R1/lista-m3u`'s Sept report on `ESPNews.us@Direct41` is obsolete: current entry deleted and playlist empty.
- **Other remaining missing IDs:** most newly surfaced FAST families (Pluto, Plex, Samsung, Roku, Xumo, LG, Free-TV, BuddyChewChew) are **already indexed in our config**. A same-title news/weather/docu FAST channel must not be mistaken for exact cable network.

## Source filtering / next research-only diagnostic pass
1. Query IPTV Nexus **US active channel shard** for only missing exact canonical IDs; extract origin URLs and freshness/health if available. Deduplicate by normalized final-origin host/path against current config, disabled URLs and both recent Local Test failure batches.
2. Query doms9's published health / source list for missing channel IDs, but reject the documented CBS 503 and transient URL cutouts.
3. Inspect rebeliptv's scrapers and source lineage for genuinely independent HLS; discard authenticated/proxy/DRM outputs. Compare against existing 27+ playlist feeds.
4. For any surviving **public direct** media candidate, perform two changing HLS manifests / segment sequence checks, FFmpeg decode burn-in, repeat/stall test and exact channel identity. Keep candidate research-only until verified.
5. Treat private connector-only WPSG and NBCSportsPhiladelphiaPlus separately; do not replace them with a different FAST/national feed or a private credential.

## Evidence
- https://github.com/dearbulut/iptv
- https://github.com/doms9/iptv
- https://github.com/rebeliptv/iptv
- https://github.com/kineticman/FastChannels
- https://github.com/xnxixi/iptv-two
- https://github.com/iptv-org/iptv/issues/45915
- https://github.com/iptv-org/iptv/issues/16032

## Bottom line
**Six potential discovery projects identified; zero new direct-video upstreams have yet passed QA**. Direct requests to IPTV Nexus live US JSON and online M3U endpoints were not accessible from the research browser, so per-channel returned URLs and health claims are still **unverified**. doms9's live October 12 log explicitly lists **both** CBS Sports Network and Smithsonian Channel as HTTP 503 at cdnlivetv.tv. That is not a stream-coverage gain. Research kept off production and local-test catalogs. Target future work by actual exact missing ID and new final-origin host, not playlist quantity.
