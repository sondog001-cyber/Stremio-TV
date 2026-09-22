# Stremio TV TODO

Working roadmap for the next development pass.

## UI / presentation

- [ ] **Clean up the stream-choice column**
  - Keep the selectable stream title short enough for Stremio's narrow right-side panel.
  - Proposed title format: `Primary • 720p`, `Backup 1 • 1080p`, etc.
  - Move source family, health/stability details, and builder-check text into the secondary description instead of repeating them in the title.
  - Avoid duplicated text such as `IPTV-org` appearing in both the title and description.
  - Keep names readable on desktop/TV layouts without relying on Stremio widening the panel.

- [ ] **Normalize every channel icon/poster**
  - Generate a consistent square local asset for each channel during the build.
  - Center the original network logo on a fixed-size canvas with consistent padding.
  - Preserve aspect ratio; never stretch or crop the logo.
  - Prefer transparent/neutral padding so wide logos and tall logos appear at a similar visual scale.
  - Fall back gracefully when an upstream logo is unavailable.
  - Point Stremio metadata at the normalized local asset instead of the raw upstream image.

- [ ] Review channel display names for readability/spacing (for example `FoxNewsChannel` -> `Fox News Channel`) without changing the underlying exact tvg-id identity.

## Source stability / diagnostics

- [x] **Cross-build source stability history**
  - Track approximately the last 5 builds per URL.
  - 5/5 passes = Stable / preferred Primary.
  - 3-4/5 = usable Backup.
  - 1-2/5 = quarantine / low priority.
  - 0/5 = dead until it recovers.

- [x] **Recovered / lost channel report**
  - Recovered this build.
  - Lost this build.
  - Still missing.
  - Stable for N consecutive builds.
  - Include the source family that caused a recovery/loss.

- [x] Use stability score when choosing Primary vs Backup rather than relying only on a single successful build.

- [x] Clean up optional source URLs that return permanent 404s (removed stale Buddy/Tubi paths).

## Source hunting

- [ ] Continue exact-channel hunting only after stability tracking is in place.
- [x] Keep Philadelphia locals as a separate source hunt from national premium cable.
- [ ] Prioritize fresh machine-readable sources and public HLS mirrors.
- [x] Scan IPTV-org issues, aria-tv, Shovo, world_ip_tv, MoveOnJoy/TVPass forks, and FMHY-adjacent caches only for remaining exact IDs.
- [ ] Keep browser-only/tokenized/DRM/authenticated sites as research indexes only; never expose protected credentials/tokens in the public addon.
- [ ] Re-run the exact missing-channel list after each stable build and target only the remaining gaps.

## Quality / metadata

- [ ] Keep exact identity rules so FAST lookalikes cannot satisfy premium/full-linear targets.
- [ ] Improve canonical channel metadata and category labels where source names are messy.
- [ ] Consider adding resolution/codec detail only when it can be measured reliably rather than trusting source labels.
