# 🌌 SpriteForge Studio

> **Forge Your 3D Motions and Video Clips into High-Fidelity 2D Game Assets. Instantly.**

SpriteForge Studio is the ultimate pipeline for converting short character animation videos, 3D renders, or AI-generated clips into production-ready 2D spritesheets and animation files. Combining state-of-the-art image processing, automated QA, normal map baking, and native game engine exporters, it bridges the gap between raw video and game engine integration in seconds.

![SpriteForge Demo Preview](app/examples/prebuilt_demo_sprite/preview.gif)

---

## 💡 Why You Need SpriteForge Studio

Creating quality 2D game animations is notoriously tedious. Hand-drawing character directions takes weeks, generating consistent assets with AI video is full of flickering, and baking normal maps for dynamic 2D lighting is nearly impossible to do manually.

**SpriteForge Studio solves this by automating the heavy lifting:**

*   **10x Faster Asset Creation:** Feed in an MP4, WEBM, or MOV video clip—whether it's a 3D character render, a motion capture output, or an AI generation—and extract a fully-packed, transparent spritesheet instantly.
*   **Dynamic 2D Lighting Out-of-the-Box:** Bake matching **Normal, Specular, AO, and Height maps** for your character animations, enabling gorgeous real-time lighting in modern game engines.
*   **Production-Grade Coherence:** Clean up outlines, harmonize palettes, stabilize temporal jittering, and upscale or downscale frames with smart LOD sampling.
*   **Zero-Configuration Engine Imports:** Export complete, plug-and-play `.tscn` scene nodes for **Godot 4.x**, import scripts for **Unity**, and Paper2D configuration notes for **Unreal Engine**.

---

## 🚀 Key Features

### 🎬 Real-Time In-Browser Animation Player
Never guess how your spritesheet will look in-game. Evaluate your outputs inside a high-performance, canvas-based animation previewer:
*   **Scrub & Step**: Easily step frame-by-frame or scrub the timeline to check alignment.
*   **Onion-Skinning**: Display preceding and succeeding frames as translucent overlays to guarantee fluid motion.
*   **Playbacks**: Adjust speed (0.25x to 4x), toggle looping, and preview against checkerboard grids or solid colors.

### ✂️ Interactive Timeline & Frame Editor
Clean up bad frames and retarget timings without opening a heavy editor:
*   **Drag-to-Reorder**: Rearrange frames directly on the visual filmstrip timeline.
*   **Hold & Delete**: Drop bad frames, duplicate frames, or set custom, frame-specific duration overrides.
*   **Interactive Repacking**: Re-align the grid on-the-fly and rebuild your spritesheet metadata with a single click.

### 💡 Normal Map & WebGL Dynamic Lighting Preview
Interactive 2D lighting, right in your browser. Drag a point light source around your character preview to see your normal maps, specular reflections, and ambient occlusion composite in real-time WebGL. Export lit previews as GIFs to share with your team.

### 🧠 AI-Powered QA & Repair Advisor
Our automated Quality Assurance suite runs statistical analysis across frame silhouettes:
*   **Loop Stability**: Measures loop RMSE to ensure seamless repeat animations.
*   **Artifact Detection**: Alerts you to outline bleed, silhouette gaps, or stray pixels.
*   **One-Click Auto-Fix**: The QA Advisor evaluates failures and builds custom repair plans (e.g. outline dilation, threshold snaps) that you can execute with one click.

### 🌀 Advanced Pipeline Power-Ups
*   **Temporal Coherence Pass**: Uses sliding-window temporal filters to eliminate color flicker and edge jitter.
*   **RIFE Frame Interpolation**: Smooth out low-framerate video clips into high-FPS animation assets.
*   **Depth-Anything Matting**: Leverages monocular depth mapping to extract perfect edge alpha around complex details.
*   **Multi-Resolution LOD Exports**: Automatically generates nested resolutions (e.g., 128px, 64px, 32px sheets) preserving crisp nearest-neighbor scale for pixel art.

---

## 🛠️ Seamless Game Engine Exporters

Every sprite folder you export comes packed with sidecar manifests and engine scaffolding:

*   **Godot 4.x**: Exports a ready-to-use `.tscn` scene. Pre-configured with crisp `nearest` texture filters, correct `hframes`/`vframes`, loop settings, and pivot metadata.
*   **Unity**: Includes companion C# script templates and imports mappings to load your sheets directly into Unity's Sprite Editor.
*   **Unreal Engine**: Auto-generates Paper2D import notes to map coordinates and flipbook frame rates.
*   **Runtime Formats**: Export animations as **APNG**, **Animated WebP**, or vector-based **Lottie JSON** with explicit format capability contracts.

---

## ⚡ Quick Start

### 1. Launch the Studio
On **Windows**, simply double-click the main launcher in the root directory:
```bat
START_HERE.bat
```
*(On macOS or Linux, run `./start.sh` from the terminal).*

The launcher automatically configures a local Python virtual environment, installs all required image-processing packages, and launches the beautiful glassmorphic Web Studio dashboard in your browser.

