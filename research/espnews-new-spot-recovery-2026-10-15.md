# ESPNews recovery from the additional-source review

The additional-source investigation inspected 37 projects, including 20 actual
channel catalogs. It found an exact `ESPNews.us` candidate in
[sweetkitten07/US-iptv-playlists](https://github.com/sweetkitten07/US-iptv-playlists/blob/main/playlist.m3u):
`http://41.205.93.154/ESPNNEWS/index.m3u8`.

The host was already known to the project; this exact media URL was not in the
compared deployed or broader scrub inventories. This is a newly found candidate
for a missing identity, not proof of a newly independent provider. Other channels
on this host remain subject to their own existing quarantines.

## Actual validation

- [Research run 38782282637](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38782282637),
  artifact 11995927775: segment-aware HLS health, five successful burn-in probes
  across 60 seconds, advancing live window, unchanged normal 2-of-3 direct-media
  decoder gate passed with repeat detection enabled.
- [Long-window run 38783197891](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38783197891),
  artifact 11996732847: three independently opened 60-second windows, each decoded
  the full 60 seconds, no detected short repeat or frozen sample, successful
  before/after HLS checks and advancing live window in every window.
- Downloaded and visually inspected the runner's actual frames. The first window
  shows the **ESPNNEWS** on-screen ticker/logo and **First Take** branding; other
  samples include commercial breaks. The configured current US guide was freshly
  read at 18:10 UTC: `ESPNEWS.HD.us2` lists First Take from 18:00 to 20:00 UTC,
  matching the captured viewing interval. This supports the exact US service and
  current schedule; it does not establish indefinite future correctness.
- HLS measurement: 1280x720. The runner's effective media URL is
  `http://41.205.93.154/ESPNNEWS/tracks-v1a1/mono.m3u8`.
- The Codex runtime's first probe failed; the independent runner evidence is
  recorded separately and does not assert universal accessibility.

## Scoped production candidate

Add one normal manual candidate under `ESPNews.us`, with playlist attribution and
no special headers, credentials or local-verification flag. Add the exact guide
alias to the already observed `ESPNEWS.HD.us2` service. The normal builder still
must establish its own health, burn-in, stability and final Primary decoder result.
No source is force-selected, no cooldown is cleared and no QA result is overridden.

The same research found NBA TV and VICE TV streams that decode successfully.
Their captured material did not establish the configured US programme schedule,
so they are held outside this production change. A working decoder alone cannot
prove channel identity.

All 203 existing main-branch tests pass. Require a current-head real catalog build
with the unchanged 86-channel/critical-ID guard and inspect the actual ESPNews
Primary/guide result before merge. This candidate is not yet a published recovery.
The original 111-channel lineup, production schedule, version and release gate
remain unchanged; the last confirmed deployment remains 87 channels.
