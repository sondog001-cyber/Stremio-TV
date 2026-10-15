# At least fifteen additional source spots — 2026-10-15

Inspected **37 additional projects**, read all **63 selected documents**, and parsed
actual channel data from **20 projects** (59,595 source records before deduplication).
The other 17 projects were frameworks, players, source indexes or landing pages,
not 17 additional playable providers. None is counted as a new independent media
origin merely because its maintainer or hostname differs.

Compared against deployed diagnostics artifact 11991554291 (run 38770608444) and
the broader research inventory artifact 11995117504. The frozen input hash list
contains no raw credential-bearing URLs. Unsafe/account-shaped media endpoints,
MAC/device identifiers, expired timestamped links, quarantines and exact-identity
rejections are excluded before probing. Original playlists remain temporary data;
no untrusted project code was executed.

## Actual channel lists/catalogs tested for project compatibility

| Source project | Parsed records | New safe URL occurrences* | Media-test references** |
|---|---:|---:|---:|
| [yowmamasita/usa-tv-next](https://github.com/yowmamasita/usa-tv-next) | 240 | 95 | 0 |
| [xJEYDAin/iptv-scraper](https://github.com/xJEYDAin/iptv-scraper) | 4800 | 25 | 0 |
| [addue06-design/live-tv-scraper](https://github.com/addue06-design/live-tv-scraper) | 1 | 0 | 0 |
| [Kingdavid3g/personal-free-tv](https://github.com/Kingdavid3g/personal-free-tv) | 2334 | 2 | 2 |
| [PeterHeoi/IPTV-USA-HK](https://github.com/PeterHeoi/IPTV-USA-HK) | 20 | 0 | 0 |
| [konanda-sg/Mrgify-Tv](https://github.com/konanda-sg/Mrgify-Tv) | 545 | 2 | 0 |
| [windozalmi/Playlist_IPTV_Pribadi](https://github.com/windozalmi/Playlist_IPTV_Pribadi) | 304 | 0 | 0 |
| [sweetkitten07/US-iptv-playlists](https://github.com/sweetkitten07/US-iptv-playlists) | 1523 | 7 | 6 |
| [Mark-609/IPTV-IPRadio-United-States](https://github.com/Mark-609/IPTV-IPRadio-United-States) | 232 | 28 | 0 |
| [1Gryfox/USA-Repository](https://github.com/1Gryfox/USA-Repository) | 80 | 5 | 0 |
| [se7enfigureinc/iptv-english-north-america](https://github.com/se7enfigureinc/iptv-english-north-america) | 3011 | 0 | 0 |
| [CookCapitalInvest/iptv-playlist](https://github.com/CookCapitalInvest/iptv-playlist) | 3547 | 43 | 0 |
| [JColeLatt/vlc-iptv-playlist](https://github.com/JColeLatt/vlc-iptv-playlist) | 67 | 0 | 0 |
| [Sunstar16/FULL-IPTV-CHANNEL-PLAYLIST](https://github.com/Sunstar16/FULL-IPTV-CHANNEL-PLAYLIST) | 13110 | 7 | 0 |
| [raymo7/iptv-playlist](https://github.com/raymo7/iptv-playlist) | 522 | 0 | 0 |
| [fortvna/iptv](https://github.com/fortvna/iptv) | 2023 | 13 | 4 |
| [skkattamaney/iptv](https://github.com/skkattamaney/iptv) | 2217 | 0 | 0 |
| [MONIR1560/iptv-1](https://github.com/MONIR1560/iptv-1) | 644 | 27 | 0 |
| [karthiceaswar/IPTV](https://github.com/karthiceaswar/IPTV) | 1816 | 9 | 6 |
| [hmripon66/8kiptv-by-techedubyte](https://github.com/hmripon66/8kiptv-by-techedubyte) | 22559 | 0 | 0 |

*New safe URL occurrences include name-only hints and known FAST stand-ins; they
are not eligible recoveries. Exact URLs are deduplicated across lists before
media testing. Different protocols/query variants can still be the same origin.
**A candidate found in two projects can appear in both source-reference counts.

## Playback outcome in the Codex runtime

Tested **17 unique exact-ID, non-FAST candidate combinations**. Fourteen failed
the initial playlist/segment test. Three passed it: NBA TV, VICE TV and Showtime.
NBA TV and VICE passed all five burn-in samples and advanced their live windows,
then failed the unchanged 2-of-3 FFmpeg decoder gate with zero decoded video.
Showtime failed during burn-in and was not decoded. Zero local decoder passes;
zero channel identities certified; zero sources eligible for production promotion.

These are local-runtime results. The independent GitHub research workflow repeats
the metadata reads and normal media checks to distinguish runtime access effects.
A green research job means evidence collection completed, not recovered channels.

## Additional provider/code compatibility checks

Read the current provider implementations in `rajhodedara/live-sport-plugin`.
The DamiTV public catalog responded successfully but returned embed descriptors,
not direct reusable media URLs; no embed-resolver code or relay was adopted.
The CDNLive route includes user/plan parameters and is not adopted as a public
direct-HLS source. Other reviewed tools require supplied playlists/accounts,
aggregate already-known IPTV-org/FAST data, or target unrelated regions/events.

Broadening source discovery did find additional metadata, but this pass has
not yet demonstrated an exact, independently operated, decoded new media origin.
Do not add all these lists to scheduled production just to increase scanner counts.

## Reproduction and restrictions

Run `python assemble_build.py`, then `python research/fifteen_new_spots.py`.
The input manifest records all 63 document URLs and captured content hashes;
the script reports changed upstream content rather than silently assuming the
snapshot is unchanged. It applies existing safety, identity and quarantine rules,
retains name-only matches as counts rather than production links, and probes only
new exact-ID non-FAST candidates. At most 24 media candidates, four workers and
one active probe per host. No credentials, local exceptions or production flags
are manufactured. All206 current-branch unit tests pass.

The research-only PR does not change production sources, the 86-channel floor,
critical channel guard, two-hour cadence, decoder thresholds, version or release
gate. Incorporate only a source with reviewed identity and full repeated QA.
