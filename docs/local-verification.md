# Local testing and explicit manual exceptions

Local Test and local verification serve different purposes. The Local Test catalog
offers eligible runner-blocked candidates for testing in Stremio; its presence is
not a normal QA pass, content-identity confirmation or production promotion.

Existing manual records explicitly marked `local_verified_override: true` can
retain user-verified playback when CI cannot validate access. Currently there are
19 such records, including 17 TVNow records. A family name, playlist label or
copied boolean cannot grant this exception. The manual-file loader binds approval
to the exact `tvg_id`, URL, family and headers. Changing any of those fields requires
an explicit manual-record review and new local verification. Do not apply the flag
to whole providers, discovered playlists or all failing candidates.

Every candidate still passes global safety, exact identity, URL/channel kill
switches and playback quarantine before probing. Detected repeated clips, frozen
playback, stalled live windows and identical media samples cannot use an override.
Timeouts or HTTP failures alone do not establish geographical blocking.

An accepted exception records `local_verified_override:true`, `passed:false` and
`publication_accepted:true` inside Primary QA. The failed CI status, detail,
continuity failure, decoder classification and complete decoder attempts remain
under `ci_*` fields. `status:ok` on an accepted publication decision does not mean
normal FFmpeg success. The existing release auditor excludes these records from
normal decoder-qualified coverage. Older artifacts may have `passed:true` on
overrides; always inspect the override field when analyzing historical evidence.

Use `diagnostics/channel-readiness.json` for all curated identities and their
Primary, backups and candidates. `tvnow-qa.json` joins channel and exact URL.
`primary-playback-qa.json` contains raw final validation evidence. Untested
backups are reported as such; distinct hosts do not establish independent origins.
Historical last decoder checks are separate from current successful validation.
Missing timestamps and unestablished provenance remain empty rather than guessed.

To remove a problematic source, add its exact URL to
`safety_controls.disabled_urls`, or its channel ID to `disabled_channels` in
`config.json`. The next successful build removes it. Keep the deployment guard
enabled: an override does not waive the 86-channel floor or critical identities.
If the protected build fails, the previous Pages deployment remains available.

Record fresh local channel results with `python record_client_result.py --help`.
That channel-level diagnostic is separate from manual source approval; it does
not automatically add source flags or promote an untested URL.
