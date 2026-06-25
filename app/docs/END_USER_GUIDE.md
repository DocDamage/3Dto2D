# SpriteForge Studio v7 End User Guide

## Normal workflow

1. Double-click `START_HERE.bat` in the main folder.
2. Click **Set Up Everything**.
3. Click **Run Health Check**.
4. Go to **Make Sprite**.
5. Describe the character, choose an action, then click **Generate Sprite**.
6. Click **Open Outputs**.

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

Use **QA / Export**:

- **Run QA** finds jitter, loop seams, duplicates, flicker, and edge problems.
- **Auto-Fix** attempts anchor stabilization, loop duplicate removal, and edge cleanup.
- **Export Godot** and **Export Unity** create engine helper files.

## Updating safely

Use **Safe Update** inside Easy Mode. It creates a snapshot before updating ComfyUI/custom nodes.

If something breaks, use **Snapshot / Rollback** from the advanced tools or the maintenance tab.
