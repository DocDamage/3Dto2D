# SpriteForge Studio v12 — Final Polish Edition

v12 is the production/pass-off version. Earlier versions proved the WAN → sprite pipeline; v12 focuses on making the app feel complete for a real end user.

## What v12 adds

- **Launchpad tab**: one guided path from demo → setup → generation → QA → release.
- **Recommended next action**: the dashboard reads your setup and tells you the next thing to do.
- **Final preflight report**: one HTML/JSON report covering Python, Git, GPU, disk, ComfyUI, model tiers, and recent sprites.
- **Asset dashboard export**: a standalone visual gallery of finished sprite outputs.
- **Release builder**: packages selected sprite outputs into a clean release folder/ZIP with sheets, metadata, previews, reports, import notes, manifest, and preflight report.
- **Persistent production queue**: creates resumable action/direction generation queues for full character sets.
- **Better UI flow**: Launchpad, Queue, and Release screens added to the polished browser UI.

## Best end-user path

1. `START_HERE.bat`
2. Open **Launchpad**.
3. Run **No-GPU Demo**.
4. Run **Install Safe Setup**.
5. Launch ComfyUI.
6. Make a debug sprite.
7. QA/Auto-Fix the result.
8. Build a release ZIP.

## Useful CLI commands

```bat
python spriteforge_unified.py next-step
python spriteforge_unified.py preflight
python spriteforge_unified.py asset-dashboard
python spriteforge_unified.py release-package --sprite-dir output\hero_walk_sprite --zip
python spriteforge_unified.py queue-create --name hero --actions idle,walk,run,attack_light,hurt --directions right
python spriteforge_unified.py queue-run --queue output\jobs\YOUR_QUEUE.json
```

## Release package contents

```text
releases/<name>_<timestamp>/
  README.md
  manifest.json
  sprites/
    <sprite output folders>/
  engine/
    *_import_notes.md
  preflight/
    preflight.json
    preflight.html
```

## Model recommendation remains unchanged

Use **Wan 2.1 T2V 1.3B** as the safe local default on RTX 3060 12GB. Add **Wan 2.2 TI2V 5B** only after the safe path works. Treat 14B-class models as cloud/heavy-GPU work.
