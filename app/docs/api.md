# SpriteForge Studio API Reference

## Overview

SpriteForge Studio v12 exposes a local REST API via Flask on `http://127.0.0.1:8765/`. All endpoints return JSON unless noted otherwise.

## Authentication

The web server is designed for local-only use on `127.0.0.1`. All `POST` requests require the current in-memory session token.

Browser clients fetch the token from:

```text
GET /api/auth/token
```

Then send it on unsafe requests as:

```text
X-SF-Token: <token>
```

JSON clients may also include `"session_token": "<token>"` in the request body. Missing or invalid tokens return HTTP `401`.

---

## Status & Health

### `GET /api/auth/token`

Returns the current local session token for the running server process.

**Response:**
```json
{
  "ok": true,
  "token": "..."
}
```

### `GET /api/status`

Returns full system status including ComfyUI state, GPU info, model summary, disk usage, cleanup suggestions, active job, and recent outputs.

**Query Parameters:**
- `project` (optional) - Project name/path filter

**Response:**
```json
{
  "version": "v12 Final Polish",
  "root": "...",
  "python": "...",
  "comfy_url": "http://127.0.0.1:8188",
  "comfy_running": true,
  "gpu": {...},
  "models": {...},
  "disk": {...},
  "cleanup_suggestions": [...],
  "next_step": {...},
  "outputs": [...],
  "project_workspace": {...},
  "job": {...},
  "time": "10:30:00"
}
```

### `GET /api/status/stream` (SSE)

Server-Sent Events stream for real-time status updates. Events fire every 500ms.

**Response:** `text/event-stream`

```json
{
  "comfy_running": true,
  "comfy_url": "...",
  "gpu": {...},
  "job": {...},
  "time": "10:30:00"
}
```

---

## Jobs

### `GET /api/job`

Current active job or most recent history entry.

**Response:**
```json
{
  "running": true,
  "title": "Generate Sprite: hero_idle_right",
  "progress": 0.45,
  "exit_code": null,
  "logs": [...],
  "started_at": "2026-06-30T10:00:00",
  "finished_at": null,
  "eta": "~12m remaining"
}
```

### `GET /api/job/history`

List of all completed/failed jobs.

### `GET /api/job/detail?id=<job_id>`

Full job details including complete log output.

### `POST /api/run`

Start a new generation or action job.

**Request Body:**
```json
{
  "action": "generate_sprite",
  "prompt": "...",
  "negative": "...",
  "tier": "wan22_5b",
  "profile": "wan22_5b_3060_best",
  "sprite_action": "idle",
  "direction": "right",
  "seed": 42,
  "default_actions": "idle,walk,run",
  "default_directions": "left,right",
  "force": false
}
```

**Response:**
```json
{
  "ok": true,
  "message": "Job started.",
  "job": {...}
}
```

### `POST /api/cancel`

Cancel the currently running job.

### `POST /api/job/retry`

Retry a previously failed job by ID.

**Request Body:** `{"id": "job_abc123"}`

### `POST /api/job/retry_safe`

Intelligent retry with profile downgrade for OOM recoveries.

### `POST /api/launch_comfy`

Launch the ComfyUI server if not already running.

### `POST /api/prompt/autofix`

Auto-fix sprite prompts and negative prompts for the final prompt preview.

**Request Body:**
```json
{
  "prompt": "knight walking, cinematic camera",
  "negative": "blur",
  "action": "walk",
  "direction": "right"
}
```

**Response:**
```json
{
  "ok": true,
  "prompt": "...locked camera...",
  "negative": "...",
  "changes": [...]
}
```

---

## Queues

### `GET /api/queues`

List batch queues with progress. Filter with `?project=...`

### `GET /api/queues/detail?path=<queue_path>`

Detailed queue information including per-job progress and failure reasons.

### `POST /api/queues/reorder`

Reorder a queued job up/down.

**Request Body:** `{"path": "...", "job_id": "...", "direction": "up"}`

### `POST /api/queues/duplicate`

Duplicate a queued job (inserts below original).

### `POST /api/queues/delete`

Remove a job from a queue.

### `POST /api/queues/cancel_queue`

Cancel all pending/running jobs in a queue.

### `POST /api/job/clean_completed`

Remove completed jobs from history.

---

## Sprites & Outputs

### `GET /api/outputs`

List recent sprite outputs (up to 80). Filter with `?project=...`

