# Five-channel Philadelphia OTA — private direct-tuner prototype

**Status: code implemented and offline tests provided; requires actual local HDHomeRun hardware for reception/codec/Stremio validation.** This branch is **not** production, and no local channel has been claimed playable or counted as recovered.

## Why an independent local setup

SiliconDust's [HTTP API](https://www.silicondust.com/hdhomerun/hdhomerun_http_development.pdf) supplies `http://<tuner-LAN-IP>/lineup.json` and, for tuner models supporting HTTP, direct MPEG-TS URLs such as `http://<tuner-LAN-IP>:5004/auto/v6.1`. The Stremio addon can **return this direct URL**; this project must never become a restreamer. OTA channels are only available to an antenna and tuner at the user's actual location. Hardware tuner occupancy, reception, codec compatibility, and Stremio/client network reachability are unverified until tested on location.

This prototype supplements the existing `private_connectors.py`/local-overlay loading path without touching any public source lists. The public GitHub Actions build already **rejects** a private overlay. The OTA script also refuses to run in GitHub Actions, validates numeric RFC1918 tuner IPs and refuses URL redirects, rejects any different stream hostname, credentials, non-direct path/port, DRM-tagged lineup record, and unresolved or ambiguous lineup mapping. No cloud endpoints are contacted by the OTA discovery script.

## Five provisional exact targets

| Curated ID | Station identity | **Suggested** guide number (verify on local scan) |
| --- | --- | --- |
| `KYW.us` | KYW-TV full linear CBS Philadelphia | `3.1` |
| `WCAU.us` | WCAU-TV full linear NBC 10 | `10.1` |
| `WPVI.us` | WPVI-TV full linear 6abc (low-VHF reception can be challenging) | `6.1` |
| `WPHL.us` | WPHL-TV full linear PHL17 | `17.1` |
| `WPSG.us` | WPSG-TV full linear Philly57 | `57.1` |

The mapper **does not assume** any of these is present. It matches the *actual* scanned `GuideNumber` **and** a known exact `GuideName` for that identity. It will refuse mislabeled news FAST feeds and unrecognized/ambiguous guide names. If your tuner shows a different name or slot, you edit your **gitignored local mapping**, not the public repo.

## Windows PowerShell instructions

Hardware prerequisite: a connected OTA antenna and an HDHomeRun that supports direct HTTP MPEG-TS, on the **same home LAN as the PC/Stremio client**. No antenna/tuner is assumed to be owned already.

1. Clone/checkout the prototype branch, then create a **private, gitignored** mapping copy:

   ```powershell
   Copy-Item private_ota.example.json private_ota.json
   $env:STREMIO_TV_HDHR_BASE_URL = "http://192.168.1.50"  # REPLACE with your tuner's real LAN IPv4
   ```

2. Ensure you have performed the tuner's antenna channel scan. You can inspect `http://192.168.1.50/lineup.json` from the same computer (replace address). Do not post actual device responses with LAN addresses publicly. First run a safe **mapping-only dry run**:

   ```powershell
   python private_ota.py
   ```

   The console shows `mapped` and per-ID status such as `mapped`, `not_found`, `ambiguous`, `drm_protected`, and `invalid_or_external_stream_url`, but never prints LAN playback URLs. If `not_found`, inspect the tuner scan and adjust `guide_numbers` and `guide_names` in **private_ota.json** to the actually observed identity.

3. Only when you approve the mapping, explicitly generate the local private overlay:

   ```powershell
   python private_ota.py --write-overlay
   python -m pip install -r requirements.txt
   python assemble_build.py
   $env:STREMIO_TV_PRIVATE_SOURCES_FILE = "private_sources.generated.json"
   python build.py --output private-site
   ```

   The generated overlay (`private_sources.generated.json`) is gitignored and receives owner-only filesystem permission when supported. Never set `PUBLIC_BASE_URL` to a publicly accessible location for this build. This is a private full build, which runs the existing health/decoder QA using that PC's network. Its public channel portions may need external network availability; the private OTA portion can only pass if the tuner and actual signal are working.

4. For **Stremio Desktop on the same PC**, launch the private static addon's HTTP server, which binds to loopback only by default and returns channel metadata/direct device URLs (no streaming):

   ```powershell
   python serve_private_ota.py
   ```

   Install `http://127.0.0.1:8765/manifest.json` as a **separate private addon** in Stremio Desktop. This is not an update to the public GitHub Pages manifest. Keep the Python server running while using the local addon; keep the tuner on the LAN. Some Stremio clients may reject HTTP/local-network addon URLs or MPEG-TS playback: these are **client tests**, not certified features.

5. For another Stremio device **only on the same LAN**, explicitly bind to your PC's RFC1918 address, e.g. `python serve_private_ota.py --host 192.168.1.20 --allow-lan`. You must ensure your firewall allows only trusted local devices. The TV device must reach both the PC's manifest server and the tuner itself. Do **not** use port forwarding, reverse proxy, tunneling, public DNS, GitHub Pages or internet hosting. The server blocks build diagnostics and sets a narrow set of Stremio CORS origins. Stremio Web over HTTPS may block mixed-content HTTP/local-LAN streams; desktop is the recommended first test.

## Offline validation (no hardware required)

```powershell
python -m unittest tests.test_private_ota -v
```

The tests use mocked lineup data (all five matches, wrong station on correct number, wrong number, duplicate names, off-tuner URLs, credentials, cloud hosts, DRM and CI protection). A green workflow means the **adapter is logically tested**; it does **not** mean five OTA broadcasts were physically received or decoded.

## Preserved project rules

- Original antenna reception, no DRM bypass, no account scraping or new premium-TV rights.
- **Direct device → Stremio client** streaming, not video restreaming or tunnel.
- Separate local addon/overlay; no private URL ever added to `config.json`, `manual_sources.json`, `combined.m3u`, research artifacts or published GitHub Pages.
- The five missing channels remain **missing in the public 87/111 baseline**. A local/private recovery is counted separately only after user reception, original station identity, FFmpeg decoding and Stremio playback verification.
- Original public v0.8.0 QA and per-channel/URL kill switches remain untouched.

## Hardware-dependent acceptance checklist

1. Tuner `lineup.json` returns the intended affiliate for the exact virtual number/name.
2. FFmpeg on the **user's LAN** decodes 60+ seconds of each selected direct `/auto/v...` stream with no repeating clips, stalls or unexpected codec restrictions.
3. Local Stremio install shows native station identity and direct client playback works over the actual TV device network.
4. No private address appears in public site artifacts, GitHub commits, workflow logs, browser-hosted public endpoint or deployed manifest.
5. If a station is absent/poor reception, classify as **OTA reception unavailable** rather than a software QA pass or project source recovery.
