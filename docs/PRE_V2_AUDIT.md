# Pre-v2 engineering audit (in progress)

This branch deliberately does not change channel selections, manifest ID, playback logic, or deployment.

## Verified
- The production builder is assembled from `build_parts/part01.txt` through `part07.txt`.
- The Pages workflow runs every two hours, assembles, tests, builds, checks the deployment guard, then deploys.
- `deployment_guard.py` enforces an 86-channel floor, HGTV identity, and status/diagnostics count agreement.
- The current workflow has no explicit main-build timeout and no separate PR test workflow.
- The existing guard does not compare the output with the last successfully deployed count.
- The existing dependency constraint `Pillow>=10.0` is not an exact pin.
- The existing `assemble_build.py` does not reject an empty parts directory.

## Deferred until safe validation
- Extract the 362 KB assembled builder into stable modules without changing output.
- Compare generated artifacts to a known-good fixture before replacing the production build command.
- Implement historical 30% drop detection and automatic issue notification with a verified baseline.
- Review official-source-only provenance and rights as the final pre-v2.0 gate, without deleting channels.

## Preserved compatibility
- Manifest ID: `com.stremiotv.philly`.
- Existing GitHub Pages URL, channels, source ranking, and deployment guard remain unchanged.
- No production changes occur until this branch is reviewed and merged.