### `GET /api/sprite/preview?path=<sprite_path>`

Get a preview bundle for a sprite output (sheet.json preview, frames, metadata).

### `GET /api/sprite/version/list?path=<sprite_path>`

List saved versions for a sprite.

### `POST /api/sprite/version/save`

Save a version snapshot of a sprite.

**Request Body:** `{"path": "...", "label": "v1.0"}`

### `POST /api/sprite/version/rollback`

Rollback to a previous version.

**Request Body:** `{"path": "...", "version_id": "..."}`

### `POST /api/sprite/save_metadata`

Save/update sheet.json metadata.

### `POST /api/sprite/edit_frames`

Edit sprite frames (delete, reorder, trim, hold).

**Request Body:**
```json
{
  "path": "...",
  "actions": [
    {"type": "delete", "indices": [0, 5]},
    {"type": "hold", "index": 3, "count": 2},
    {"type": "trim", "start": 2, "end": 8}
  ],
  "fps": 12
}
```

### `POST /api/sprite/frame/save`

Save an edited frame image (base64).

### `POST /api/sprite/frame/status`

Update frame QC status.

---

## QA & Quality

### `GET /api/qa/batch_summary`

Batch QA summary for all sprites in the project.

### `GET /api/sprite/validate_engine?path=...&engine=godot|unity`

Validate engine export readiness.

### `POST /api/release/precheck`

Run pre-release quality gate check.

### `POST /api/sprites/palette_harmonize`

Harmonize palettes across multiple sprites.

---

## Prompt Linting

### `POST /api/prompt/lint`

Score and lint a prompt for sprite-generation quality.

**Request Body:**
```json
{
  "prompt": "knight walking, 3d render, camera panning",
  "negative": "blur",
  "action": "walk"
}
```

**Response:**
```json
{
  "ok": true,
  "score": 62,
  "severity": "fair",
  "warnings": ["Avoid camera-movement terms: camera panning", "Terms better suited for negative prompt: 3d render"],
  "suggestions": ["Use 'locked camera' or 'fixed camera' for sprite generation", "Add 'plain bright green chroma key background' for clean extraction"],
  "checks": {...},
  "prompt_length": 42
}
```

---

## Character Archetypes

### `GET /api/archetypes`

List all character archetype templates. Filter with `?tag=monster` or `?search=skeleton`.

**Response:**
```json
{
  "ok": true,
  "archetypes": [
    {
      "id": "skeleton",
      "name": "Skeleton Warrior",
      "description": "An undead skeleton with rusty sword and shield",
      "character": "...",
      "style": "...",
      "recommended_actions": ["idle", "walk", "attack_light"],
      "recommended_directions": ["left", "right"],
      "palette_hint": "bone white, rust orange, dark iron"
    }
  ],
  "total": 21
}
```

---

## LPC Parts, Composer, and Training

### `POST /api/lpc/parts/scan`

Scan a Universal LPC source folder and write a catalog of readable paper-doll layers.

**Request Body:**
```json
{
  "source_dir": "app/input/lpc_assets/Universal-LPC-Spritesheet-Character-Generator",
  "output": "output/lpc_parts",
  "thumbnail_limit": 24
}
```

### `POST /api/lpc/parts/dataset`

Build a training dataset from individual LPC parts with captions.

**Request Body:**
```json
{
  "source_dir": "app/input/lpc_assets/Universal-LPC-Spritesheet-Character-Generator",
  "output": "output/training_datasets/lpc_parts",
  "trigger": "lpc_parts"
}
```

### `POST /api/lpc/options`

Return picker options for the dedicated LPC tab and Training Lab composer.

**Request Body:**
```json
{
  "source_dir": "app/input/lpc_assets/Universal-LPC-Spritesheet-Character-Generator",
  "categories": ["hair", "torso", "legs", "feet", "weapons"],
  "limit_per_category": 240
}
```

### `POST /api/lpc/compose`

Compose one LPC character spritesheet from selected layers.

**Request Body:**
```json
{
  "source_dir": "app/input/lpc_assets/Universal-LPC-Spritesheet-Character-Generator",
  "compose_action": "idle",
  "body_type": "male",
  "compose_name": "hero_idle",
  "selections": {
    "hair": "afro",
    "torso": "shirt",
    "legs": "pants",
    "feet": "shoes"
  }
}
```

