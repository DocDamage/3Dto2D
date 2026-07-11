# SpriteForge Studio v12 - Final Polish Edition

v12 is the production/pass-off version. Earlier versions proved the WAN → sprite pipeline; v12 focuses on making the app feel complete for a real end user.

## What the current v12 experience adds

- **Console-style Home**: an immediate **Start creating** action, a real bundled
  demo, recent-work continuation, and clear next-step language.
- **Guided Create flow**: a four-step character wizard with friendly defaults,
  simple first moves, an advanced escape hatch, and goal-aware ready checks for
  creation, video conversion, and release preparation.
- **Playful but accessible navigation**: original color-coded menu modes,
  keyboard and optional controller navigation, reduced-motion support, light
  and dark theme contrast, and reliable focus behavior for dialogs and drawers.
- **Friendly Review and Export**: plain-language quality actions, playtesting,
  and engine-oriented packaging choices.
- **Local Forge companion**: project-aware local retrieval that explains the
  next step and suggests safe navigation only.

- **Guided Home flow**: one clear path from demo → setup → creation → review → export.
- **Recommended next action**: the dashboard reads your setup and tells you the next thing to do.
- **Final preflight report**: one HTML/JSON report covering Python, Git, GPU, disk, ComfyUI, model tiers, and recent sprites.
- **Asset dashboard export**: a standalone visual gallery of finished sprite outputs.
- **Release builder**: packages selected sprite outputs into a clean release folder/ZIP with sheets, metadata, previews, reports, import notes, manifest, and preflight report.
- **Persistent production queue**: creates resumable action/direction generation queues for full character sets.
- **Better UI flow**: Home, Task Center, Review, and Export surfaces keep the
  main journey readable while professional controls remain available.
- **Sprite Lab generation controls**: multi-action generation, **All** directions, T-pose/A-pose options, persistent previews, and final prompt **AI Auto Fix**.
- **ComfyUI quality-of-life**: generation can request local ComfyUI startup automatically when needed.
- **Cloud provider key panel**: local key management for Hugging Face, OpenAI, Google/Gemini, Anthropic, Moonshot/Kimi, GLM, DeepSeek, and Grok/xAI provider slots.
- **LPC builder and training flow**: a dedicated LPC tab with zoomable paper-doll preview, plus Training Lab controls for cataloging LPC parts, composing batches, QA, and LoRA preparation.
- **Pixel Studio**: MagicPixel-style workflows for prompt/reference pixel assets, normalization, directions, tilesets, edit/inpaint, animation, animation transfer, skeleton rig rendering, and cohesive pack export.

## Best end-user path

1. `START_HERE.bat`
2. Open **Home** and choose **Try a demo** or **Start creating**.
3. Follow the wizard's ready check; configure optional AI generation in
   **Settings** only when needed.
4. Create a first character, then use **Review** to check motion and polish it.
5. Use **Export** to pack the reviewed character for the target game workflow.
6. Use **LPC** for paper-doll characters/training data or **Pixel Studio** for
   standalone pixel assets, tilesets, animation, and cohesive packs.

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
