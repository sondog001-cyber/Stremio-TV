# Targeted provider discovery

## What existed on main

As inspected at `754381e37aee6a80d49e1af0a4e8e4b3de427e7c`, the builder already has
targeted source-family scanners, public-player adapters, official-player scans,
Philadelphia scans, exact-ID curation and media QA. `provider_discovery.py` searches
six broad GitHub repository queries, reads up to two playlist paths per project,
and retains rotating catalogs. `playlist_scrub.py` inventories exact IDs and has
bounded advisory media triage. These capabilities are not new in this change.

Open PR #130's actual diff adds missing-channel repository queries, measured catalog
ranking and reporting. It is unmerged. Research PRs #111, #123, #128 and #131 contain
separate research scripts or fixed candidate inputs; they are not current-main
behavior and this change does not merge their production or research changes.

## New behavior

`targeted_provider_discovery.py` provides an opt-in research path, outside the
production builder and the existing broad catalog scrub. It reads current published
status, channel-change diagnostics, channels and stream-health inventory. Stale,
empty, inconsistent snapshots fail closed. Names, explicit configured aliases,
quality variants and affiliate identities are reconciled against the curated
allowlists. Only currently missing exact channels become targets. West feeds and
different affiliates cannot satisfy national/East targets.

Search rotates readable names, known aliases and exact IDs through GitHub repository
search, sorted by recent upstream activity. It reads small playlists, READMEs,
HTML and JSON documents from the returned repository tree revision. Channel-labelled
public page links and advertised iframe chains are followed to a maximum depth of
two. Literal public HLS URLs are collected; no scripts are executed, numeric stream
IDs guessed, tokens manufactured or protected players unlocked. Playlist IDs must
match an exact configured target. Page-derived identities remain provisional.

Observed unfamiliar media families prioritize candidate review and subsequent
project review. Two repository exploration slots prevent previous winners from
starving new projects. Repository timestamps and tree revisions are attributed.
Neither recent maintenance nor an unfamiliar host establishes working playback.

Media endpoints are grouped across subdomains and explicit known mirror families.
Recognized token expiry/signature query changes do not create new endpoints;
channel selector query parameters remain distinct. Unrecognized signature formats,
including tokens embedded in paths, still require manual grouping.
This is conservative lead grouping, not proof of
independent infrastructure. Unknown cross-domain mirrors can remain unrecognized.

Each candidate retains discovery timestamps, exact target, provider family, source
documents, repository revision, relevant-declaration fingerprint and prior test
outcomes. `--previous` accepts its own journal or an existing playlist-scrub state.
Unchanged failed evidence is marked ineligible for another probe. A changed endpoint,
headers or observed player-library declaration can make it eligible again.
Unrelated repository edits and token rotations alone do not erase failed history.
History is capped at 2,000 endpoints, 20 attributions per endpoint, and 100 project
scores. Keep and reuse the journal; a run without prior state cannot know absent
historical failures. Eligibility is advisory for a subsequent validator: this
command itself does not perform playback probes.

## Counts and limits

Reports separate search result records reviewed, grouped provider leads, exact-ID
candidates, manifest/segment passes, sustained decoder passes, identity-confirmed
feeds and staging-published recoveries. The last four are **zero** here: this tool
does discovery only, and never upgrades old test evidence into current approval.
Backup candidates are separately reported as zero because published channels are
excluded. A page/playlist declaration is not a programming identity confirmation.

Default budgets: 120 seconds, three queries, six repository-target inspections,
16 documents, 2 MB per document and eight seconds per HTTP/API request. A request
already in flight may overrun the soft wall-clock deadline by its bounded timeout.
At most three files per project are examined, so this is intentionally incomplete.
Only API requests to GitHub receive its API token; public document requests use a
separate client with validated redirects and no API credentials.

This adds searches and public-player discovery paths; it does not add any feeds to
production. It does not search the whole web, execute dynamic player scripts, verify
channel programming, decode media, run staging or promote candidates. A normal
validation/staging review remains necessary before a recovery can be counted.

## Run

```sh
python assemble_build.py
python targeted_provider_discovery.py --out targeted-provider-results
python targeted_provider_discovery.py --previous targeted-provider-results/state.json --out next-results
```

For offline replay, `--snapshot-dir` accepts the four named JSON files saved from
the current published snapshot. It still enforces freshness and consistency.
An existing scrub state can be supplied via `--previous` to retain known failures.

The manual **Targeted missing-channel provider research** workflow preserves its
branch-specific journal and output artifacts. It has no schedule, deployment job
or source-file write. The normal production schedule, source selection, HGTV
exception, kill switches, quarantines and deployment guards are unchanged.

Focused tests cover live missing-target selection, aliases and affiliate separation,
search rotation, exact filtering, public-player traversal, mirror/signature dedup,
failed-history import, material-change eligibility, exact-ID JSON, credential-shaped
route rejection, bounded operation and honest
zero promotion/verification counts. The existing PR workflow also runs the full
suite and guarded staging catalog/logo audit before merge.