### `POST /api/lpc/batch-compose`

Build a balanced dataset of composed LPC character sheets for LoRA training.

**Request Body:**
```json
{
  "source_dir": "app/input/lpc_assets/Universal-LPC-Spritesheet-Character-Generator",
  "batch_count": 48,
  "batch_actions": "idle,walk,slash,cast",
  "batch_body_types": "male,female",
  "batch_categories": "hair,torso,legs,feet,weapons",
  "trigger": "lpc_composed"
}
```

### `POST /api/lpc/dataset-qa`

Validate a composed LPC dataset before LoRA handoff.

**Request Body:**
```json
{
  "dataset_dir": "output/training_datasets/lpc_composed_123",
  "min_layers": 3
}
```

### `POST /api/lpc/lora-prefill`

Return recommended LoRA training settings for a QA-passed composed LPC dataset.

**Request Body:**
```json
{
  "dataset_dir": "output/training_datasets/lpc_composed_123"
}
```

---

## Cloud Image Providers

### `GET /api/cloud/image-providers`

Return provider metadata and key readiness for Hugging Face, OpenAI, Google/Gemini, Anthropic, Moonshot/Kimi, GLM, DeepSeek, and Grok/xAI slots. Use `?provider=openai` to inspect one provider.

### `POST /api/cloud/image-provider-key`

Save a provider API key to the local app environment.

**Request Body:**
```json
{
  "provider": "openai",
  "api_key": "..."
}
```

### `DELETE /api/cloud/image-provider-key`

Remove stored local keys for a provider.

**Request Body:**
```json
{
  "provider": "openai"
}
```

### `POST /api/cloud/image-generation-plan`

Preview the hardened prompts and post-processing plan for a cloud image generation request without launching a full local WAN job.

---

## Pixel Studio

Pixel Studio endpoints power prompt/reference pixel assets, normalization, direction sheets, tilesets, edit/inpaint, animation, transfer, rigging, and pack export.

### `GET /api/pixel-assets/modes`

Return supported Pixel Studio asset modes.

**Response:**
```json
{
  "ok": true,
  "modes": ["characters", "creatures", "items", "weapons", "potions", "ui_icons", "tilesets", "backgrounds"],
  "mode_configs": {
    "weapons": {
      "label": "Weapons",
      "controls": {
        "class": ["sword", "axe", "bow", "staff", "dagger", "spear"]
      }
    }
  }
}
```

### `POST /api/pixel-assets/generate`

Generate a batch of pixel assets or return a dry-run plan.

**Request Body:**
```json
{
  "asset_type": "weapons",
  "prompt": "golden bow",
  "resolution": "24x24",
  "palette_size": "16",
  "provider": "openai",
  "count": 2,
  "style_profile_id": "style_fantasy",
  "mode_options": {
    "class": "bow",
    "material": "wood",
    "effects": "none"
  },
  "mock": true
}
```

Use `"dry_run": true` to return a prompt/provider plan without writing assets.
`mode_options` are validated against `app/config/pixel_asset_modes.json` and included in the expanded prompt through `app/config/pixel_prompt_templates.json`.

### `POST /api/pixel-assets/failure/explain`

Return a plain-English Pixel Studio failure explainer for UI panels and troubleshooting.

**Request Body:**
```json
{
  "message": "Key Validation Failed: Missing local API key."
}
```

**Response:**
```json
{
  "ok": true,
  "explainer": {
    "code": "pixel_missing_provider_key",
    "title": "Provider key is missing",
    "fix": "Open Setup or Cloud Hub, save the provider key, then retry."
  }
}
```

### `POST /api/pixel-assets/qa/report`

Build a visual QA report for a Pixel Studio asset from its sidecar metadata.

**Request Body:**
```json
{
  "asset_id": "pxa_123"
}
```

The UI may also send an `asset` object to avoid re-reading the sidecar when the current metadata is already in memory.

**Response includes:**
- `schema: "spriteforge.pixel_visual_qa.v1"`
- `score`
- `status`
- `gates` for palette, alpha/background, sharpness, tile seams, style match, versions, cleanup, and inpaint trace when present
- `recommendations`

### `GET /api/pixel-assets/qa/report.html?asset_id=<id>`

Generate and open a saved Pixel Studio visual QA HTML page for the asset. The page is written beside the asset as `pixel_qa_report.html`.

