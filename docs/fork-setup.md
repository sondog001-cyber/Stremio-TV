# Fork setup and troubleshooting

## Requirements and local setup

Use Python 3.12 and Pillow (`requirements.txt`). A full online build also needs
FFmpeg on PATH. GitHub Actions installs these automatically. The optional pinned
build-time resolver requires Node 20 and npm; its failure must not grant a QA pass.

Clone your fork, then run from the repository root:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python assemble_build.py
python -m unittest discover -s tests -v
```

`build.py` is generated and gitignored. Edit `build_parts/part*.txt`, then assemble
again; changes to the generated file alone are not retained. The test suite uses
synthetic data/mocked media and does not certify live channel availability.

For a local online build, install FFmpeg separately and set the public URL for the
site you intend to serve:

```bash
PUBLIC_BASE_URL=https://YOUR-USER.github.io/YOUR-REPO python build.py
python -m http.server 8080 --directory site
```

On PowerShell set `$env:PUBLIC_BASE_URL` before running Python. The local HTTP
server previews the output; install an HTTPS deployment for normal Stremio use.
Do not set `PUBLIC_BASE_URL` to the original author's site for your fork.

## GitHub Pages

Enable Actions on the fork and choose **Settings → Pages → GitHub Actions**.
GitHub normally disables scheduled workflows in new forks until Actions is
enabled; inspect your fork's Actions tab. Dispatch **Build and deploy Stremio TV**.
Its build and deploy jobs must both succeed before installation is considered done.

The builder derives asset/manifest URLs from the fork's `GITHUB_REPOSITORY`.
Project sites use `https://OWNER.github.io/REPO`; an `OWNER.github.io` repository
uses the root URL. `PUBLIC_BASE_URL` overrides this for a custom deployment.
Install `https://YOUR-USER.github.io/YOUR-REPO/manifest.json` in Stremio.
If you need both addons installed independently, choose a unique `addon.id` in
your fork's config and retain stable curated channel IDs. Existing production
addon IDs must stay stable during normal upgrades.

No owner-only secret is required for public builds. `GITHUB_TOKEN` is the built-in
Actions token; it is not a secret to copy from the original owner. Pages uses the
workflow's Pages/OIDC permissions. Public upstream services can fail or restrict
access from a runner. The unchanged 86-channel/critical-identity guard may block a
first deployment during an outage. Read diagnostics and fix qualified coverage;
do not lower thresholds to make a release appear ready. A first fork has no prior
deployment to retain; a failed guard means there is no addon site yet.

Never add private account material to public config, manual sources or Actions
artifacts. Private connector overlays are blocked in public Actions builds; see
the README for local private deployment instructions.

## Sources, validation and diagnosis

The original curated roster has 111 identities. `config.json` controls curation,
source ranking, health, Local Test and emergency removal; `manual_sources.json`
stores explicitly reviewed public upstreams; `aliases.json` handles exact EPG
mapping. A matching playlist label is insufficient evidence of full US East or
Philadelphia affiliate programming. Keep attribution and verify actual media.

Full validation includes HLS/segment probes, continuity/burn-in, configured
stability/cooldowns, FFmpeg decode and repeated-clip checks, final Primary QA and
backup promotion. See [local verification](local-verification.md) for the narrow
exception path. Kill switches are exact URLs/channels under `safety_controls`.

Inspect the exact run's **stremio-tv-diagnostics** artifact, even when a guard
blocks deployment. Compare `status.json`/`build-info.json` with the run SHA before
using its reports. `channel-readiness.json` joins the complete roster and source
evidence. `missing-source-diagnostics.json`, `primary-playback-qa.json`,
`tvnow-qa.json` and `stream-stability.json` distinguish missing URLs, access
failures, decoder failures, local exceptions and cooldown. Test suspected runner
access problems from Stremio using the separate Local Test catalog. Never infer
actual playback success from a green research job or HTTP 200 alone.

## Workflow inventory and rollback

| Workflow | Role | Automatic trigger |
|---|---|---|
| Build and deploy Stremio TV | Protected production build and Pages deployment | Main code changes; `7 */2 * * *` |
| Validate Stremio TV PR | Unit tests and real catalog/logo audit | Relevant pull requests |
| Audit v0.9.0 release evidence | Read-only three-schedule audit (PR #116) | After production completion once merged |
| Update combined IPTV playlist | Separate playlist maintenance | `17 */6 * * *` |
| Discover Fresh Media Origins | Isolated discovery; cannot deploy | Relevant PR/manual |
| Established Probe Retry Network Test | Historical branch experiment | Pinned research branch only |
| QA Resilience Network Test | Historical branch experiment | Pinned research branch only |
| WTXF logo preview | Visual research utility | See its manual/branch triggers |

The historical research workflows/scripts remain useful for reproducing evidence;
they have not been deleted. The discovery workflow's hardcoded historical baseline
run may be unavailable in a fork: its download is optional, and missing baseline
evidence is not recovery proof. Review that input before new discovery work.
No production schedule or concurrency change is required for fork setup.

Keep the `pages` concurrency group and `cancel-in-progress:false`. Use isolated
branches/PRs, wait for all checks and preserve a known-good commit. If an update
regresses, revert the responsible commit through a validated PR and rebuild.
The deployment guard protects the last deployed site when a new build fails.
Reverting code cannot restore an upstream service that has independently failed.