### 2. Verify Your Pipeline (No-GPU Demo)
To check the system capabilities without downloading heavy AI weights or requiring a CUDA GPU, double-click:
```bat
RUN_DEMO_NO_GPU.bat
```
This runs a CPU-safe demo processing pipeline generating a sample character spritesheet complete with sheet metadata, previews, normal maps, and export helpers.

### 3. Setup AI Generation (Optional)
If you want to use the text-to-video generation features:
1.  Navigate to the **Setup** view in the Web UI.
2.  Install or link your local/remote **ComfyUI** instance.
3.  Load the Wan model tiers (from Wan 2.1 1.3B up to heavier 5B or 14B models).
4.  Use **Sprite Lab** to choose one or more actions, one or more directions, or **All** directions.
5.  Leave **Start ComfyUI if needed** enabled when you want SpriteForge to start the local ComfyUI server automatically before generation.
6.  Review the **Final prompt preview** and use **AI Auto Fix** to add sprite-safe language before running.

### 4. Build LPC Characters and Training Data
SpriteForge now includes a dedicated **LPC** tab for Universal LPC paper-doll assets:

*   Load the bundled/local Universal LPC asset folder and choose body, hair, clothes, weapons, and accessories from LPC-style picker panels.
*   Preview the composed character in the center pane and zoom with the mouse wheel, zoom buttons, or slider.
*   Compose a single character sheet, build a balanced batch dataset, run dataset QA, and prepare an LPC LoRA run from the same tab.
*   Use **Training Lab -> LPC** when you need lower-level catalog scans, parts datasets, or batch controls.

The LPC source assets are local-only and are not bundled into release ZIPs or pushed as generated output.

### 5. Create Pixel Assets, Tiles, Animations, and Packs
Use **Pixel Studio** when you want MagicPixel-style game asset workflows directly inside SpriteForge:

*   Generate pixel-art characters, creatures, items, weapons, potions, UI icons, tilesets, and backgrounds from a prompt, reference image, style profile, and provider.
*   Use asset-specific controls for characters, creatures, items, weapons, potions, UI, tilesets, and backgrounds. These controls expand prompts through editable JSON configs in `app/config/pixel_asset_modes.json` and `app/config/pixel_prompt_templates.json`.
*   Normalize and clean outputs to game-ready pixel constraints: fixed canvas size, palette reduction, transparent background, nearest-neighbor scaling, version backups, and sidecar metadata.
*   Build 4-direction or 8-direction character sheets, tile atlases with seam QA, text-to-animation sheets, animation transfers from an existing sheet, and lightweight skeleton/rig renders.
*   Edit assets in-browser with pencil, eraser, fill, picker, line, rectangle, selection/move, PNG import/export, version saves, mock AI inpainting, fast reskin batches, and variant-first outfit/part application workflows.
*   Extract a style profile from any selected asset, then reuse that palette/style memory for matching future generations.
*   Use **Cohesive Pack Builder** to generate built-in or saved recipe packs such as RPG, dungeon crawler, platformer, potion shop, or UI HUD packs, then export the whole pack as a ZIP with a browsable HTML catalog.
*   Save current Pixel Studio settings as reusable local recipes, import recipe JSON, and export recipe JSON for sharing or backup.
*   Pixel Studio sidecars link into SpriteForge experiment memory, and project-scoped generations are also added to the active project Library.
*   The local CuteSCKR tile corpus can be prepared as an auto-tile LoRA dataset with trigger `cutesckr_tiles`; SpriteForge registers the resulting native adapter as the default `tile_style`.

Pixel Studio outputs are written under `app/output/pixel_assets/` with per-asset JSON metadata, batch manifests, style profiles, recipes, and pack manifests.

### 6. Cloud Image Providers and API Keys
Open **Setup** or **Cloud Hub** to inspect cloud image provider readiness and save local API keys. Supported provider slots include Hugging Face, OpenAI, Google/Gemini, Anthropic, Moonshot/Kimi, GLM, DeepSeek, and Grok/xAI. Free-tier availability depends on each provider and model account; SpriteForge reports provider capability but does not guarantee quota or pricing.

---

## 📂 Spritesheet Output Structure

A typical output package contains everything a game engine needs:

```text
my_sprite/
├── sheet.png                 # The assembled spritesheet grid
├── sheet.json                # SpriteForge engine-agnostic frame & pivot metadata
├── sheet.aseprite.json       # Aseprite-compatible frame tags and timing data
├── preview.gif               # Transparent preview loop
├── report.html               # Quality QA breakdown score
├── contact_sheet.jpg         # Visual grid overview
├── animated_exports/         # APNG, WebP, or Lottie runtime assets
│   ├── idle.apng.manifest.json
│   └── idle.png
├── godot_export/             # Plug-and-play Godot files
│   ├── sheet_player.gd
│   └── my_sprite.tscn
└── frames_processed/         # Individual cropped & processed frames (PNG)
```

---

## 🧪 Built to Last

SpriteForge Studio is built on a robust, service-oriented Python architecture backed by **over 420 automated unit and integration tests** verifying outline calculations, rate-limiting security guards, SQLite db indexing, and schema validation.

To run the test suite locally:
```bat
pytest
```
*Note: If running the entire suite on Windows triggers memory issues due to native DLL cleanups, run with garbage collection disabled:*
```bat
python -c "import gc; gc.disable(); import pytest; pytest.main()"
```
