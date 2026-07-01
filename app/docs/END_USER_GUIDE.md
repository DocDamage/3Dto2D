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
