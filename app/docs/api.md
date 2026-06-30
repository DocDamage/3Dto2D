# SpriteForge Studio API Reference

## Overview

SpriteForge Studio v12 exposes a local REST API via Flask on `http://127.0.0.1:8765/`. All endpoints return JSON unless noted otherwise.

## Authentication

Currently, the API is designed for local-only use (`127.0.0.1`). No authentication is required for local access. For network-exposed usage (`--listen 0.0.0.0`), configure an API key in `spriteforge_config.json` under `web_server.api_key`.

---

## Status & Health

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
- `400` - Bad request (missing parameters)
- `403` - Forbidden (path outside workspace)
- `404` - Not found (sprite/job not found)
- `409` - Conflict (job already running)
- `500` - Internal server error