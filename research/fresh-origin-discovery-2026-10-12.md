# Fresh-origin discovery: four missing-channel batches — 2026-10-12

## Goal and status

**Discovery first** for the 24 exact IDs missing from the last successful GitHub Pages deployment [#38316450648](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38316450648) (**87/111**). The prior normal full build #38321378327 was blocked by the coverage regression guard and **did not replace production**.

Research workflow: [#38328158569](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38328158569). All four jobs completed; artifacts contain channel-by-channel JSON and direct-access/redirect inspection. We used GitHub's **last successful build** stream-health artifact as a host baseline, with 158 exact known entry hosts after including repo manual and configured source hosts.

Six less-established source files were fetched successfully (FSTV24, SOFAST, MoreScreens, Pixelsports, CricHD, BD) from the `abusaeeidx/IPTV-Scraper-Zilla` repository. **564 playlist entries** were inspected across each independent batch's search scope (108+83+1+19+2+351). Exact channel ID or explicitly marked provisional name-hint matching only; no broad fuzzy channel identity substitution.

## Batch outcome

| Batch | Targets | New host leads | Media/identity/rights status |
| --- | --- | --- | --- |
| A | Bravo, KYW, WCAU, WPVI, Cinemax Classics, HBO Movies | 0 | No fresh matching entries in these six source files |
| B | BET, CBS Sports Network, CNBC, ESPNews, MS NOW, Nicktoons | 4 entry URLs from one previously unseen host family | **All four HTTPS manifest requests failed TLS connection**; zero playlist reads, decoder passes, verified channel identities |
| C | Hallmark Family, Hallmark Mystery, Starz Cinema, Starz Comedy, Starz Edge, Starz Encore Spanish | 0 | No fresh matching entries |
| D | RFD-TV, Smithsonian, SundanceTV, WPHL, NBC Sports Philadelphia Plus, WPSG | 0 | No fresh matching entries; last two remain authorized OTA/provider-connector only |

**New to our previous host inventory:** `o2.greektoday.shop` and `o4.greektoday.shop`, both under **one** apparent service domain `greektoday.shop`. We have not verified original media-lineage independence; this could be an index gateway, mirror or restream.

### Candidate-level facts (research-only; NOT working links)

| Candidate target | Public playlist identity hint | URL | HTTP/HLS outcome |
| --- | --- | --- | --- |
| CBS Sports Network | `Ori2Usacbssport` | `https://o4.greektoday.shop/usa-cbssport.m3u8` | GitHub runner `SSL: UNEXPECTED_EOF_WHILE_READING`; no HLS manifest |
| ESPNews | `Ori2Usespnnews` | `https://o2.greektoday.shop/us-espnnews.m3u8` | Same TLS error |
| CNBC | `Ori2Usacnbc` | `https://o2.greektoday.shop/us-cnbc.m3u8` | Same TLS error |
| MS NOW | `Ori2Usmsnbc` (former MSNBC name; **renamed channel requires identity verification**) | `https://o2.greektoday.shop/us-msn.m3u8` | Same TLS error |

Discovery evidence: [IPTV-Scraper-Zilla FSTV24](https://github.com/abusaeeidx/IPTV-Scraper-Zilla/blob/main/FSTV24.m3u8). GitHub Actions runner error is not definitive proof a stream cannot play from a different network; however, there is **no valid HLS or video-decoder result** to support even an experimental Stremio link at this point.

## Correct classification and follow-up

1. **Four new published *playlist entry* URLs, one newly observed host family, zero confirmed independent original media origins, zero HLS manifests or decoded streams.** No Stremio Local Test link, auto-promotion or QA bypass.
2. Investigate why the `greektoday.shop` TLS connections terminate: is service offline, geo-/runner-denied or a discontinued rehosting gateway? Redirect/media-origin resolution remains **unknown**. Do not assume domain family independence equals upstream media independence.
3. Keep 4x6 matrix and expand original-provider seeds separately for batches **A, C and D**, not another wholesale IPTV-org playlist import. For Philly locals prefer broadcaster/OTA sources and exact affiliate identity. Treat FAST channel selections as separate identities.
4. For batches with legitimate fresh candidates, preflight public HLS, verify actual final media URL and video origin, compare with existing host/path and reject list, then only pass to FFmpeg 60s/repeat/stall QA and rights/exact-channel verification.
5. No automated periodic source hunting is enabled from this PR; workflow is currently PR-run and manual `workflow_dispatch`. Repeat on new curated independent sources rather than endlessly reprobe known failures.

## Separation and safeguards

This is an isolated **draft research PR**. Does **not** edit `config.json`, `manual_sources.json`, production build assembly, deployment guard, local-test catalogs, authenticated tokens, or per-URL kill switches. The source scan rejects embedded credentials, private IPs and account-shaped live stream paths. **No streaming or retransmission of video was performed** in this pass; only HTTP manifest inspections were attempted on newly found URLs.
