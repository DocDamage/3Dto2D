# SpriteForge Studio v9 — Visual Edition

This edition keeps the v8 fail-safe backend and adds a polished local browser UI.

## Start

Double-click `START_HERE.bat`.

A browser window opens to the SpriteForge Studio dashboard. Keep the console window open while using the app.

## What changed in v9

- New glass/aurora visual dashboard.
- Better onboarding through visual setup cards.
- Output gallery with animated previews.
- Drag-and-drop video upload for WAN/ComfyUI videos.
- Live command console with cancel button.
- Visual status chips for GPU, ComfyUI, models, disk, and outputs.
- One-screen WAN to sprite form.
- Quality Lab for QA, auto-fix, Godot export, and Unity export.
- Production Pack and Atlas screens.
- Classic Tkinter mode is still included as fallback.

## First-use order

1. Start the app with `START_HERE.bat`.
2. In the Setup tab, run **Install SpriteForge deps**.
3. Run **Install ComfyUI + WAN**.
4. Run **Download WAN models**.
5. Click **Launch ComfyUI**.
6. Run **Doctor**.
7. Use **Make Sprite** with profile `debug` first.
8. After that works, switch to `rtx3060_12gb`.

## Fallbacks

If the new browser UI fails, run `START_CLASSIC_MODE.bat`.

If setup needs to be repeated, run `START_FIRST_RUN_WIZARD.bat`.

The UI is a local app served from your own machine at `127.0.0.1`. It does not require Electron, Node, React, or internet access just to open. Internet is only needed for installing/updating ComfyUI and downloading model files.
