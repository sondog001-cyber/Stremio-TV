# AynaScope Nicktoons East — programming identity & source provenance audit (2026-10-13)

**Disposition: TECHNICALLY PLAYABLE, NOT ELIGIBLE FOR PRODUCTION OR LOCAL TEST.** The source is a legitimate *working transport endpoint*, but US Nicktoons East **episode/program match**, root broadcaster origin and permission to embed its direct stream remain unverified. This is a research-only finding on [draft PR #88](https://github.com/sondog001-cyber/Stremio-TV/pull/88); it does not modify config, production, QA exceptions or the existing `aynascope.net` local-test exclusion.

## 1. What the network/decode evidence proves

- Historical source: [IPTV-org issue #48485, submitted August 16 2026](https://github.com/iptv-org/iptv/issues/48485) labels `http://tvsen7.aynascope.net/nicktoons/index.m3u8` as `Nicktoons.us@East`, reports 720p, and received automated `check:passed` / `approved` labels. **These labels do not certify video episode identity or publishing/redistribution permission.**
- [Six-candidate research workflow #38412786788](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38412786788) confirmed HTTP 200 and genuinely advancing HLS sequence 77600→77603; the final manifest/media/segment hostname stayed `tvsen7.aynascope.net`, proving that hostname delivered a readable video stream.
- [Run #38413345691](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38413345691), [#38413401537](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38413401537) and [#38413435716](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38413435716) each ran three independent 60s FFmpeg sampling windows. All 9/9 decoded 60 unique one-second sampled frames with no 2–4s clip-loop or multi-second freeze. **Short-window technical quality is good**, although these closely timed sessions do not constitute multi-day uptime.
- A separate [on-screen OCR/ffprobe-only workflow #38416906639](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38416906639) decoded another 57s and inspected 5 transient in-memory frames. **1/5 OCR frames contained the word `spongebob`**, **0/5 showed recognized text `nicktoons`**, and no episode or channel bug was independently reviewed. Another [full repeat #38417084626](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38417084626) recognized neither name. **A one-off series word is not channel authentication.** Crucially, neither workflow uploaded screenshots, frames, audio or transcripts; only keyword-presence flags.
- Actual FFprobe metadata: **768×432 video (H.264), AAC audio, embedded `closed_captions: 0`**. This is **432p**, *not* the claimed 720p in the iptv-org submission. It may be a downscaled relay; it does **not** prove an upstream transcoding method.
- Compare existing deployed Nicktoons on `41.205.93.154`, which had 2/3 passing windows and on the third showed two/three-second loops plus an eight-second freeze. AynaScope is a distinct delivery hostname, but **not independently proven to be a distinct original broadcaster input**.

## 2. How far exact US East identity has been validated

| Required evidence | Observed | Verdict |
| --- | --- | --- |
| GitHub TVG identity claim | `Nicktoons.us@East` on iptv-org issue #48485, repeated in playlist mirrors | **Source label only** |
| Cartoon/series clues from actual video | OCR saw `spongebob` on one transient still; not repeatably reproduced | **Weak supporting clue** |
| Visible Nicktoons US on-screen bug | OCR failed to recognize; no human screenshot reviewed | **Not confirmed** |
| Specific episode at a fixed Eastern-time broadcast slot | No trustworthy *date+time+episode* comparison; [TV Passport East](https://www.tvpassport.com/tv-listings/stations/nicktoons-east/2010) and [AmericaTVListings](https://americatvlistings.com/en/us/nicktoons) have stale/partial snapshots for Oct 13 in retrieval | **Not confirmed** |
| East versus West feed | No episode-offset or schedule delta corroborated | **Not confirmed** |
| 24/7 genuinely current linear output versus delayed or looped curated program | Nine clean 1-minute samples close in time; no days-long continuity or schedule transitions sampled | **Not confirmed** |

**Never count `SpongeBob` as proof**: SpongeBob airs on multiple Nickelodeon family channels and FAST services, and frame OCR cannot disambiguate a series, episode, East/West feed or tape delay by itself.

## 3. What the origin-host evidence really establishes

1. **Ayna Scope is a real OTT/IPTV/CDN/aggregation vendor.** Its [official site](https://aynascope.com/index.html), [Live TV aggregation product](https://aynascope.com/livetv.html), and [projects list](https://aynascope.com/projects.html) openly describe multisource streaming/aggregation and point to **AynaOTT**, with 100+ premium live TV channels. [AynaOTT's own contact page](https://aynaott.com/contact.php) describes a subscription model.
2. The **`aynascope.net` hostname is brand-consistent** with the vendor's `aynascope.com` identity, but public evidence does **not conclusively establish legal ownership or operator control** of that exact `.net` domain. Do not assert that an official AynaScope/Paramount partnership has been proven.
3. The exact `tvsen7.aynascope.net` host appears in different-country IPTV-org playlist entries: [UK Nickelodeon](https://github.com/iptv-org/iptv/issues/45425), [India Assam Talks and other broadcasters](https://github.com/iptv-org/iptv/blob/master/streams/in.m3u), [Pakistan Madani TV](https://github.com/iptv-org/iptv/blob/master/streams/pk.m3u), and US Nicktoons. This supports a **multi-channel aggregation/distribution gateway** interpretation, *not* a direct Paramount-owned Nicktoons CDN.
4. One unrelated host sibling in this family previously had a [wrong-channel-ID rejection](https://github.com/iptv-org/iptv/issues/45691) and a [broken-link report](https://github.com/iptv-org/iptv/issues/45754). These are general **label/provenance warnings**, not proof that the current Nicktoons entry is mislabeled.
5. **No public broadcaster authorization or direct-reuse permission** for the specific Nicktoons URL has been found in the iptv-org issue or Ayna Scope/AynaOTT product terms reviewed. Unknown permission is **not equivalent to a confirmed infringement**, but the project's policy requires provenance and permission *before* promotion.
6. "Direct video" in the addon would be **direct to this third-party aggregation endpoint**, not direct to a verified Paramount origin. HLS playlist/segment hosts sharing `aynascope.net` does not identify who ingests or upstream sources the original show.

## 4. Remediation and go/no-go criteria

**GO only after both identity AND origin/use permission are documented** (plus local-client QA):
- Confirm content against **two specific US East episodes at known Eastern slots** from a current independent EPG, preferably at different programme boundaries. Visual comparison should be done privately without committing any screenshots/segments to GitHub or uploading copyrighted frames. Identify US Nicktoons channel bug and ensure East, not West/international or Nick Jr/TeenNick.
- Establish the `.net` endpoint's actual operator (through provider ownership/support and a verified relationship) and obtain an explicit allowance for third-party direct HLS playback/link inclusion where applicable, rather than presuming public GET means permission.
- Verify codec/resolution expectations (current observed 432p), local Stremio playback, decoder loop/reliability at materially separated hours/days, and failure/kill-switch behavior.
- Until then, keep `config.local_test_catalog.exclude_provider_hosts` excluding `aynascope.net`. No stream priority changes, no Local Test, no production.
- If permission cannot be verified, treat as a **research-only useful lead** and continue looking for a genuinely approved alternate origin.

### Verdict

**Technical decode: PASS.** **Single program title OCR: weak positive clue only.** **Exact US Nicktoons East programming: UNVERIFIED.** **Broadcaster-owned original CDN: UNVERIFIED.** **Reuse permission: UNVERIFIED.** **Production / Local Test eligibility: NO.**
