# SpriteForge Studio

SpriteForge Studio is a local Python application for turning short character
animation videos into usable 2D sprite assets. It includes a browser dashboard,
CLI tools, batch scripts, QA reports, sprite-sheet packing, project management,
and engine export helpers.

It can also drive ComfyUI/WAN workflows for AI video generation, but that part is
optional and depends on your own local or remote ComfyUI setup, model downloads,
GPU memory, and workflow configuration. Model weights and ComfyUI are not
bundled in this repository.

The most reliable current path is:

1. Run the app locally.
2. Verify the no-GPU demo.
3. Convert or polish existing videos into sprite sheets.
4. Use ComfyUI/WAN generation only after the local processing pipeline works.

![SpriteForge demo preview](app/examples/prebuilt_demo_sprite/preview.gif)

## Current Status

This repository is best described as an actively developed local tool, not a
finished consumer product. The codebase has a broad automated test suite and many
working utility paths, but some advanced UI flows and AI generation workflows are
still sensitive to local environment differences.

What is currently solid:

- Local Flask/browser dashboard for the main workspace.
- CPU-friendly no-GPU demo sprite generation.
- Video-to-sprite processing with chroma keying, alpha cleanup, frame extraction,
  packing, previews, and metadata.
- Sprite QA reports, visual comparisons, frame status metadata, palette tools,
  and repair helpers.
- Project folders, references, release packaging, queue records, and history.
- Export helpers for formats such as Godot, Unity, Unreal/Paper2D notes,
  Aseprite JSON, XML atlases, APNG, and animated WebP.
- A tested plugin/service architecture for selected QA and export extensions.

What should be treated as optional or experimental:

- One-click WAN model installation on every machine.
- Local text-to-video generation on low-VRAM GPUs.
- Heavy reference-image and 14B-class model workflows.
- Optional research integrations such as SAM2, BiRefNet, MediaPipe-style pose
  extraction, LoRA training helpers, and advanced native/AI cleanup paths.
- Marketplace-style bundle discovery and some training-lab workflows.

## Requirements

Minimum for the local app and processing tools:

- Python 3.10 or newer.
- Git, if you want the setup scripts to install or update external tools.
- Enough disk space for generated outputs.
- Windows is the best-tested path. macOS/Linux launch scripts exist, but expect
  more manual setup.

Optional for AI generation:

- ComfyUI.
- WAN model checkpoints.
- A CUDA-capable NVIDIA GPU for practical local generation.
- Remote/cloud ComfyUI for heavier workflows.

The Python dependencies are listed in:

- [pyproject.toml](pyproject.toml)
- [app/requirements.txt](app/requirements.txt)
- [requirements-lock.txt](requirements-lock.txt)

## Quick Start

On Windows, from the repository root:

```bat
START_HERE.bat
```

On macOS or Linux:

```sh
./start.sh
```

The launcher creates `app/.venv`, installs the app requirements, and starts the
local browser UI. If the web UI fails, it attempts to fall back to the older
classic UI.

Once the dashboard opens:

1. Run the no-GPU demo first.
2. Open the generated demo output and confirm it includes `sheet.png`,
   `sheet.json`, `preview.gif`, and `report.html`.
3. Try converting an existing short `.mp4`, `.webm`, or `.mov` before spending
   time on WAN generation.
4. Only after that, use Setup to install or connect ComfyUI/WAN.

## Common Workflows

### Convert Existing Video

Use the dashboard's Convert Video view, or use the CLI from the `app` folder:

```bat
python spriteforge.py video --input input\clip.mp4 --output output\clip_sprite
```

Best results come from videos with a locked camera, centered full-body subject,
clean silhouette, and solid green or blue background.

### Run the No-GPU Demo

From the repository root:

```bat
RUN_DEMO_NO_GPU.bat
```

Or from the `app` folder:

```bat
python spriteforge_demo.py
```

This path is useful because it checks the local Python/image-processing pipeline
without requiring ComfyUI or a GPU.

### Use ComfyUI/WAN Generation

The dashboard can launch setup actions and generate through ComfyUI, but the
success of this path depends on your environment. The safe starting tier is the
Wan 2.1 1.3B workflow. Wan 2.2 5B is heavier. 14B-class workflows should be
considered remote/cloud GPU work.

See:

- [app/docs/WAN_MODEL_TIERS_v11.md](app/docs/WAN_MODEL_TIERS_v11.md)
- [app/workflows/README_WAN_INTEGRATION.md](app/workflows/README_WAN_INTEGRATION.md)

## What Gets Produced

A typical processed sprite output folder contains:

```text
sheet.png
sheet.json
sheet.aseprite.json
preview.gif
report.html
contact_sheet.jpg
frames_processed/
godot_notes.txt
```

Depending on options, it may also include normal/specular/AO/height maps,
engine-specific exports, APNG/WebP animations, QA reports, or release metadata.

Generated outputs are intentionally ignored by Git.

## Project Layout

```text
app/
  spriteforge_web.py          Local Flask dashboard entry point
  spriteforge.py              Core sprite/video processing CLI
  spriteforge_unified.py      Unified command dispatcher
  services/                   Processing, QA, project, export, and web helpers
  web/                        Browser UI assets and components
  workflows/                  ComfyUI/WAN workflow JSON files
  docs/                       User and setup documentation
  examples/prebuilt_demo_sprite/

tests/                        Main automated test suite
projects/                     Sample/global project data
output/                       Local generated outputs, ignored by Git
```

## Testing

Run the test suite from the repository root:

```bat
pytest
```

At the time this README was rewritten, the suite passed locally with:

```text
203 passed
```

The tests cover service behavior, web APIs, project handling, QA thresholds,
packing/export formats, sprite processing, visual comparison, and regression
checks.

## Documentation

The most useful docs are:

- [app/docs/END_USER_GUIDE.md](app/docs/END_USER_GUIDE.md)
- [app/docs/FIRST_RUN_CHECKLIST_v8.md](app/docs/FIRST_RUN_CHECKLIST_v8.md)
- [app/docs/TROUBLESHOOTING_v8.md](app/docs/TROUBLESHOOTING_v8.md)
- [app/docs/WAN_MODEL_TIERS_v11.md](app/docs/WAN_MODEL_TIERS_v11.md)
- [app/docs/api.md](app/docs/api.md)
- [app/docs/PLUGIN_GUIDE.md](app/docs/PLUGIN_GUIDE.md)

Some filenames include older version numbers for compatibility. Their content is
still used by the current app.

## Distribution Notes

This repository does not include:

- ComfyUI installs.
- WAN checkpoints or other model weights.
- User-uploaded videos.
- Generated output folders.
- Local logs.
- Release ZIPs created from a user's workspace.

Large local payloads are excluded on purpose. See:

- [LICENSE](LICENSE)
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

## Honest Caveats

SpriteForge is useful today if you are comfortable running a local Python tool
and debugging your own AI/video environment. It is not yet a polished installer
with guaranteed one-click generation on every machine.

If your goal is to process already-generated clips into sprite sheets, the app is
much easier to use. If your goal is full local AI generation, expect to spend
time on ComfyUI, model placement, GPU memory settings, and workflow validation.
