# Stremio TV

A self-updating, Philadelphia-focused live-TV addon for Stremio. It combines a curated channel list, automatic stream validation, XMLTV guide data, and static GitHub Pages hosting.

## Features

- Philadelphia broadcast affiliates and selected national channels
- Native Stremio Live TV EPG generated from XMLTV, including scheduled programme metadata
- Locally cached, normalized square channel logos with consistent padding and fallbacks
- Favorites and category catalogs
- Up to three playback choices per channel
- Measured HLS resolution rather than source-label quality alone
- Cross-build stream stability scoring and retry cooldowns
- Effective-URL deduplication and independent-provider backup preference
- Exact channel-identity validation
- Five-probe, 60-second burn-in for new/unproven candidates before promotion
- 2-of-3 FFmpeg decoder survival gate for direct MPEG-TS/media streams
- Final decoded Primary playback QA with automatic backup promotion
- Automated missing-channel, source-yield, and redundancy diagnostics
- Build-time refresh of short-lived public signed HLS candidates through a pinned resolver
- Scheduled GitHub Pages deployment with no application server

The addon does not host, proxy, or restream video. It returns validated upstream URLs to Stremio.

## Stream policy

Only allow-listed channels are considered. Before publication, every candidate must pass the configured health checks. New, Quarantine, and Dead candidates are sampled at 0, 15, 30, 45, and 60 seconds before promotion; any failed intermediate probe rejects them. Previously established Stable or Backup URLs keep the lower-churn two-probe continuity check across the same validation window. HLS streams must expose a valid playlist and readable media segment, and live HLS windows must advance across the validation window. Direct non-HLS media must sustain at least 10 seconds of decoded video in at least 2 of 3 independent 12-second FFmpeg connections; immediately replayed 2–4 second clips hard-fail before stability scoring or selection. After selection, the chosen Primary is decoded end-to-end for a final QA pass across both HLS and direct transports. A failed Primary is removed and the next backup is tested/promoted; a channel with no decoded passing choice is omitted for that build. Confirmed decoder-visible playback defects can be exact-URL quarantined even when ordinary reachability checks pass. Failed and untested candidates remain diagnostic-only.

Streams are classified across recent builds:

| Classification | Recent results |
|---|---:|
| Stable | 5/5 passes |
| Backup | 3–4/5 passes |
| Quarantine | 1–2/5 passes |
| Dead | 0/5 passes |

Dead candidates use increasing retry cooldowns. A bounded recovery pass periodically retests candidates for missing channels.

Publicly published signed HLS URLs may be evaluated when they are exposed without authentication. Short-lived resolver-backed URLs are refreshed during each scheduled build, carry only the public request headers required by the upstream player, and must pass the same burn-in, continuity, and decoded Primary QA as every other candidate. Their cross-build stability is tracked by logical channel/server identity rather than the rotating signature, while current playback health remains mandatory. Freshly signed candidates bypass dead-URL cooldown so an expired signature cannot suppress a newly resolved URL. Embedded usernames, passwords, account-shaped provider paths, cookies, bearer headers, and private subscription credentials are rejected.

## Stream selection

For each channel, the builder:

1. keeps only exact allow-list matches;
2. removes duplicate effective playback URLs;
3. ranks full-linear content and cross-build reliability;
4. applies channel-specific or default source preferences;
5. prefers backups hosted by an independent provider; and
6. publishes no more than three choices, targeting two HD and one SD stream.

The most reliable candidate becomes Primary. Sources explicitly marked as primary-deprioritized (currently SourPatchKid-derived direct streams) are kept out of Primary when another passing provider exists, but may remain as a last-resort Primary when they are the only source and have passed the decoder gate. Additional links are labeled Backup 1 and Backup 2.

## Data sources

The builder combines:

- IPTV-org public US and Philadelphia playlists
- selected public backup playlists and targeted source indexes
- official public station/player pages
- recent approved IPTV-org issue submissions
- a pinned build-time public stream resolver for selected missing exact IDs
- an optional `manual_sources.json` file
- optional private OTA/provider connectors for local deployments

