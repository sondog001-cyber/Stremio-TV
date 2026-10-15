# New public-directory discovery — 2026-10-15

Inspected current primary source code in
[stremio-tv-scrapers-live-tv](https://github.com/gauravsuman007/stremio-tv-scrapers-live-tv):
`SOURCES.md`, `scrapers/jestone.mts`, `scrapers/vipotv.mts`, `scrapers/ntvst.mts`.
The public jest.one news-directory and VipOTV WordPress/FirePlayer descriptors
are new discovery entry points for this project. Their presence does not prove
independent media origins; every resulting CDN still needs provenance review.
No third-party scraper code is executed or copied into the production builder.
Excluded approaches requiring segment rewriting, DRM or a relay are not adopted.

Inspected ten target stream files in
[notr3kt/stremio-us-live-tv](https://github.com/notr3kt/stremio-us-live-tv) and
three in [ajo-live](https://github.com/imakshayjoshi/ajo-live). They mostly recycle
known IPTV-org hosts; unobserved URL variants on the same dead hosts are not fresh
origins. Ajo's WCAU link is the known NBC Philadelphia news stream already rejected
by the exact identity gate; it must not be counted as full WCAU programming.
Recent repository search also returned the previously examined dmandache index
and an empty repository; neither justifies repeat media probing.

This draft adds an isolated read-only research workflow. It reads the exact
recent runner baseline (run38737164051), searches all22 currently missing targets
plus4 intermittent targets, bounds directory resolutions to12 and applies the
existing project safety controls before retaining public media descriptors.
It does not probe media, manufacture credentials/tokens, proxy, restream, change
config, select streams, deploy, or certify identity. Name matches remain unverified
hints. Unsafe URLs are omitted from reports. All findings still require exact
programming/provenance and normal full playback/stability validation in a separate
staging change before any promotion. No recovered channel is claimed.

The runner performs the API reads because this session's public-web retrieval
could not access those three directory endpoints. Inaccessibility here is not
evidence that the runner or upstream media will fail. A missing baseline stops
the job rather than falsely calling old URLs new. The pinned baseline is dated
research evidence and must be refreshed for future work/forks.
