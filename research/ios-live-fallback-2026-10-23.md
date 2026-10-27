# Built-in live playback fallback

Observed on sideloaded iOS Stremio 2.0.8 b23 / core 0.6.5: scheduled
programmes appear as ordinary episodes, including Upcoming labels, and the
selected programme has no playback options. Production serves the NFL Network
channel stream resource (HTTP 200) but not its EPG programme ID (HTTP 404).
We do not have a device request trace, so the exact client failure is unproven.

## Change

- Channel catalog previews and metadata advertise `defaultVideoId` equal to
  the existing channel ID, never a programme ID.
- Channel detail metadata includes an explicit, untimed `Watch live` video
  using that same ID. Its historical `released` value avoids an Upcoming gate;
  it describes live playback, not an actual historical broadcast.
- Following a failed device test of the untimed entry, the live video explicitly
  declares `season: 0` and `episode: 0` for clients requiring series coordinates.
  This single fallback retains the channel ID and existing live stream resource;
  the timed guide programmes keep their original metadata.
- Date-filtered EPG catalogs retain only their original timed programmes.
  Detail metadata retains the timed programmes and native scheduling hint.
- No inline video streams, programme-ID aliases, catch-up claims, alternate
  addon, new upstream requests, or source-selection changes are introduced.

This is a persistent compatibility path, not automatic detection of a failed
player: static GitHub Pages cannot inspect a client version or playback result.
Native guide clients continue using the channel stream resource. Legacy clients
can route directly to that resource or select Watch live in channel details.

## Validation and limitations

Focused tests cover channel/default-video identity, explicit available live
entry, unchanged future/timed programmes and date-filtered guide behavior,
input immutability, and channels without EPG or artwork. Existing native EPG
generated-output tests remain applicable. Normal PR validation must pass the
real-build logo audit and protected-channel deployment guard before merge.

The fallback does not fix incompatible codecs, upstream outages, or any mobile
transport/header restriction. Device compatibility remains unconfirmed until
tested in the reported iOS build. Restart/refresh the existing addon after the
new build publishes; reinstalling the app is not part of this change.

Protocol references:
- https://github.com/Stremio/stremio-addon-sdk/blob/master/docs/epg.md
- https://github.com/Stremio/stremio-addon-sdk/blob/master/docs/api/responses/meta.md
- https://github.com/Stremio/stremio-core/blob/master/src/deep_links/mod.rs

The core master implementation is supporting design evidence, not proof of
the exact behavior of the installed core 0.6.5 binary.
