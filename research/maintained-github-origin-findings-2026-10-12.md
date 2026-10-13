# Maintained GitHub origin-family audit — all 24 missing Stremio TV channels

**Research session:** 2026-10-12 (America/New_York; GitHub Actions run early 2026-10-13 UTC). **Production unchanged.** This is a *software-only* hunt, not an OTA tuner hardware recommendation. This report is not a public sources file and should not be consumed by the builder.

## Scope

Inspected two current, independently maintained source projects, an existing high-volume source reference, and two newer resolver implementations:

* [IPTV-Scraper-Zilla](https://github.com/abusaeeidx/IPTV-Scraper-Zilla), pushed 2026-10-13 UTC: `TVPass.m3u` and `US_LOCAL.m3u` (556 and 178 approximate records). Its `TVPass.m3u` refresh script [file/tvpass.py](https://github.com/abusaeeidx/IPTV-Scraper-Zilla/blob/main/file/tvpass.py) copies remote TVPass's channel watch URLs, not original HLS origins.
* [nightah/daddylive](https://github.com/nightah/daddylive), pushed 2026-10-13 UTC: direct-looking `daddylive-channels.m3u8` playlist with around 728 video entries; most target matches resolve to sibling `*.newkso.ru` paths with public `Origin`/`Referer` dependencies, not a newly proven licensed broadcaster/CDN.
* [iptv-org/iptv](https://github.com/iptv-org/iptv/blob/master/streams/us.m3u), around 1,060 US entries: source-of-record for the older IP/CDN leads, not evidence of new health or originality.
* [sharoon7171/daddylive-stream-resolver](https://github.com/sharoon7171/daddylive-stream-resolver) (pushed Sept 24 2026) and [Lunatic16/dlhd-web](https://github.com/Lunatic16/dlhd-web) (pushed Sept 29 2026): technically real resolver work, but the pipeline uses `src/proxy/live.ts`, `src/proxy/unwrap-webp-ts.ts` or `src/proxy/media.ts`. The image/wrapped-segment decoding and media rewriting belong in a proxy/restream path, which this project explicitly **does not adopt**. These repos improve discovery knowledge, not automatically compatible direct Stremio sources.
* Checked additional GitHub indexes, issue history, older playlist clones, and exact IDs including legacy `HBOZone`, `5StarMax`, `HallmarkDrama`, `MSNBC` and `CW57WPSG`. No subscriber credential paths, DRM/player sessions, or copied opaque signed tokens were harvested.

The four CI jobs parsed **2,521 playlist entries per batch** across these four pinned public files (1,060 + 555 + 178 + 728). They match all 24 research targets with exact IDs, explicit historical aliases or exact channel names. **52 source-label matches** occurred across 18/24 target IDs after alias corrections: A=11, B=25, C=10, D=6. These are playlist *claims*; many are multiple SD/HD variants on the same `tvpass.org` web route, the same historical relays, or unrelated clones. None of these counts represents independent original video hosts.

Six IDs have **zero matches in this specific four-file source set**: `KYW.us`, `WPVI.us`, `StarzEdge.us`, `WPHL.us`, `NBCSportsPhiladelphiaPlus.us`, `WPSG.us`. This does *not* negate previously known sources outside this sample; for example previous [Philadelphia dedicated hunt](philly-github-results-2026-10-12.md) already tested 17 archived leads with 0 manifest passes.

## Five selected historical direct HLS leads — isolated preflight

| Target | Public GitHub-listed URL lineage | Result / engineering implication |
| --- | --- | --- |
| **Bravo.us** | `http://41.205.93.154/BRAVO/index.m3u8`, [iptv-org US](https://github.com/iptv-org/iptv/blob/master/streams/us.m3u) | **Intermittent**: progressing media plus segment readable in one run; in a later run, `hls-window-not-progressing`. Not a Stable or qualifying Primary. |
| **Nicktoons.us** | Same `41.205.93.154` origin/IP, `/NICKTOONS/index.m3u8`, [iptv-org US](https://github.com/iptv-org/iptv/blob/master/streams/us.m3u) | **Promising at preflight level only:** two progressing manifest windows with readable segment bytes on repeated CI research passes. No original-media provenance, uninterrupted FFmpeg video or precise schedule/identity established at this stage. |
| **MSNOW.us** | `41.205.93.154/MSNBC`, from [iptv-org history](https://github.com/iptv-org/iptv/issues/42525) | No progressing readable HLS on this research pass; the exact link was also marked broken in July 2026. |
| **MSNOW.us** | `40.160.24.53/MSNBC`, recent [Freeman0501/freelist](https://github.com/Freeman0501/freelist) | No progressing readable HLS on this pass. Old MSNBC labels don't establish current MS NOW feed identity. |
| **StarzEncoreSpanish.us** | `168.228.44.241:9998/play/a0e1`, [iptv-org US](https://github.com/iptv-org/iptv/blob/master/streams/us.m3u) | No progressing readable HLS; public third-party issue history also notes earlier timeout, likely aging reseller endpoint. |

See [all-24 audit run #38338409538](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38338409538), [latest full four-batch code run #38338644536](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38338644536) and current PR's [research workflow](https://github.com/sondog001-cyber/Stremio-TV/actions/workflows/audit-maintained-github-origin-families.yml).

**Historical-health caveat:** iptv-org issue [#42525](https://github.com/iptv-org/iptv/issues/42525) reports `41.205.93.154/MSNBC` broken in July 2026; issue [#48358](https://github.com/iptv-org/iptv/issues/48358) notes a broken Nicktoons link with that IP in August 2026, so the same IP working in one snapshot is not enough for production. These observed positive Nicktoons/Bravo snapshots should not be confused with a 60-second uninterrupted decode.

## Family-level engineering conclusions

| Finding | Meaning for Stremio |
| --- | --- |
| TVPass `/live/..../hd` and `/sd` | Published browser watch endpoint, **not direct HLS**; a green TVPass playlist refresh does not prove the video CDN is reachable. |
| DaddyLive `newkso.ru` / `mizhls.ru` | Popular direct-looking links but segment processing/referer controls or media proxy paths remain known obstacles. A resolver fork is not an original media-family discovery. |
| 41.205.93.154 | Multiple target channels on **one shared upstream host**, with intermittent health and prior outage reports. Two labels on that IP do **not** create redundancy. Provenance and legal access remain unverified. |
| 23.237.104.106 `HBO_ZONE` / `5STARMAX` / `STARZ_...` | Known widely shared source family; Cinemax exact path has prior decoder-zero-frame quarantine. Avoid recycling as new source. |
| 168.228.44.241 and 40.160.24.x | Historical IPTV gateways/resellers with unsuccessful public preflights. Not first-party original broadcasters. |
| Original FAST news or thematic channels | CBS News Philadelphia, NBC10 News, 6abc Action News, Bravo Vault, CBS Sports HQ, Hallmark Movies & More etc. are **not** full curated linear identities. Reject false-positive replacements. |

## Acceptance and source-policy result

No network stream URL was added to public `manual_sources.json`, `config.json`, a production catalog or Stremio Local Test. All QA flags in scanner artifacts remain false even where a manifest and segment read passed, until:
1. 60+ seconds genuine FFmpeg video decode and anti-repeat/stall QA, over multiple independent intervals.
2. Exact 24/7 linear channel identity and local affiliate/East-v-West match against schedule.
3. Original source/segment delivery CDN provenance and applicable permission to provide a direct URL to the user.
4. Stable performance and provider diversity sufficient to avoid replicating 3-second loops or single-host outages.

**Research branch:** [draft PR #86](https://github.com/sondog001-cyber/Stremio-TV/pull/86). Reproducible [machine-readable 24-ID registry](maintained-github-origin-registry-2026-10-12.json) and [four-batch scanning code](maintained_github_origin_scan.py). No source promotion and no public deployment changes.
