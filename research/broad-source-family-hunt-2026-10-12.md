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


## In-depth follow-up: IPTV Nexus vs Rebel IPTV (Oct 12)

### IPTV Nexus — actual upstream provenance
- Read live upstream config: [config/sources.yml](https://github.com/dearbulut/iptv/blob/main/config/sources.yml). **Enabled sources:** iptv-org API and `config/discovered.m3u` (auto-discovery list).
- Fetched current `config/discovered.m3u`: **exactly `#EXTM3U\n`** (zero entries). This provides **zero** candidate media URLs for any of the 24 missing channels.
- Read [config/discovery.yml](https://github.com/dearbulut/iptv/blob/main/config/discovery.yml): only **iptv-org country index** and **iptv-org category index** are enabled. The community index example is disabled.
- Samsung, Pluto and Plex in sources.yml are **commented out**, not running as new IPTV Nexus source families. (Most FAST sources already indexed independently by our own addon.)
- The `state` branch contains 8.8 MB health.json and discovery.json. `discovery.json` is a persisted rejection-hash list, not a media URL source. GitHub's file API declined to return the large health.json contents in the available runtime.
- Requested these public static Nexus endpoints:
  `https://dearbulut.github.io/iptv/api/v1/index.json`,
  `.../by-country/us.json`,
  `.../channels/Bravo.us.json`, and
  `.../playlists/country/us.m3u`.
  **All were inaccessible to the available research client.** Therefore there was *no media origin extraction* from its live API; no per-channel freshness, working source, or source count can be confirmed.
- **Verdict:** The only observable enabled origins are IPTV-org; auto-discovered source count **0**, original distinct media origin gain **0 observed**. Re-evaluate Nexus when its public API is accessible or config/discovered.m3u contains entries. A novel **monitoring implementation** is not itself a novel provider.

### Rebel IPTV — actual upstream provenance
- Checked [repository root](https://github.com/rebeliptv/iptv): it contains `README.md`, release notes, screenshots, license, GitHub metadata; **no open src directory, scraper implementations, channel database, or public direct-origin M3U**.
- [README](https://github.com/rebeliptv/iptv/blob/master/README.md) explicitly states **all streams are fully proxied and upstreams hidden**; provides self-hosted Docker server, user playlists and sources, and authenticated playlist/EPG API. Promises 450+ channels but **does not establish identities or public upstream media URLs**.
- Proxy/MPEG-TS restreaming, auth/API keys, local HDHomeRun server support **do not meet our direct-upstream-only policy** and don't provide an inspectable upstream origin to deduplicate.
- No documented usable route in the public repository for extracting its original sources without running its proprietary container and inspecting private backend behavior. We did not attempt access bypass, decompilation or circumventing protected streams.
- **Verdict:** **0 extractable upstream URLs** from the public repository. Treat as an architecture/feature reference only unless its maintainers release independently public direct origins.

### Exact missing-ID source comparison result
| Source | Bravo.us | CBSSportsNetwork.us | SmithsonianChannel.us | ESPNews.us | Other missing IDs |
|---|---|---|---|---|---|
| Nexus configured new `discovered.m3u` | 0 | 0 | 0 | 0 | 0 |
| Nexus health/US production API | inaccessible | inaccessible | inaccessible | inaccessible | inaccessible |
| Rebel public repo direct-origin URLs | none available | none available | none available | none available | none available |

**Meaning:** We extracted the upstream configuration and found **zero new feed URLs** in the observable Nexus discovery output; Rebel does not publish direct-source data. This is a **source-level negative finding**, not a verification of every stream hidden in their hosted deployments. No comparison against the project's 11 killed URL paths is needed for a zero-entry dataset.

### Useful follow-up
1. If Nexus API becomes accessible, query **only the canonical 24 missing IDs**, traverse `streams[].url` in each returned channel JSON, normalize URL host+path (discard volatile tokens), dedupe against existing sources, and tag `sources[]` provenance (iptv-org-only vs novel).
2. For Rebel, obtain a maintainer-published origin list **with permission**; no proxy playback from its proprietary server.
3. Continue distinct-origin research against other candidates (small playlist generators and legally accessible official endpoints) rather than manufacturing a test list from empty/proxy-only results.


## Small independent playlist / generator origin triage — follow-up

Focused search on Bravo, CBS Sports Network, Smithsonian and ESPNews, excluding existing MoveOnJoy, 41.205.93.154, expired TVE and credentialed Xtream hits. **Repository identity is not source-family identity.**

| Research lead | Provenance | Exact-channel outcome | Verdict |
|---|---|---|---|
| [CeresLabX/us-tv](https://github.com/CeresLabX/us-tv) | README explicitly says its source is IPTV-org US; regenerates ~676-channel playlist | Bravo is the **identical** `http://41.205.93.154/BRAVO/index.m3u8` | Duplicate origin; do not test again |
| [gogetta69/public-files](https://github.com/gogetta69/public-files/blob/main/m3u_formatted.dat) | Publishes MoveOnJoy M3U and channel metadata | ESPNews URL on `fl2.moveonjoy.com` | Existing excluded origin family |
| [afshinkobi/iptv](https://github.com/afshinkobi/iptv/blob/main/playlist%204.m3u) | Mixed playlist from public sources | ESPNews `https://fl1.moveonjoy.com/ESPN_NEWS/index.m3u8` | Existing excluded origin family |
| [dzhafar777-ai M3U gist](https://gist.github.com/dzhafar777-ai/2bc403291f95dbee9bb29a4a41735312) | IPTV-org compilation | Bravo upstream `41.205.93.154`; alternate `tvsen7.aynascope.net` | Both already cataloged/known failing |
| [mik25/marvel_m3u](https://github.com/mik25/marvel_m3u) | Xtream-style account-path links (username/password components) | CBS Sports Network via private account-shaped `25461` IPTV endpoint | Excluded by embedded credential policy; not a public direct feed |
| [eslco/YueChan combined gist](https://gist.github.com/eslco/95291fddc442733afb4ab5abb9ab4caf) | Mixes MoveOnJoy with individual CDN FAST channels | No new exact target match established; recognizable NBCU-derived FAST names are **not** Bravo linear | Potential general generator lead, not a recovery |
| [CeresLabX playlist](https://github.com/CeresLabX/us-tv/blob/main/playlist.m3u) | Same IPTV-org output at alternate host | Bravo exact same failed upstream | Rejected duplicate |

Other screened repos ([koztay/iptv-sources](https://github.com/koztay/iptv-sources), [whhxmwhh/iptv-usa](https://github.com/whhxmwhh/iptv-usa)) are IPTV-org indexes/forks, while [kpirnie/kptv-proxy](https://github.com/kpirnie/kptv-proxy) is a proxy aggregator with authenticated Xtream support rather than a public new media upstream. Keep them out of recovery count.

**Disposition:** Multiple new *playlist URLs* reviewed, **0 verified novel exact-channel video origin URLs** for the four top targets, **0 new Stremio local-test candidates**, **0 production changes**. Broaden to source repositories whose config declares a primary independent provider/official broadcast origin; reject forks, rehosting, masked proxy links and expired credential lists before consuming QA time.
