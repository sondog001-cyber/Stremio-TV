# Shared-origin recovery diagnostic — October 13, 2026

## Confirmed production issue

Last published logo cleanup deployment succeeded in GitHub Pages run #38485092556 (retry attempt 2). The next scheduled run #38491995485 was blocked with 89 candidates but History.us absent after final decode validation.

In the failed run:
- DisneyChannel.us: `212.5.144.156/disney/index.m3u8` decoded; 720p; previous 5/5 source stability
- NationalGeographic.us: `212.5.144.156:8080/natgeo/index.m3u8` decoded; 720p; previous 5/5 source stability
- History.us@East: `212.5.144.156:8080/history/index.m3u8` returned nominal HTTP success but **zero decoded video frames** in 2 FFmpeg attempts. Error: `Stream map 0:v:0 matches no streams`
- Earlier run #38485092556 first attempt saw access failures across all three, including 403s.
- All three draw from the same 212.5.144.156 host. Distinct alternate hosts do not by themselves establish independent upstream ownership.

## Targeted candidate matrix

The new diagnostic workflow runs these leads **read-only**, comparing the existing host with different-host alternatives:

| Channel | Alternate host | Source / label | Caveat |
|---|---|---|---|
| History East | 40.160.24.53 | THEROCKSSS/sorted-iptv History East | Needs actual East schedule identity, continuity check |
| History East | livex.pop-app.live | iptv-org issue 16051 (2024) | Historical; may be dead |
| History | 170.254.18.106 | iptv-org issue 15900 (2024) | Historical; feed variant not yet verified |
| Disney Channel East | httpstreamer01.dc1.airlinktt.co | Existing curation seed | Validate US East exact programming |
| Disney Channel East | ott.artmott.com | Existing curation seed | Historical |
| Disney Channel East | e3.thetvapp.to | iptv-org issue 27125 (2025) | Historical, provider may reject probes |
| Nat Geo HD East | 198.58.104.90 | iptv-org current USA playlist HDEast | Confirm exact East schedule |
| Nat Geo East | 40.160.24.53 | THEROCKSSS/sorted-iptv East | Confirm exact East schedule |

Known History issue 53046 says 4.30.180.36 link frequently interrupts; do not use it as primary or unproven backup. Latin America feeds, FAST documentary channels and History West are **not** equivalent to these US East feeds.

## Decision gate

1. Run two independent 12-second FFmpeg frame-decode attempts, separated in time, on each current/alternate candidate. Flag no-video, same-frame, and short repeated-loop failures.
2. Verify any candidate that passes with longer (60+ seconds) playback and exact East EPG/programming identity, including source-family independence. Add a manual/local test step if GitHub's runner is geo-blocked.
3. Promote **only** once existing final production playback QA, stream/stall detection, exact channel identity checks, and deployed-channel coverage guard pass. Otherwise leave production unchanged.

The current diagnostic PR changes **only** a research script, research note, and separate workflow. It deliberately does not edit `manual_sources.json`, `config.json`, `deployment_guard.py`, or any playback/source selection.

## Links
- Failed production build and diagnostic artifact: https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38491995485
- Prior successful Pages deploy: https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38485092556
- Upstream candidate list: https://github.com/iptv-org/iptv/blob/master/streams/us.m3u
- Alternate-host directory: https://github.com/THEROCKSSS/sorted-iptv/blob/main/playlists/categories/documentary.m3u

## Actual isolated GitHub runner results

