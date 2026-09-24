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
- Automated missing-channel, source-yield, and redundancy diagnostics
- Scheduled GitHub Pages deployment with no application server

The addon does not host, proxy, or restream video. It returns validated upstream URLs to Stremio.

## Stream policy

Only allow-listed channels are considered. Before publication, every candidate must pass the configured health checks. HLS streams must expose a valid playlist and readable media segment; live HLS windows must also advance between stability probes. Confirmed decoder-visible playback defects can be exact-URL quarantined even when ordinary reachability checks pass. Failed and untested candidates remain diagnostic-only.

Streams are classified across recent builds:

| Classification | Recent results |
|---|---:|
| Stable | 5/5 passes |
| Backup | 3–4/5 passes |
| Quarantine | 1–2/5 passes |
| Dead | 0/5 passes |

Dead candidates use increasing retry cooldowns. A bounded recovery pass periodically retests candidates for missing channels.

Publicly published signed HLS URLs may be evaluated when they are exposed without authentication. They are rediscovered from their public source and must pass the same validation as every other candidate. Embedded usernames, passwords, account-shaped provider paths, cookies, bearer headers, and private subscription credentials are rejected.

## Stream selection

For each channel, the builder:

1. keeps only exact allow-list matches;
2. removes duplicate effective playback URLs;
3. ranks full-linear content and cross-build reliability;
4. applies channel-specific or default source preferences;
5. prefers backups hosted by an independent provider; and
6. publishes no more than three choices, targeting two HD and one SD stream.

The most reliable candidate becomes Primary. Additional links are labeled Backup 1 and Backup 2.

## Data sources

The builder combines:

- IPTV-org public US and Philadelphia playlists
- selected public backup playlists and targeted source indexes
- official public station/player pages
- recent approved IPTV-org issue submissions
- an optional `manual_sources.json` file
- optional private OTA/provider connectors for local deployments

Secondary sources are isolated: one unavailable playlist does not fail the entire build. Source families are measured over time so consistently unproductive scanners can be reviewed and removed.

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

Scheduled builds refresh sources and guide data automatically. The installation URL does not change between deployments.

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
