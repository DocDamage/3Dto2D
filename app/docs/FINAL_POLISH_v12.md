# SpriteForge Studio v12 - Final Polish Edition

v12 is the production/pass-off version. Earlier versions proved the WAN → sprite pipeline; v12 focuses on making the app feel complete for a real end user.

## What v12 adds

- **Launchpad tab**: one guided path from demo → setup → generation → QA → release.
- **Recommended next action**: the dashboard reads your setup and tells you the next thing to do.
- **Final preflight report**: one HTML/JSON report covering Python, Git, GPU, disk, ComfyUI, model tiers, and recent sprites.
- **Asset dashboard export**: a standalone visual gallery of finished sprite outputs.
- **Release builder**: packages selected sprite outputs into a clean release folder/ZIP with sheets, metadata, previews, reports, import notes, manifest, and preflight report.
- **Persistent production queue**: creates resumable action/direction generation queues for full character sets.
- **Better UI flow**: Launchpad, Queue, and Release screens added to the polished browser UI.
- **Sprite Lab generation controls**: multi-action generation, **All** directions, T-pose/A-pose options, persistent previews, and final prompt **AI Auto Fix**.
- **ComfyUI quality-of-life**: generation can request local ComfyUI startup automatically when needed.
- **Cloud provider key panel**: local key management for Hugging Face, OpenAI, Google/Gemini, Anthropic, Moonshot/Kimi, GLM, DeepSeek, and Grok/xAI provider slots.
- **LPC builder and training flow**: a dedicated LPC tab with zoomable paper-doll preview, plus Training Lab controls for cataloging LPC parts, composing batches, QA, and LoRA preparation.
- **Pixel Studio**: MagicPixel-style workflows for prompt/reference pixel assets, normalization, directions, tilesets, edit/inpaint, animation, animation transfer, skeleton rig rendering, and cohesive pack export.

## Best end-user path

1. `START_HERE.bat`
2. Open **Launchpad**.
3. Run **No-GPU Demo**.
4. Run **Install Safe Setup**.
5. Launch ComfyUI.
6. Make a debug sprite in **Sprite Lab** with prompt **AI Auto Fix**.
7. QA/Auto-Fix the result.
8. Use **LPC** if you need paper-doll characters or LPC training data.
9. Use **Pixel Studio** if you need standalone pixel assets, tilesets, animations, or a cohesive starter pack.
10. Build a release ZIP.

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

## Source distribution contents

Source releases include SpriteForge code, examples, docs, launch scripts, and configuration templates. They do not include local runtime payloads or user-generated artifacts:

```text
app/vendor/
app/input/uploaded_videos/
app/output/
app/releases/
app/logs/
*.safetensors
```

Use `LICENSE` for the SpriteForge MIT license, `THIRD_PARTY_NOTICES.md` for external payload notes, and `requirements-lock.txt` when you need to reproduce the currently tested Python dependency set.

## Model recommendation remains unchanged

Use **Wan 2.1 T2V 1.3B** as the safe local default on RTX 3060 12GB. Add **Wan 2.2 TI2V 5B** only after the safe path works. Treat 14B-class models as cloud/heavy-GPU work.