### `POST /api/pixel-assets/normalize`

Normalize an existing image to pixel-art constraints.

**Request Body:**
```json
{
  "path": "output/pixel_assets/assets/pxa_123/raw.png",
  "resolution": "16x16",
  "clean_alpha": true,
  "quantize_palette": true,
  "max_colors": 8,
  "remove_islands": true,
  "min_island_size": 2,
  "outline": "none"
}
```

### `GET /api/pixel-assets/style/list`

List saved Pixel Studio style profiles.

### `POST /api/pixel-assets/style/save`

Save a Pixel Studio style profile.

**Request Body:**
```json
{
  "name": "Cozy RPG",
  "outline_hint": "dark one-pixel outline",
  "shading_hint": "limited 16-bit cel shading",
  "camera_hint": "orthographic sprite view",
  "lora_name": "cozy-rpg-lora",
  "lora_weight": 0.8,
  "base_model": "stable-diffusion-xl"
}
```

### `POST /api/pixel-assets/style/extract`

Create a reusable style profile from an existing Pixel Studio asset or workspace image.

**Request Body:**
```json
{
  "asset_id": "pxa_123",
  "name": "Hero Sprite Style",
  "max_colors": 24
}
```

### `POST /api/pixel-assets/style/compare`

Score a Pixel Studio asset against a saved style profile.

**Request Body:**
```json
{
  "asset_id": "pxa_123",
  "style_id": "style_project"
}
```

**Response includes:**
- `palette_overlap`
- `size_match`
- `overall`
- `recommendation`

### `GET /api/pixel-assets/history`

Return saved Pixel Studio asset metadata records plus linked experiment-memory rows.

Optional query parameters:
- `q`: search prompts, asset ids, roles, providers, and output paths.
- `asset_type` or `mode`: filter by saved asset type, such as `characters`, `weapons`, `tilesets`, or `ui_icons`.
- `limit`: cap results from `1` to `250`; defaults to `80`.

**Response:**
```json
{
  "ok": true,
  "history": [{ "schema": "spriteforge.pixel_asset.v1" }],
  "experiment_history": [{ "job_id": "pixel_asset:pxa_123" }],
  "filters": { "q": "golden", "asset_type": "weapons", "limit": 80 }
}
```

Generated Pixel Studio assets also write a `memory` block into their sidecar with the linked `experiment_run_id` and, when a project name is supplied, the `library_asset_id`.

### `GET /api/lora/progress`

Inspect a LoRA training run folder for loss points, preview samples, and finished `.safetensors`, `.pt`, or `.ckpt` checkpoints.

Optional query:
- `path=output/training_runs/my_run`

### `POST /api/lora/register-checkpoint`

Register a completed external trainer checkpoint in the shared LoRA registry. If `checkpoint_path` is omitted, SpriteForge registers the newest checkpoint found under `run_path`.

**Request Body:**
```json
{
  "run_path": "output/training_runs/cutesckr_tile_style_kohya_ready",
  "role": "tile_style",
  "label": "CuteSCKR Tile Style",
  "make_default": true
}
```

**Response includes:**
- `role`
- `filename`
- `registry_path`
- `default`
- `record`

### `GET /api/pixel-assets/loras`

Return built-in Pixel Studio LoRA presets for style/profile controls.

### `GET /api/pixel-assets/providers/capabilities`

Return Pixel Studio provider capability metadata for generation, edit, inpaint, and prompt-help workflows.

Optional query:
- `provider=openai`

**Response includes:**
- local fallback and local ComfyUI entries
- cloud provider configured status without exposing key values
- `capabilities`
- `free_tier`
- provider limits and notes

### `POST /api/pixel-assets/providers/plan`

Return a provider workflow plan for a Pixel Studio action, including whether SpriteForge should use the selected provider or local fallback.

**Request Body:**
```json
{
  "provider": "openai",
  "workflow": "inpaint"
}
```

**Response includes:**
- `status`
- `supports_workflow`
- `configured`
- `adapter_wired`
- `fallback_provider`
- `mock_recommended`
- `provider_capability`

### `POST /api/pixel-assets/directions`

Generate a 1, 4, or 8-direction character sheet.

**Request Body:**
```json
{
  "prompt": "elf rogue",
  "resolution": "32x32",
  "palette_size": 16,
  "provider": "gemini",
  "count": 4,
  "mock": true
}
```

