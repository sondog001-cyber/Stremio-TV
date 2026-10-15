# Automatic playlist discovery

The two-hour production build already refreshes its configured public playlists,
national targeted source lists, Philadelphia sources, public seed candidates and
IPTV-org issue signals. Newly encountered candidates for missing/unstable channels
enter the ordinary safety, identity, health, burn-in, decoder and selection gates.
GitHub-wide code search remains disabled because it hit sustained secondary rate
limits. Playlist scraping does not depend on an active ChatGPT conversation.

The `playlist-scrub` job adds a persistent view of changes across **all original
111 identities**, including potential backups for currently healthy channels.
It scans the configured M3U lists (48 distinct document URLs at implementation),
deduplicates repeated exact channel/URL/header combinations, and distinguishes:

- Known candidates from the current production attempt or prior scrub inventory.
- New candidates since a retained trusted inventory.
- An initial inventory when historical evidence is unavailable.
- Previously unseen provider hostnames, which do **not** prove independent media
  ownership or delivery origins.

Sources use explicit playlist IDs and configured ID aliases; West variants,
unrelated FAST/foreign networks and wrong affiliates are excluded. Credential
paths, authentication headers, configured kill switches and exact playback
quarantines are applied before storing or probing candidates. Unsafe media URLs
are counted without being copied into the evidence artifact.

After each production attempt the scrub checks up to three unseen, queued
candidates with a segment-aware HLS probe and the existing normal direct-media
FFmpeg/repeat detector. Missing channels and newly observed hosts take priority.
The queue persists across runs, and current-build candidates are not redundantly
probed. This is initial media triage: it does not perform full promotion burn-in,
confirm programming identity, grant local exceptions, change source priority,
write production configuration, or count as a release-qualified recovery.
Ordinary builder discovery continues to reconsider its configured sources on
subsequent builds. Healthy-channel backup leads can be reviewed from the scrub.

## Execution and evidence

The job uses the existing `7 */2 * * *` production schedule. It starts **after**
`build` and `deploy`, even if either was blocked, and never gates Pages. It has
read-only repository/Actions permissions, a 12-minute timeout and advisory failure
behavior. It does not create another two-hour timer or enable GitHub code search.

Open a production Actions run and read **Playlist scrub (advisory)** in its job
summary. Download its **playlist-scrub** artifact for:

| File | Contents |
|---|---|
| `playlist-scrub.json` | Source success/errors, candidate novelty, provenance and bounded probe results |
| `playlist-scrub.md` | Compact counts and limitations |
| `playlist-scrub-state.json` | Persistent seen URLs and queued/completed media triage |

The next scrub restores the newest retained artifact from this repository's
default-branch production workflow, including runs whose deployment guard failed.
PR runs cannot supply state. Artifact history is retained for 14 days; inventory
is bounded to 5,000 recently observed entries. If prior state is missing,
expired, corrupt or inaccessible, the report says so and creates an initial
inventory rather than claiming that every old stream is newly discovered.
Incomplete source reads never establish a removal or wipe earlier observations.

## What still benefits from research

The scrub finds changes **inside the configured sources**. Finding entirely new
projects, player APIs or independently operated media origins still requires
targeted research and source review. A newly found playlist or hostname often
recycles the same upstream media. Identity, actual programming and resilience
must be established before considering a new feed a recovered channel or backup.

To reproduce without GitHub API history:

```sh
python assemble_build.py
python playlist_scrub.py --baseline-dir site/diagnostics --probe-limit 0 --out scrub-results
python playlist_scrub.py --baseline-dir site/diagnostics --previous scrub-results/playlist-scrub-state.json --probe-limit 0 --out scrub-replay
```

The CLI performs public metadata reads; `--probe-limit 0` skips media triage.
No API token is sent to playlist or media hosts. GitHub authentication is used
only to read trusted prior artifacts, with bearer credentials stripped on the
artifact download redirect.