Secondary sources are isolated: one unavailable playlist does not fail the entire build. Source families are measured over time so consistently unproductive scanners can be reviewed and removed. Missing-channel hunting is prioritized toward runner/geo-blocked exact IDs first, then cooldown/quarantined gaps, so scarce discovery work focuses on the most recoverable channels.

## Channel curation

The package is controlled by `config.json` under `curation`. It is a whitelist, so an upstream entry does not automatically appear in Stremio.

Philadelphia coverage centers on WPVI, WCAU, KYW, WTXF, WHYY, WPHL, and WPSG. National channels are grouped into news, sports, entertainment, lifestyle, factual, kids, and movies.

## Adding a public manual source

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

Only exact curated IDs survive the identity gate. Never commit private provider URLs, credentials, API keys, cookies, authorization headers, or subscription tokens.

## Private connectors

Channels requiring an antenna tuner or authorized provider account are kept separate from the public deployment.

1. Copy `private_connectors.example.json` to the gitignored `private_connectors.json`.
2. Configure the documented environment variables for an HDHomeRun and/or authorized provider playlist.
3. Run `python private_connectors.py`.
4. Build a private site:

```bash
STREMIO_TV_PRIVATE_SOURCES_FILE=private_sources.generated.json \
  python build.py --output private-site
```

The public GitHub Actions build refuses to load the private overlay. Serve private output only from infrastructure you control.

## Deployment

1. Place the project in a public GitHub repository.
2. Open **Settings → Pages**.
3. Select **GitHub Actions** as the deployment source.
4. Run **Build and deploy Stremio TV** from the Actions tab.
5. Install the generated manifest:

```text
https://YOUR-GITHUB-USER.github.io/YOUR-REPOSITORY/manifest.json
```

Scheduled builds refresh sources, short-lived public signed stream URLs, and guide data automatically. The resolver runs only inside the build job; the deployed addon remains static GitHub Pages and publishes validated direct upstream URLs with the required public request headers. The installation URL does not change between deployments.

## Local development

Assemble and test the builder:

```bash
python assemble_build.py
python -m unittest discover -s tests -v
```

Run a network build and preview the static site:

```bash
python build.py
python -m http.server 8080 --directory site
```

## Diagnostics

Build output includes `status.json` and structured reports under `site/diagnostics/`.

| Report | Purpose |
|---|---|
| `channel-changes.json` | Recovered, lost, stable, and still-missing channels |
| `missing-source-diagnostics.json` | Actionable missing-channel classifications |
| `stream-health.json` | Current candidate probe results |
| `primary-playback-qa.json` | Final decoded Primary checks, promotions, and dropped channels |
| `daddylive-resolver.json` | Build-time signed-stream resolution status by exact target ID |
| `stream-stability.json` | Cross-build URL reliability history |
| `source-family-scoreboard.json` | Candidate, passing, selected, and recovery yield by source |
| `source-ordering.json` | Primary/backup selection details |
| `host-redundancy.json` | Independent-provider and fragile-mirror coverage |
| `quality-measurements.json` | Declared and measured stream quality |
| `philly-recovery.json` | Philadelphia runner/client verification state |
| `targeted-source-scans.json` | Targeted public source-scan results |
| `epg-matches.json` | Successful guide mappings |
| `epg-unavailable.json` | Intentionally unavailable guide mappings |
| `epg-unmatched.json` | Remaining guide mismatches |

Each generated response includes the addon version, UTC build timestamp, build ID, and source revision so a deployed result can be traced to its exact build.

## Security and legal notes

- Use only streams you are authorized to access.
- Do not commit credentials or private provider material.
- The project does not bypass DRM or manufacture authorization tokens.
- Public availability is not a guarantee of ownership, reliability, or regional availability.
- Upstream rights holders and source maintainers control availability.