**Response includes:**
- `batch_id`
- `assets`
- `manifest`
- `consistency_scores`

### `GET /api/pixel-assets/export?batch_id=<id>&engine=godot|unity|aseprite`

Export a Pixel Studio batch as a ZIP for the requested engine/tool.
Godot exports for tileset batches include `godot_tileset.json` with tile size, atlas coordinates, roles, and `TileSetAtlasSource` setup hints.

### `POST /api/pixel-assets/tileset`

Generate a top-down, side-scroller, or isometric tileset with seam checks.

**Request Body:**
```json
{
  "prompt": "ruins cobblestone",
  "tileset_type": "side-scroller",
  "resolution": "16x16",
  "palette_size": 16,
  "provider": "gemini",
  "mock": true
}
```

### `POST /api/pixel-assets/tileset/repair`

Repair the selected tileset tile by blending opposite edges for cleaner seams. The current `asset.png` is saved into `versions/`, `tile_repair_history` records before/after seam deltas, and the asset QA seam metrics are refreshed.

**Request Body:**
```json
{ "asset_id": "pxa_tile_123" }
```

### `POST /api/pixel-assets/edit`

Alias: `POST /api/pixel-assets/edit/save`

Save a browser-edited pixel asset image.

**Request Body:**
```json
{
  "asset_id": "pxa_123",
  "image_data": "data:image/png;base64,..."
}
```

The Pixel Studio editor can create this payload from manual pencil, eraser, fill, picker, line, rectangle, selection/move, or imported PNG edits.

### `POST /api/pixel-assets/version/save`

Copy the current `asset.png` into the asset's `versions/` folder and append version metadata.

**Request Body:**
```json
{
  "asset_id": "pxa_123",
  "label": "manual cleanup pass"
}
```

### `POST /api/pixel-assets/cleanup`

Run one-click cleanup on a selected Pixel Studio asset. This removes obvious corner-color backgrounds, snaps to the requested resolution, cleans alpha, clamps palette colors, removes small islands, updates QA/palette sidecar fields, and stores the previous `asset.png` in `versions/`.

**Request Body:**
```json
{
  "asset_id": "pxa_123",
  "remove_background": true,
  "resolution": "32x32",
  "clean_alpha": true,
  "quantize_palette": true,
  "max_colors": 24,
  "remove_islands": true,
  "outline": "none"
}
```

### `POST /api/pixel-assets/inpaint`

Apply a masked edit workflow to an existing pixel asset.

**Request Body:**
```json
{
  "asset_id": "pxa_123",
  "image_data": "data:image/png;base64,...",
  "mask_data": "data:image/png;base64,...",
  "prompt": "make it gold color",
  "mock": true
}
```

### `POST /api/pixel-assets/part/apply`

Create non-destructive outfit, armor, weapon, or accessory variants for an existing pixel asset.

**Request Body:**
```json
{
  "asset_id": "pxa_123",
  "part_prompt": "gold chest armor",
  "part_image_data": "data:image/png;base64,...",
  "count": 3,
  "mock": true
}
```

### `POST /api/pixel-assets/part/accept`

Accept one generated part variant and apply it to `asset.png`. The previous asset image is copied into `versions/`, and the sidecar receives `part_apply_history`.

**Request Body:**
```json
{
  "asset_id": "pxa_123",
  "variant_path": "output/pixel_assets/assets/pxa_123/part_variants/part_abc/part_abc_v1.png",
  "label": "gold chest armor"
}
```

### `POST /api/pixel-assets/reskin`

Create fast non-destructive palette/theme variations from an existing pixel asset.

**Request Body:**
```json
{
  "asset_id": "pxa_123",
  "prompt": "ice blue variant",
  "count": 6,
  "mock": true
}
```

### `POST /api/pixel-assets/reskin/accept`

Accept one reskin variant and apply it to `asset.png`. The previous asset image is copied into `versions/`, and the sidecar receives `reskin_history`.

**Request Body:**
```json
{
  "asset_id": "pxa_123",
  "variant_path": "output/pixel_assets/assets/pxa_123/reskin_variants/reskin_abc/reskin_abc_v1.png",
  "label": "ice blue variant"
}
```

### `POST /api/pixel-assets/animate`

Generate an animation sheet plus GIF, APNG, and animated WebP previews from an asset.

