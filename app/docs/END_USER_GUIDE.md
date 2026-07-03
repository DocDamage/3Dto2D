# SpriteForge Studio v12 End User Guide

## Normal workflow

1. Double-click `START_HERE.bat` in the main folder.
2. Open **Launchpad** and run the **No-GPU Demo**.
3. Open **Setup**, run the first-run diagnostic, install the safe WAN setup, and launch ComfyUI.
4. Open **Generate Sprite**.
5. Describe the character, choose an action/direction, and use the `debug` or recommended profile first.
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

## Reference image mode

Reference-image WAN workflows are heavier than basic text-to-video. Use a remote/cloud ComfyUI server for best results.

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
