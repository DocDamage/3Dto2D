# SpriteForge Studio v12 End User Guide

## Normal workflow

1. Double-click `START_HERE.bat` in the main folder.
2. Open **Launchpad** and run the **No-GPU Demo**.
3. Open **Setup**, run the first-run diagnostic, install the safe WAN setup, and launch ComfyUI.
4. Open **Sprite Lab**.
5. Describe the character, choose one or more actions, choose one or more directions, or select **All** directions, and use the `debug` or recommended profile first.
6. Watch progress in **Task Center** or **Queue Monitor**.
7. Review the finished result in **Quality Lab**.
8. Build a shareable/exportable package in **Release**.

Each finished sprite folder usually contains:

- `sheet.png` — the sprite sheet
- `sheet.json` — metadata
- `preview.gif` — animated preview
- `report.html` — visual report/contact sheet
- `frames_processed/` — individual frame PNGs

## Best first test

Use this first:

- Profile: `debug`
- Action: `idle`
- Direction: `front`
- Character: `single full body original game hero, simple outfit, boots, clean silhouette`

After that works, use:

- Profile: `rtx3060_12gb`
- Action: `walk`
- Direction: `right`

## Best sprite prompting rules

Good:

```text
single full body character, side view, locked camera, no zoom, centered, plain bright green background, clean silhouette
```

Bad:

```text
cinematic shot, camera orbit, close-up, complex background, motion blur, scene cut, dramatic zoom
```

Use the **Final prompt preview** before generating. The **AI Auto Fix** button calls SpriteForge's prompt fixer and adds sprite-safe cues such as locked camera, clean silhouette, transparent/chroma background language, and negative prompt cleanup.

## Sprite Lab generation controls

- **Actions** can include more than one animation in a single request, such as `idle`, `walk`, `slash`, and `cast`.
- **Directions** can include individual directions or **All**, which expands to the full directional set.
- **T-pose** and **A-pose** are available for reference/pose generation workflows.
- **Start ComfyUI if needed** should stay enabled for normal local generation. ComfyUI may still take time to load Python, custom nodes, models, and GPU memory before it can accept work.
- Generated previews and recent outputs persist when changing tabs; use **History** for previous experiment records and **Task Center/Logs** for job logs.

## Reference image mode

Reference-image WAN workflows are heavier than basic text-to-video. Use a remote/cloud ComfyUI server for best results.

## LPC character workflow

Use the dedicated **LPC** tab when you want a paper-doll character builder like the Universal LPC generator:

1. Click **LPC**.
2. Click **Load Pickers** if the part dropdowns have not loaded yet.
3. Choose body, hair, clothing, weapons, and accessories from the left/right panels.
4. Click **Compose** to build a single LPC spritesheet.
5. Zoom the center preview with the mouse wheel, zoom buttons, or slider.
6. Click **Build Batch** to create a composed LPC training dataset, then **Run QA**, then **Prepare LoRA**.

Use **Training Lab -> LPC** for advanced catalog scans, LPC parts datasets, direct composer inputs, and LoRA handoff controls.

## Cloud provider keys

Open **Setup** or **Cloud Hub** to add local API keys for Hugging Face, OpenAI, Google/Gemini, Anthropic, Moonshot/Kimi, GLM, DeepSeek, and Grok/xAI. Keys are stored locally in the app environment file. Free/community image generation depends on the provider, region, account, model, and current quota.

## Pixel Studio workflow

Use **Pixel Studio** for MagicPixel-style asset creation:

1. Open **Pixel Studio**.
2. Choose an asset type such as character, creature, item, weapon, potion, UI icon, tileset, or background.
3. Enter a prompt, optional reference image, resolution, palette size, provider, and style profile.
4. Generate assets in mock mode for fast local previews or use a configured provider for real image generation.
5. Use the gallery and inspector to normalize, edit, inpaint, animate, export, or reuse outputs.

Common Pixel Studio workflows:

- **Generate** creates individual pixel assets and writes metadata sidecars.
- **Normalize** enforces fixed pixel canvas, palette, alpha, outline, and cleanup rules.
- **Directions** builds 1, 4, or 8-direction character sheets and consistency scores.
- **Tileset** creates top-down, side-scroller, or isometric tile roles with seam checks.
- **Edit** saves an in-browser pixel edit as a new asset version.
- **Inpaint** applies a masked edit workflow while preserving pixel metadata.
- **Animate** generates a spritesheet and GIF preview from a selected asset.
- **Animation Transfer** applies an existing sheet layout to a new prompt/style.
- **Skeleton & Rigging** renders simple keyframed rig motion into a sheet.
- **Use as style reference** extracts palette and style hints from a selected asset so future assets can match it.
- **Cohesive Pack Builder** generates built-in or user-saved recipe packs and exports a ZIP with assets, sidecars, manifest, and `catalog.html`.
- **Recipe controls** let you preview the pack queue, save the current settings as a local recipe, and export recipe JSON for reuse.

Pixel Studio files are saved under:

```text
app/output/pixel_assets/assets/
app/output/pixel_assets/batches/
app/output/pixel_assets/packs/
app/output/pixel_assets/recipes/
app/output/pixel_assets/styles/
```

## Existing video conversion

Use the **Convert Video** tab if you already have a WAN/ComfyUI `.mp4`, `.webm`, or `.mov`.

For easiest background removal, make the generated video use a solid green or blue background.

Advanced CLI polish options:

```text
python spriteforge.py video --input input/clip.mp4 --output output/clip_sprite --matting-engine birefnet --alpha-refine --interpolate-fps 24
```

- `--matting-engine birefnet` uses the optional BiRefNet-matting checkpoint when `torch`, `torchvision`, and `transformers` are installed.
- `--matting-engine pixel-art` uses native hard-edge border-connected background removal for flat or dithered pixel-art backgrounds.
- `--temporal-alpha-stabilize` applies native motion-aware alpha smoothing to reduce frame-to-frame mask flicker.
- `--pixel-cleanup --pixel-cleanup-colors 24` learns one native Oklab palette across the animation and snaps frames to it for steadier AI pixel art.
- `--pixel-cleanup-palette pico8` or `--pixel-cleanup-palette gameboy` snaps cleanup to a native retro palette; custom hex lists also work.
- `--pixel-cleanup-dither-mode bayer` adds ordered dithering, while `floyd-steinberg` keeps the existing error-diffusion style.
- `--interpolate-fps 24` adds native interpolation; use `--interpolation-engine flow` for OpenCV optical-flow interpolation or `blend` for the simpler fallback.
- `--interpolation-skip-pixel-art` and `--interpolation-skip-impact-frames` hold crisp frames instead of blending transitions that would ghost.
- `--generate-normal-maps --normal-map-engine native-depth` creates native pseudo-depth normal, specular, AO, and height/parallax maps without an external depth tool.
- `python spriteforge.py dual-alpha --black black.png --white white.png --output transparent.png` extracts clean alpha from matching black/white Blender renders.
- `blender -b --python app/blender_render_ortho.py -- --blend input/character.blend --output output/frames --dual-background-alpha` renders black/white passes and writes transparent PNG frames directly.

## Fixing bad outputs

Use **Quality Lab**:

- **Run QA** finds jitter, loop seams, duplicates, flicker, and edge problems.
- **Auto-Fix** attempts anchor stabilization, loop duplicate removal, and edge cleanup.
- Engine export actions create Godot, Unity, Unreal, Aseprite, APNG, WebP, and release helper files where supported.

## Updating safely

Use the safe update and diagnostic actions in **Setup**. Snapshot before updating ComfyUI/custom nodes.

If something breaks, collect a support bundle with `COLLECT_SUPPORT_BUNDLE.bat` and use the maintenance/recovery actions in Setup.

## Release and project bundles

Use **Release** for clean release ZIPs and **Projects** for portable `.spriteforge` bundles. Bundles intentionally exclude local uploads, logs, generated release folders, vendor payloads, and model weights.

Do not ship workspace-local archives such as an old `dist_release.zip` unless it was rebuilt after cleanup.