**Request Body:**
```json
{
  "asset_id": "pxa_123",
  "action_type": "run",
  "frame_count": 6,
  "fps": 12,
  "mock": true
}
```

### `POST /api/pixel-assets/animation-transfer`

Transfer an existing sheet layout/motion to a new prompt/style.
The transfer manifest includes `pose_captions` for each source frame and `qa.before_repair` / `qa.after_repair` consistency metrics from the centering repair pass.

**Request Body:**
```json
{
  "source_sheet_path": "input/source_sheet.png",
  "rows": 1,
  "cols": 2,
  "prompt": "change to blue wizard",
  "mock": true
}
```

### `POST /api/pixel-assets/rig/render`

Alias: `POST /api/pixel-assets/skeleton/render`

Render a lightweight skeleton/bone rig animation from an existing asset.

**Request Body:**
```json
{
  "asset_id": "pxa_123",
  "bones": [],
  "keyframes": [],
  "frame_count": 4,
  "mock": true
}
```

### `POST /api/pixel-assets/pack/generate`

Alias: `POST /api/pixel-assets/pack/build`

Generate a cohesive asset pack from a built-in or saved recipe.

**Request Body:**
```json
{
  "recipe_type": "rpg_starter",
  "style_profile_id": "style_fantasy",
  "mock": true
}
```

Supported recipes include:
- `rpg_starter`
- `dungeon_crawler`
- `platformer_starter`
- `potion_shop`
- `ui_hud_pack`

### `GET /api/pixel-assets/pack/export?pack_id=<id>`

Export a generated Pixel Studio pack as a ZIP containing asset PNGs, sidecar metadata, `pack_manifest.json`, and `catalog.html`.

### `GET /api/pixel-assets/recipes`

List built-in and user-saved Pixel Studio recipes.

### `POST /api/pixel-assets/recipes/save`

Save a reusable recipe for Pixel Studio pack generation.

**Request Body:**
```json
{
  "schema": "spriteforge.pixel_recipe.v1",
  "recipe_id": "recipe_custom_shop",
  "name": "Custom Shop",
  "items": [
    {"type": "potions", "prompt": "tiny green potion", "resolution": "16x16", "count": 4}
  ]
}
```

### `POST /api/pixel-assets/recipes/import`

Import a recipe JSON payload and save it locally.

The in-app Pack Builder import button posts the selected JSON file to this endpoint, refreshes the recipe selector, and selects the imported recipe.

### `GET /api/pixel-assets/recipes/export?recipe_id=<id>`

Download a recipe JSON file for sharing or backup.

---

## Experiments & A/B Runs

### `GET /api/experiments`

List experiment history. Filter with `?project=...`

### `POST /api/experiments/review`

Mark an experiment as starred, rejected, or reviewed.

### `POST /api/experiments/note`

Add notes to an experiment.

### `POST /api/experiments/star`

Toggle star on experiment.

### `POST /api/experiments/clear`

Clear experiment history (keeps starred by default).

### `POST /api/experiments/rerun_similar`

Create a similar run from an experiment record.

### `POST /api/ab_run/create`

Create a new A/B comparison run.

### `GET /api/ab_run/list`

List all A/B comparison runs.

### `POST /api/compare`

Compare two sprite directories.

**Request Body:** `{"a": "path/to/sprite_a", "b": "path/to/sprite_b"}`

---

## Cleanup & Maintenance

### `GET /api/cleanup/scan`

Scan for unused files (ComfyUI outputs, uploads, failed outputs, old logs).

### `POST /api/cleanup/purge`

Purge selected files by ID.

### `GET /api/config`

Get current SpriteForge configuration.

### `GET /api/advisor?quality=balanced`

Get hardware/pipeline advisor recommendations.

### `GET /api/model/explain?tier=wan22_5b&profile=...`

Explain a model tier and profile.

### `GET /api/preflight/generation`

Run preflight checks before generation.

### `POST /api/open`

Open a folder path in the OS file explorer.

---

## Error Responses

All errors follow this format:

```json
{
  "ok": false,
  "message": "Error description",
  "error": "Optional error details"
}
```

HTTP status codes:
- `401` - Unauthorized (missing or invalid session token on POST)
- `400` - Bad request (missing parameters)
- `403` - Forbidden (path outside workspace)
- `404` - Not found (sprite/job not found)
- `409` - Conflict (job already running)
- `500` - Internal server error