- [Run #38503588376](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38503588376): all three existing 212.5.144.156 streams passed two independent 12-second decodes; each produced 24 changing frames per probe. The 198.58.104.90 NatGeo HD East alternate also passed 2/2; all other alternate URLs failed.
- [Run #38503844952](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38503844952): all three current 212.5.144.156 sources returned **HTTP 403 simultaneously**, confirming correlated shared-host access failures. During the same run, NatGeo HD East at 198.58.104.90 passed 2/2 12-second decoder attempts and an additional 65-second decode with **130 unique frames**, no detected short repeat, exit code 0, and no FFmpeg errors.
- History alternatives: 40.160.24.53 returned HTTP 404; livex.pop-app.live failed DNS; 170.254.18.106 timed out.
- Disney alternatives: Airlink redirected to ottorigin04.dc1.airlinktt.co:1935 and timed out; ott.artmott.com failed DNS; e3.thetvapp.to returned HTTP 404.
- NatGeo East alternate 40.160.24.53 returned HTTP 404.

**Important curation finding:** `NationalGeographic.us@HDEast` is present in the IPTV-org raw USA playlist, but `canonical_tvg_id` treats `HDEast` as a different identity, excluding it from the configured `NationalGeographic.us` allowlist. A narrowly scoped draft [PR #98](https://github.com/sondog001-cyber/Stremio-TV/pull/98) proposes an exact one-ID alias and a no-deploy full staging build to check backup inclusion under existing QA. Do not broaden generic variant normalization across other channels just to address this one.

This confirms improved **availability diversity** for the NatGeo candidate, not necessarily independent provider ownership or actual programme identity. No candidate has been deployed or promoted by this diagnostic PR. Existing production selections and deployment guard remain unchanged.

## AynaScope follow-up — three-channel cross-check

[Run #38504384310](https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38504384310) tested AynaScope's publicly listed History English, Disney, and Nat Geo TV paths *without* attempting to generate or reuse expired playlist access tokens.

- `https://tvsen5.aynascope.net/historyen/index.m3u8`: two 12s decoder passes + 65s continuation (130 unique frames, no short repeat).
- `https://tvsen7.aynascope.net/disney/index.m3u8`: two 12s decoder passes + 65s continuation (130 unique frames, no short repeat).
- `https://tvsen6.aynascope.net/natgeo/index.m3u8`: invalid media input; rejected.
- During the same run, existing 212.5.144.156 feeds and the 198.58.104.90 NatGeo East alternative also passed 65s; during the preceding run, the entire 212.5.144.156 family returned correlated HTTP 403 failures.

**Identity precautions:** AynaScope calls its `disney` feed Disney Channel, while IPTV-org lists the same path under Disney Junior. Do not map either label automatically. AynaScope's `historyen` is labeled English History, *not yet confirmed* as History Channel US East. Visual/EPG comparison is required.

The paired frame-sample workflow collects stills for manual review on this diagnostic branch. No AynaScope feed has been promoted to production.

## Still-frame identity investigation — run #38504770902

The diagnostic workflow captured still frames from each candidate at 640px width. Artifact: https://github.com/sondog001-cyber/Stremio-TV/actions/runs/38504770902/artifacts/11866913481.

- **AynaScope Disney `/disney/`: REJECT as DisneyChannel.us.** Captured video displays an unambiguous **Disney Jr.** on-screen bug. This resolves the conflicting playlist metadata in favor of the Disney Junior identity; passing HLS/FFmpeg tests was not sufficient to identify the network. Do not add or alias it as Disney Channel. It might separately warrant DisneyJunior.us discovery, but is **not** a candidate for this three-channel recovery.
- **AynaScope History English `/historyen/`: INDETERMINATE exact feed.** Frame displays a scanned newspaper/text documentary shot, without a network bug or programme-specific proof that it matches the US East History channel. Remains a research lead, not production-ready.
- **NatGeo HD East at 198.58.104.90:** visible **National Geographic** yellow rectangle branding and documentary footage; this supports network-brand identity but does not independently prove US East feed/programme schedule. Exact timezone/programme identity still requires confirmation.
- **Existing 212.5.144.156 History, Disney, NatGeo feeds:** all three simultaneously returned HTTP **403** during the frame capture, so synchronized side-by-side programme comparison could not be completed. Correlated shared-origin failure reproduced a third time.

**Decision:** Keep History and Disney production selections unchanged; disqualify the AynaScope Disney link as a DisneyChannel.us replacement. Keep NatGeo exact HD East alias in separate draft PR #98 for staging and confirm schedule before merging. Do not weaken the deployment guard.
