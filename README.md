# Stremio TV

A free, self-updating **Philadelphia-area cable-style** Stremio Live TV addon.

The goal is intentionally **not** to dump every channel from a giant IPTV list into Stremio. Stremio TV uses a curated allow-list so the guide feels like a normal Philadelphia expanded-basic package: Philadelphia locals plus major national entertainment, news, sports, kids, lifestyle, factual and movie networks.

## What v0.3 does

- Live-channel pages with **Now / Next EPG information in the description**
- Curated whitelist; random FAST, shopping, religious, community and out-of-market local stations are filtered out
- Philadelphia local affiliates only
- Major national cable networks when a usable public stream is present upstream
- **Up to three links per channel** with a target of **2 HD + 1 SD**
- IPTV-org remains the primary source; other source families are backups
- Duplicate channel variants such as `@HD`, `@SD`, `@East` and `@West` are merged without collapsing local affiliates into one channel
- Backup streams can come from a national/raw list even when the primary channel is a Philadelphia local
- Automatic EPG matching for Now / Next programme descriptions
- Favorites and category catalogs
- Automatic rebuild every 15 minutes so the static Now / Next snapshot stays reasonably fresh
- GitHub Pages hosting: no paid server
- A `needs-sources.json` report after each build tells us exactly which curated channels still need HD/SD backups

## Source stack

Stremio TV reads these in priority order:

1. **IPTV-org US public** — primary national source
2. **IPTV-org Philadelphia public** — primary local source
3. **IPTV-org US raw/internal stream list** — preserves alternate URLs that the normal public playlist filters down
4. **Free-TV/IPTV** — quality-over-quantity backup list that favors mainstream free channels and HD where possible
5. **Philadelphia-local source hunt** — WPVI, WCAU, KYW, WHYY, WPHL and WPSG are searched separately across station pages, the experimental OTA relay and local MoveOnJoy affiliate entries
6. **National targeted source-family scanners** — aria-tv US, Shovo US, world_ip_tv US, MoveOnJoy/TVPass forks, FreeCastHub and InsolenceTVGo are searched only for exact national IDs that have no candidate now or were missing in the prior build
7. **Fresh IPTV-org add/remove issues** — recent `check:passed` issues are filtered independently to the remaining local and national exact IDs; removal issues are diagnostic signals and never become stream candidates
8. **User manual sources** — optional public URLs you add to `manual_sources.json`

For Philadelphia locals, the builder prefers full-linear station feeds when available. **WHYY uses an official PBS-hosted live feed.** The local hunt is isolated from premium/national cable discovery and produces `site/diagnostics/philly-local-scans.json`. The WPSG station page is diagnostics-only because its embedded player currently exposes CBS News Philadelphia rather than a verified Philly 57 linear feed. The OTA-relay and MoveOnJoy sources are explicitly unverified and remain lower priority than vetted/public sources. They are included for testing closer-to-broadcast linear coverage rather than treated as authoritative or guaranteed-stable sources.

EPG:

- `https://vcicio.github.io/US-EPG/merged_epg.xml.gz`

The addon does **not** host or proxy video. It returns upstream stream URLs to Stremio.

### Why the FMHY/Reddit web aggregators are not scraped directly

FMHY currently recommends several live-TV web aggregators. Those can be useful when watching manually, but the ones reviewed for this project do not expose a stable, documented M3U/API that is appropriate for a six-hour static GitHub build. Their stream extraction logic and upstream sources can change without notice. Stremio TV therefore uses stable machine-readable playlists automatically and leaves other sources as candidates for manual additions.

Pluto, Samsung TV Plus and Plex-style playlists were also reviewed. They are useful free FAST-TV sources, but they mostly add separate FAST channels rather than the Philadelphia/basic-cable networks this project is trying to reproduce, so they are not enabled by default.

## Passed-only playback policy

Before a stream can appear in Stremio, the builder probes the full curated candidate pool. HLS candidates must return a valid playlist and a readable media segment; direct media URLs must be reachable. Only candidates that pass this automated check are eligible for selection, regardless of source family or whether that source is marked unverified.

A failed or untested candidate stays in diagnostics but is not exposed to Stremio.

## Stream selection: 2 HD + 1 SD

For each curated channel the builder:

1. de-duplicates exact URLs
2. considers only candidates that passed the automated playback check
3. ranks full-linear content and five-build stability before source-family preference
4. applies an exact channel preference when configured, otherwise the default IPTV-org-first family order
5. makes the most reliable selected stream **Primary**, even when it is SD and a newer HD stream is available
6. fills the remaining links toward **2 HD + 1 SD**, preferring a different source family where possible
7. never exposes more than **3 stream choices** for a channel

The exact Primary/Backup decision for every built channel is written to `site/diagnostics/source-ordering.json`, including stability history, matched preference rank and the configured channel rule.

The HD/SD classification is based on the **quality declared by the source playlist**. The static builder does not decode every HLS rendition, so a source label is not a promise about the actual encoder output.

In Stremio the choices look like:

```text
HD 1 • IPTV-org US
HD 2 • Free-TV/IPTV
SD • IPTV-org US Raw
```

## Finding channels that still need a source

