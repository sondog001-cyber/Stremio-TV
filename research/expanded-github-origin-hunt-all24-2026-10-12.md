# Expanded GitHub origin hunt — all 24 missing IDs (2026-10-12)

This experiment broadens the [existing four-batch research scanner](fresh_origin_discovery.py) from **9** GitHub playlist/generator entry points to **17**, retaining all 24 exact curated IDs and the established A–D 6-channel groupings. No production selection, stremio local-test catalog, or source policy changes.

## Search targets

- **A —** Bravo, KYW, WCAU, WPVI, Cinemax Classics, HBO Movies.
- **B —** BET, CBS Sports Network, CNBC, ESPNews, MS NOW, Nicktoons.
- **C —** Hallmark Family, Hallmark Mystery, Starz Cinema, Starz Comedy, Starz Edge, Starz Encore Spanish.
- **D —** RFD-TV, Smithsonian Channel, SundanceTV, WPHL, NBC Sports Philadelphia Plus, WPSG.

## New GitHub discovery families

| Github project | Input / purpose | Independence caveat |
|---|---|---|
| [nightah/daddylive](https://github.com/nightah/daddylive) | Maintained scraped playlist and media host output | Dynamic `newkso.ru` / premium-number mirrors may be already known. Origin/Referer can be public, but headers alone don't prove decodability, as WCAU #277 403 showed |
| [spliff123/tv](https://github.com/spliff123/tv) | Updated curated USA sources | Many MoveOnJoy paths; known family must not count as new |
| [Tateguru/Outdoor-and-Wild](https://github.com/Tateguru/Outdoor-and-Wild) | News playlist including current MS NOW channel ID | A `41.205.93.154/MSNBC` direct-IP entry has appeared in GitHub extractor research; need identity/media verification |
| [iptvmate/iptvchannels](https://github.com/iptvmate/iptvchannels) | Channel-specific gateway entries | `ch.iptvmate.net` gave TLS errors in Philly study; different hashed paths may still share one gateway |
| [arquerido/mych](https://github.com/arquerido/mych) | TV247 scraped playlist | A hosted `memfs` playlist can be timed/looped; full segment progression and identity required |
| [judy-gotv/iptv](https://github.com/judy-gotv/iptv) | Updated variant MoveOnJoy paths for ESPNews/Smithsonian | Deliberate historical family control; not an original new host |
| [MarkMCFC/TMDB-To-VOD-Playlist-main](https://github.com/MarkMCFC/TMDB-To-VOD-Playlist-main) | Alternate DaddyLive resolver output | Same-family duplicate control; never count as independent |
| [marasiganjosephursaiz-crypto/IPTV-PH-AND-US.M3U](https://github.com/marasiganjosephursaiz-crypto/IPTV-PH-AND-US.M3U) | US miscellaneous stream references | Heavy jmp2/pluto proxy references; distinguish FAST from exact premium linear |

## Tests and promotion boundaries

The runner checks only public URLs without user/passwords, credential-bearing account-shaped paths, cookies or DRM keys, and discards the private-only WPSG and NBC Sports Philadelphia Plus IDs before probing. Each batch probes at most two new host families **per channel**, checking actual HLS media playlist advancement and a readable segment prefix after redirect resolution. The `entry_host` is explicitly not an independent origin: a new final segment host may still be an unrelated relay or an equivalent CDN mirror. **No source is eligible for publication or a Stremio Local Test merely because this research preflight passes.** Actual legal/authorized access, exact identity, FFmpeg 60s playback/loop QA and user's local network corroboration remain further gates.

### Excluded known stale families

Old LocalBTV/MyBTV copy lists, obsolete `theus6tv` domains, MoveOnJoy clones, expiring paid Xtream access paths, and already-tested `23.237.104.106` premium channel index relays are evidence only and must not count as new recoveries. This scan uses remaining new hosts and redirects to determine what actually deserves follow-up.

### Output

The branch's existing `Discover Fresh Media Origins (research only)` workflow reruns the same four A–D parallel jobs and saves distinct JSON artifacts per batch. Check the run summaries before promoting any lead. **Last confirmed public baseline remains 87/111** unless separately verified newer successful deployment artifacts say otherwise.
