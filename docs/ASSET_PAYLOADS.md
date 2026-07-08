# Asset Payload Policy

SpriteForge keeps source code, small fixtures, manifests, and documentation in Git. Large local corpora, generated datasets, trainer installs, and model/checkpoint payloads stay outside repository tracking.

## Optional local payloads

- `CuteSCKR_uncut/`: optional root-level tile corpus for tile LoRA dataset preparation. Keep it local and ignored unless there is an explicit product decision to publish it elsewhere.
- `app/input/lpc_assets/Universal-LPC-Spritesheet-Character-Generator/`: optional Universal LPC source tree used by the LPC composer and dataset tools.
- `app/vendor/`: local external tools, trainers, model helpers, and downloaded dependencies.
- `output/`, `app/output/`, and `dist_release.zip`: generated outputs and release archives.

## Sharing large assets

Do not add large corpora directly to Git. If a payload must be shared across machines, publish it as an external artifact with license notes and checksums, or adopt Git LFS after an explicit repo-level decision. Checked-in config should use portable relative paths such as `CuteSCKR_uncut` or `input/lpc_assets/Universal-LPC-Spritesheet-Character-Generator`.

## Guardrails

The repository tests assert that ignored local payload folders remain untracked and that tracked text files do not contain user-machine absolute paths.