Every build creates:

`site/diagnostics/needs-sources.json`

Each entry shows:

- channel name / tvg-id
- number of selected streams
- HD count
- SD count
- `missing_hd`
- `missing_sd`
- current source names

The GitHub Action also uploads the whole diagnostics directory as an artifact. That report is the source of truth for deciding which channels we should manually improve next.

## Adding a public manual backup

Edit `manual_sources.json`:

```json
{
  "streams": [
    {
      "tvg_id": "ExampleChannel.us",
      "name": "Example Channel",
      "url": "https://example.com/live/playlist.m3u8",
      "quality": "1080P",
      "source": "Manual",
      "family": "manual",
      "priority": 1,
      "philly": false,
      "headers": {}
    }
  ]
}
```

Only entries that also match the curated whitelist are kept. **Do not put private provider URLs, usernames, passwords, API keys or tokenized subscription links in this public GitHub repository.** A private authenticated source would need a different deployment design using secrets rather than a static public Pages site.

## Channel curation

The curated package is controlled by `config.json` → `curation`.

Philadelphia locals are centered on:

- WPVI / 6ABC
- WCAU / NBC10
- KYW / CBS Philadelphia
- WTXF / FOX29
- WHYY / PBS
- WPHL / PHL17
- WPSG / Philly 57

National categories include:

- National News
- Sports
- Entertainment
- Home & Lifestyle
- Discovery & Knowledge
- Kids & Family
- Movies

This is a whitelist, so an obscure source being present in an upstream playlist does not make it appear in Stremio TV.

## One-time deployment

1. Put this project in a **public GitHub repository** (suggested name: `stremio-tv`).
2. Open **Settings → Pages**.
3. Set **Build and deployment → Source** to **GitHub Actions**.
4. Open **Actions → Build and deploy Stremio TV → Run workflow**.
5. After deployment the site will normally be:

   `https://YOUR-GITHUB-USER.github.io/stremio-tv/`

6. Install:

   `https://YOUR-GITHUB-USER.github.io/stremio-tv/manifest.json`

The landing page also includes an **Install in Stremio** button.

## After deployment

Normally you do nothing. GitHub Actions rebuilds every 15 minutes. The addon URL does not change, so ordinary source/EPG refreshes do **not** require reinstalling it.

## Favorites / catalogs

Initial catalogs:

- ★ Favorites
- Philadelphia Locals
- Sports
- National News
- Entertainment
- Home & Lifestyle
- Discovery & Knowledge
- Kids & Family
- Movies

The main live-TV catalog contains the entire curated package. Programme rows are no longer exposed as selectable episodes; EPG data is used to enrich each channel description with Now / Next information.

## Diagnostics

The build writes:

- `status.json`
- `diagnostics/build-info.json`
- `diagnostics/source-results.json`
- `diagnostics/channels.json`
- `diagnostics/needs-sources.json`
- `diagnostics/targeted-source-scans.json`
- `diagnostics/channel-changes.json`
- `diagnostics/stream-stability.json`
- `diagnostics/epg-matches.json`
- `diagnostics/epg-unmatched.json`

Every manifest, channel metadata response, and stream response carries the same immutable build ID, addon version, UTC build timestamp, and—on GitHub Actions—the source revision/run identity. This makes it possible to identify exactly which deployment Stremio is displaying when testing a stream.

Optional playlist failures do not take down the whole build. The two primary IPTV-org public playlists remain required; secondary sources are allowed to fail independently.

## Local test

Network build:

```bash
python build.py
python -m http.server 8080 --directory site
```

Offline self-test:

```bash
python -m unittest discover -s tests -v
```

## Still intentionally separate

- Highfly premium sports stays separate for now.
- Stremio TV does not proxy or restream video.
- Stremio controls the in-app skin/layout.


## Discovery-only source notes

- **DaddyLive / DLHD (dlive.sx)** may be used as a **manual coverage reference only** to see which channels exist elsewhere.
- It is **not** used as a runtime playback source in Stremio TV.
- Stremio TV continues to prefer public/authorized machine-readable sources such as IPTV-org and other free public playlists.
- If a curated channel is missing, add an authorized public M3U8/M3U source to `manual_sources.json` rather than scraping or embedding third-party premium streams.


### Philadelphia linear-feed policy

The preferred order for local stations is:

1. official full-linear station feed when one is available
2. existing vetted/public source
3. experimental OTA-style relay candidate
4. MoveOnJoy affiliate fallback
5. official 24/7 local-news stream only when a true linear feed is unavailable

Current intent:

- **WPVI / 6ABC** — test OTA-style linear + MoveOnJoy candidates
- **WCAU / NBC10** — test OTA-style linear + MoveOnJoy candidates
- **KYW / CBS3** — test OTA-style linear + MoveOnJoy candidates
- **WHYY / PBS 12** — official PBS-hosted WHYY live feed
- **WPHL / PHL17** — test OTA-style linear candidate
- **WPSG / Philly 57** — no credential-free linear candidate approved yet
- **NBC Sports Philadelphia Plus** — no free linear candidate approved yet

No private usernames, passwords, subscription tokens, or credentials from third-party playlists are committed to this public repository.
