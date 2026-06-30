# SpriteForge Product Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Turn the 10 proposed additions and 20 proposed improvements into a prioritized, testable roadmap for making SpriteForge Studio feel like a complete production sprite workstation.

**Architecture:** Keep changes inside the current Flask service, vanilla JS component, and Python service boundaries. Implement the roadmap in independent tracks so each track can ship with tests, docs, and a focused commit without blocking the rest of the product plan.

**Tech Stack:** Python, Flask, Pillow, vanilla JavaScript, existing SpriteForge services, existing web components, JSON metadata, optional SQLite for later state persistence.

---

## Roadmap Overview

This plan groups all 30 original recommendations plus the additional ease-of-use recommendations into seven implementation tracks:

1. **Preview and Review Workflow**: animation player, frame editor, A/B diff player, Quality Lab before/after review.
2. **Generation Guidance**: prompt linting, reference style lock, seed reuse, model/profile explainers.
3. **Production Pipeline**: character pack wizard, queue retry, animated exports, release metadata.
4. **Reliability and Safety**: API token protection, status caching, startup self-test, JSON schemas, safer writes.
5. **User Experience and Accessibility**: loading states, toasts, mobile polish, accessible statuses, guided forms.
6. **Extensibility and Operations**: plugin manager, notifications, state storage, frontend organization.
7. **Ease-of-Use Fast Track**: sample project, first-sprite wizard, smart defaults, plain-English failures, resume state, command launcher, undo, drag-and-drop, export recipes.

Existing related plans:

- `docs/superpowers/plans/2026-06-30-roadmap-phase-1-live-preview-onion-skin.md`
- `docs/superpowers/plans/2026-06-30-generation-intelligence.md`

---

## Target File Map

### Backend Services

- Modify: `app/services/sprite_preview_service.py` if created; otherwise keep preview helpers in `app/web_helpers.py`
- Modify: `app/services/sprite_sheet_service.py` for APNG/WebP export and metadata-preserving repack
- Modify: `app/services/prompt_linter_service.py` for prompt scoring and warnings
- Modify: `app/services/palette_harmonizer_service.py` for reference palette extraction and generation handoff
- Modify: `app/services/job_service.py` for queue retry, safer job state, and notification hooks
- Modify: `app/services/notification_service.py` for webhook/system notification delivery
- Modify: `app/services/seed_gallery_service.py` for best-seed persistence and reuse
- Modify: `app/services/plugin_manager.py` for UI-visible plugin discovery and enablement
- Modify: `app/services/qa_threshold_service.py` for configurable QA weights and thresholds
- Modify: `app/services/advisor_service.py` for smart defaults and plain-English recommendations
- Modify: `app/services/project_service.py` for sample project creation, resume state, and named output conventions
- Modify: `app/services/open_path_service.py` for user-facing output-folder actions
- Create: `app/services/startup_self_test_service.py` for startup diagnostics
- Create: `app/services/schema_validation_service.py` for JSON schema validation
- Create: `app/services/api_auth_service.py` for local API token validation
- Create: `app/services/onboarding_service.py` for first-run sample project and first-sprite wizard orchestration
- Create: `app/services/action_command_service.py` for global command palette action discovery and execution
- Create: `app/services/failure_explainer_service.py` for converting common failures into user-facing recovery guidance

### Web Routes

- Modify: `app/web_routes/routes_sprites.py` for frame save validation, repack endpoints, animated export endpoints
- Modify: `app/web_routes/routes_jobs.py` for retry failed jobs, lightweight heartbeat, and safer status streaming
- Modify: `app/web_routes/routes_projects.py` for validated project import/export
- Modify: `app/web_routes/routes_misc.py` for startup self-test and plugin manager APIs
- Modify: `app/web_routes/routes_static.py` only if static asset serving needs cache hints
- Create: `app/web_routes/routes_onboarding.py` for sample project, resume state, first-sprite wizard, command palette, and export recipe APIs

### Frontend Components

- Modify: `app/web/components/generate.html` for guided controls, prompt linting, reference style lock, and seed reuse
- Modify: `app/web/components/quality.html` for before/after repair review and frame timeline editing
- Modify: `app/web/components/ab_runs.html` for synchronized diff playback and N-way comparison
- Modify: `app/web/components/queues.html` for retry failed jobs and job failure grouping
- Modify: `app/web/components/setup.html` for startup self-test and plugin manager controls
- Modify: `app/web/components/release.html` for APNG/WebP export controls
- Modify: `app/web/components/history.html` for prompt favorites and rerun-from-history
- Modify: `app/web/components/guide.html` for one-click sample project and first-sprite wizard entry points
- Modify: `app/web/components/launchpad.html` for resume card, smart defaults, and suggested next action
- Modify: `app/web/components/dashboard.html` for last project, latest sprite, unfinished job, and empty-state guidance

### Frontend JavaScript

- Modify: `app/web/js/sprite_preview.js` for interactive animation playback
- Modify: `app/web/js/frame_review.js` for timeline editing and before/after repair
- Modify: `app/web/js/prompt_builder.js` for linting results, favorites, and history
- Modify: `app/web/js/seed_gallery.js` for seed reuse controls
- Modify: `app/web/js/app_jobs.js` for retry failed and clearer queue failure states
- Modify: `app/web/js/app_status.js` for heartbeat/full-status split
- Modify: `app/web/js/app_notifications.js` for capped notification storage
- Modify: `app/web/js/marketplace_gallery.js` if plugin marketplace/install UI shares patterns
- Modify: `app/web/js/app_main.js` for load failure recovery and route-level loading states
- Modify: `app/web/js/app_guide.js` for sample project and first-sprite wizard controls
- Modify: `app/web/js/app_dashboard.js` for resume state, empty states, and latest-output summaries
- Modify: `app/web/js/drag_drop.js` for project-wide drag-and-drop import handling
- Create: `app/web/js/command_palette.js` for global command/search behavior

### Frontend CSS

- Modify: `app/web/styles.css`
- Modify: `app/web/sprite_preview.css`
- Modify: `app/web/frame_review.css`
- Modify: `app/web/prompt_builder.css`
- Modify: `app/web/seed_gallery.css`
- Modify: `app/web/css/accessibility.css`
- Modify: `app/web/mobile_nav.css`

### Config, Schemas, and Docs

- Modify: `app/config/spriteforge_config.json`
- Modify: `app/config/character_archetypes.json`
- Create: `app/config/schemas/spriteforge_config.schema.json`
- Create: `app/config/schemas/project.schema.json`
- Create: `app/config/schemas/queue.schema.json`
- Create: `app/config/schemas/sheet.schema.json`
- Modify: `app/docs/END_USER_GUIDE.md`
- Modify: `app/docs/api.md`
- Modify: `app/docs/PLUGIN_GUIDE.md`
- Modify: `app/docs/ONE_PAGE_CHEAT_SHEET.md`

### Tests

- Modify: `tests/test_web_api.py`
- Modify: `tests/test_spriteforge_jobs.py`
- Modify: `tests/test_spriteforge_projects.py`
- Modify: `tests/test_generation_intelligence.py`
- Modify: `tests/test_advanced_features.py`
- Modify: `tests/test_editor_history.py`
- Modify: `tests/test_pack_formats.py`
- Create: `tests/test_prompt_linter.py`
- Create: `tests/test_startup_self_test.py`
- Create: `tests/test_schema_validation.py`
- Create: `tests/test_api_auth.py`
- Create: `tests/test_animated_exports.py`
- Create: `tests/test_onboarding.py`
- Create: `tests/test_action_command_service.py`
- Create: `tests/test_failure_explainer.py`

---

## Phase 1: Preview and Quality Review

### Task 1: Interactive Animation Preview

**Covers:** Addition 1, Improvement 7

**Files:**
- Modify: `app/web_helpers.py`
- Modify: `app/web/js/sprite_preview.js`
- Modify: `app/web/sprite_preview.css`
- Modify: `app/web/components/quality.html`
- Test: `tests/test_advanced_features.py`

- [x] **Step 1: Add backend frame manifest test**

Create or extend a test that builds a temporary sprite output with `sheet.json`, `sheet.png`, and `frames_processed/frame_0000.png`, then asserts the preview bundle returns ordered frame URLs, frame count, FPS, and sheet metadata.

Run: `python -m pytest tests/test_advanced_features.py::test_sprite_preview_bundle_includes_frame_manifest -q`

Expected before implementation: FAIL because the preview bundle does not expose the full manifest contract.

- [x] **Step 2: Implement frame manifest support**

Add a helper that discovers `frames_processed/*.png`, falls back to sheet metadata if processed frames are unavailable, and returns records shaped like:

```json
{
  "index": 0,
  "url": "/api/file?path=...",
  "name": "frame_0000.png",
  "duration_ms": 83,
  "sheet_rect": {"x": 0, "y": 0, "w": 512, "h": 512}
}
```

- [x] **Step 3: Add animation player controls**

In the preview UI, add FPS, zoom, background, frame-step, play/pause, and onion-skin controls. Keep controls compact and consistent with the existing Quality Lab.

- [x] **Step 4: Implement playback**

Use `requestAnimationFrame` in `app/web/js/sprite_preview.js`. Advance frames by elapsed time so playback remains accurate even when browser timing varies.

- [x] **Step 5: Verify**

Run:

```powershell
python -m pytest tests/test_advanced_features.py tests/test_web_api.py -q
node --check app\web\js\sprite_preview.js
```

Expected: tests pass and JavaScript parses.

### Task 2: Frame Timeline Editor

**Covers:** Addition 4, Improvement 10

**Files:**
- Modify: `app/services/sprite_sheet_service.py`
- Modify: `app/web_routes/routes_sprites.py`
- Modify: `app/web/components/quality.html`
- Modify: `app/web/js/frame_review.js`
- Modify: `app/web/frame_review.css`
- Test: `tests/test_editor_history.py`

- [x] **Step 1: Test repack operations**

Add tests for delete frame, duplicate frame, reorder frames, set per-frame duration, and repack without losing `sheet.json` metadata.

- [x] **Step 2: Add `/api/sprite/repack`**

Accept a sprite directory and a frame operation list. Validate paths, apply operations to a copy of the frame list, rebuild `sheet.png`, and write updated `sheet.json`.

- [x] **Step 3: Add timeline UI**

Render frame thumbnails as a horizontal timeline. Add controls for delete, duplicate, move left/right, duration, and rebuild preview.

- [x] **Step 4: Add before/after repair review**

When a repair action runs, show the original and repaired frames side by side before replacing the active result.

- [x] **Step 5: Verify**

Run:

```powershell
python -m pytest tests/test_editor_history.py tests/test_spriteforge_api.py -q
node --check app\web\js\frame_review.js
```

Expected: tests pass and JavaScript parses.

### Task 3: Side-by-Side Diff Player and N-Way Compare

**Covers:** Addition 5, Improvement 12

**Files:**
- Modify: `app/spriteforge_compare.py`
- Modify: `app/services/web_helpers_ab.py`
- Modify: `app/web/components/ab_runs.html`
- Modify: `app/web/js/experiments.js`
- Modify: `app/web/css/inspector_ab_compare.css`
- Test: `tests/test_advanced_features.py`

- [x] **Step 1: Test comparison manifest**

Add a test that compares two sprite outputs and asserts synchronized frame records, QA deltas, and a diff summary.

- [x] **Step 2: Add backend comparison bundle**

Return frame manifests for each selected run, shared playback FPS, QA scores, and optional alpha/visual diff image URLs.

- [x] **Step 3: Build synchronized compare player**

Add play/pause, frame step, diff overlay, alpha heatmap toggle, and QA summary rows.

- [x] **Step 4: Extend to N-way comparison**

Allow selecting more than two runs and render a grid where all players share the same frame index.

- [x] **Step 5: Verify**

Run:

```powershell
python -m pytest tests/test_advanced_features.py -q
node --check app\web\js\experiments.js
```

Expected: tests pass and JavaScript parses.

---

## Phase 2: Generation Guidance

### Task 4: Prompt Linting and Prompt History

**Covers:** Addition 2, Improvement 13

**Files:**
- Modify: `app/services/prompt_linter_service.py`
- Modify: `app/web_routes/routes_sprites.py`
- Modify: `app/web/components/generate.html`
- Modify: `app/web/js/prompt_builder.js`
- Test: `tests/test_prompt_linter.py`

- [x] **Step 1: Add prompt linter tests**

Test missing locked camera, missing transparent/chroma background cue, contradictory camera language, overly long prompts, and strong sprite-positive prompts.

- [x] **Step 2: Implement lint rules**

Return a score from 0 to 100, warning records, blocking errors only for known-invalid inputs, and suggested replacement phrases.

- [x] **Step 3: Add API endpoint**

Add an endpoint that accepts prompt text and returns lint results without starting a generation job.

- [x] **Step 4: Add UI feedback**

Show score, warnings, and one-click prompt improvements beside the Generate Sprite prompt box.

- [x] **Step 5: Add favorites and history**

Let users pin prompts, rerun previous prompts, and autocomplete from successful experiment history.

- [x] **Step 6: Verify**

Run:

```powershell
python -m pytest tests/test_prompt_linter.py tests/test_web_api.py -q
node --check app\web\js\prompt_builder.js
```

Expected: tests pass and JavaScript parses.

### Task 5: Reference Style Lock and Palette Handoff

**Covers:** Addition 3, Improvement 9

**Files:**
- Modify: `app/services/palette_harmonizer_service.py`
- Modify: `app/services/prompt_builder_service.py`
- Modify: `app/services/sprite_processing_pipeline.py`
- Modify: `app/web/components/generate.html`
- Modify: `app/web/js/palette_harmonizer.js`
- Test: `tests/test_generation_intelligence.py`

- [x] **Step 1: Test reference extraction**

Create synthetic reference images and assert palette colors, approximate outline thickness, transparent coverage, and dominant sprite bounds are extracted.

- [x] **Step 2: Add reference style profile**

Create a JSON-serializable profile with palette, outline hint, size/proportion hint, and optional prompt phrase suggestions.

- [x] **Step 3: Wire profile into generation**

Allow generation requests to pass a reference style profile. Store the chosen profile in job metadata and output `sheet.json`.

- [x] **Step 4: Add palette-locked post-processing**

Quantize output frames to the selected palette when the user enables palette lock.

- [x] **Step 5: Verify**

Run:

```powershell
python -m pytest tests/test_generation_intelligence.py tests/test_advanced_features.py -q
node --check app\web\js\palette_harmonizer.js
```

Expected: tests pass and JavaScript parses.

### Task 6: Seed Reuse and Best-Seed Persistence

**Covers:** Improvement 11

**Files:**
- Modify: `app/services/seed_gallery_service.py`
- Modify: `app/services/job_service.py`
- Modify: `app/web/js/seed_gallery.js`
- Modify: `app/web/components/history.html`
- Test: `tests/test_generation_intelligence.py`

- [x] **Step 1: Test best-seed selection**

Add tests that mark a result as passed QA and starred, then assert its seed is written to pack or project metadata.

- [x] **Step 2: Persist winning seeds**

Write winning seed records with prompt, action, direction, model, profile, QA score, and output path.

- [x] **Step 3: Add reuse controls**

Add “reuse best seed” and “rerun with same seed” actions in History and Generate Sprite.

- [x] **Step 4: Verify**

Run:

```powershell
python -m pytest tests/test_generation_intelligence.py -q
node --check app\web\js\seed_gallery.js
```

Expected: tests pass and JavaScript parses.

---

## Phase 3: Production Pipeline

### Task 7: Character Pack Wizard

**Covers:** Addition 6

**Files:**
- Modify: `app/config/character_archetypes.json`
- Modify: `app/services/prompt_builder_service.py`
- Modify: `app/services/job_service.py`
- Modify: `app/web/components/generate.html`
- Modify: `app/web/components/queue.html`
- Test: `tests/test_spriteforge_jobs.py`

- [x] **Step 1: Test archetype-to-queue creation**

Add tests that select an archetype, actions, and directions, then assert a production queue is created with resolved prompts.

- [x] **Step 2: Expand archetype config**

Add archetype records with name, body description, default actions, style hints, forbidden prompt terms, and recommended QA thresholds.

- [x] **Step 3: Add wizard UI**

Guide the user through archetype, outfit/colors, actions, directions, model/profile, and queue creation.

- [x] **Step 4: Verify**

Run:

```powershell
python -m pytest tests/test_spriteforge_jobs.py tests/test_web_api.py -q
```

Expected: tests pass.

### Task 8: Animated APNG/WebP Export

**Covers:** Addition 7

**Files:**
- Modify: `app/services/sprite_sheet_service.py`
- Modify: `app/spriteforge_pack_formats.py`
- Modify: `app/web_routes/routes_sprites.py`
- Modify: `app/web/components/release.html`
- Test: `tests/test_animated_exports.py`

- [x] **Step 1: Test APNG and WebP export**

Use synthetic RGBA frames and assert APNG/WebP files are created, non-empty, and preserve expected frame duration metadata where Pillow supports it.

- [x] **Step 2: Implement exporters**

Add `export_apng()` and `export_webp_animation()` using existing frame ordering from `sheet.json`.

- [x] **Step 3: Add release controls**

Expose APNG/WebP as optional release package artifacts.

- [x] **Step 4: Verify**

Run:

```powershell
python -m pytest tests/test_animated_exports.py tests/test_pack_formats.py -q
```

Expected: tests pass.

### Task 9: Queue Retry and Failure Grouping

**Covers:** Improvement 17

**Files:**
- Modify: `app/services/job_service.py`
- Modify: `app/web_routes/routes_jobs.py`
- Modify: `app/web/components/queues.html`
- Modify: `app/web/js/app_jobs.js`
- Test: `tests/test_spriteforge_jobs.py`

- [x] **Step 1: Test retry failed jobs**

Create a queue with failed and completed jobs. Assert retry only requeues failed jobs and preserves original job metadata.

- [x] **Step 2: Add retry endpoint**

Add `/api/queues/retry_failed` with input validation and a response showing retried job count.

- [x] **Step 3: Add Queue Monitor UI**

Group jobs by status and add “Retry failed” and “Retry selected” controls.

- [x] **Step 4: Verify**

Run:

```powershell
python -m pytest tests/test_spriteforge_jobs.py tests/test_web_api.py -q
node --check app\web\js\app_jobs.js
```

Expected: tests pass and JavaScript parses.

---

## Phase 4: Reliability and Safety

### Task 10: API Token Protection and Safer File Writes

**Covers:** Improvement 16 plus local API safety hardening

**Files:**
- Create: `app/services/api_auth_service.py`
- Modify: `app/web_routes/routes_jobs.py`
- Modify: `app/web_routes/routes_sprites.py`
- Modify: `app/web_routes/routes_misc.py`
- Modify: `app/services/web_helpers_cmd.py`
- Test: `tests/test_api_auth.py`

- [x] **Step 1: Test token-required endpoints**

Assert destructive endpoints reject missing/invalid tokens and accept the current session token.

- [x] **Step 2: Generate local session token**

Create a random token on server startup, expose it to served pages only, and require it for POST requests that run commands, save files, cancel jobs, or purge data.

- [x] **Step 3: Validate frame save paths**

Use `Path(frame_name).name` or the existing safe-name helper before writing frame files.

- [x] **Step 4: Add locked JSON writes**

Update shared JSON writes for jobs, experiments, and config to use atomic temporary files and Windows-safe replacement.

- [x] **Step 5: Verify**

Run:

```powershell
python -m pytest tests/test_api_auth.py tests/test_web_api.py -q
```

Expected: tests pass.

### Task 11: Status Performance and Startup Self-Test

**Covers:** Addition 10, Improvements 4 and 5

**Files:**
- Create: `app/services/startup_self_test_service.py`
- Modify: `app/services/model_service.py`
- Modify: `app/web_routes/routes_jobs.py`
- Modify: `app/web/components/setup.html`
- Modify: `app/web/js/app_status.js`
- Test: `tests/test_startup_self_test.py`

- [x] **Step 1: Test startup checks**

Assert the service reports Python, FFmpeg, Pillow, ComfyUI reachability, model presence, GPU summary, disk space, and writable output folders.

- [x] **Step 2: Add cached model and GPU status**

Cache expensive model and GPU checks with a short TTL and explicit invalidation after install/download actions.

- [x] **Step 3: Split heartbeat and full status**

Add lightweight `/api/heartbeat` for frequent polling and reserve full diagnostics for slower refreshes.

- [x] **Step 4: Add Setup diagnostics panel**

Show startup self-test results with direct actions for common failures.

- [x] **Step 5: Verify**

Run:

```powershell
python -m pytest tests/test_startup_self_test.py tests/test_web_api.py -q
node --check app\web\js\app_status.js
```

Expected: tests pass and JavaScript parses.

### Task 12: JSON Schema Validation

**Covers:** Improvement 15

**Files:**
- Create: `app/services/schema_validation_service.py`
- Create: `app/config/schemas/spriteforge_config.schema.json`
- Create: `app/config/schemas/project.schema.json`
- Create: `app/config/schemas/queue.schema.json`
- Create: `app/config/schemas/sheet.schema.json`
- Modify: `app/services/config_service.py`
- Modify: `app/services/project_service.py`
- Test: `tests/test_schema_validation.py`

- [x] **Step 1: Test schema validation**

Add valid and invalid examples for config, project, queue, and sheet metadata. Assert errors include the failing field path.

- [x] **Step 2: Add schemas**

Define required fields, accepted enum values, and safe defaults for each JSON document type.

- [x] **Step 3: Wire validation into load/import paths**

Validate config on startup, projects on import, queues before run, and sheet metadata before export.

- [x] **Step 4: Verify**

Run:

```powershell
python -m pytest tests/test_schema_validation.py tests/test_spriteforge_projects.py -q
```

Expected: tests pass.

---

## Phase 5: User Experience and Accessibility

### Task 13: Loading States, Error Recovery, and Toasts

**Covers:** Improvements 2 and 6

**Files:**
- Modify: `app/web/index.html`
- Modify: `app/web/js/app_main.js`
- Modify: `app/web/js/globals.js`
- Modify: `app/web/styles.css`
- Test: `tests/test_web_api.py`

- [x] **Step 1: Add component load failure state**

If a component fetch fails, render a visible retry panel inside that view.

- [x] **Step 2: Add fetch wrapper**

Create one shared wrapper for API calls that displays success, warning, or error toasts using the existing `#toast` element.

- [x] **Step 3: Add loading skeletons**

Show lightweight loading states when switching views or refreshing async data.

- [x] **Step 4: Verify**

Run:

```powershell
python -m pytest tests/test_web_api.py -q
node --check app\web\js\globals.js
node --check app\web\js\app_main.js
```

Expected: tests pass and JavaScript parses.

### Task 14: Accessibility and Mobile Polish

**Covers:** Improvements 3 and 18

**Files:**
- Modify: `app/web/css/accessibility.css`
- Modify: `app/web/mobile_nav.css`
- Modify: `app/web/styles.css`
- Modify: `app/web/index.html`
- Modify: `app/web/js/keyboard_shortcuts.js`

- [x] **Step 1: Replace color-only status**

Add text labels and icons for health, queue, QA, and job states. Preserve color as a secondary cue.

- [x] **Step 2: Improve keyboard navigation**

Add visible focus states and view navigation shortcuts. Ensure modal close buttons and destructive actions are reachable by keyboard.

- [x] **Step 3: Check mobile layouts**

Review rail, topbar, project strip, preview modal, and dense Quality Lab controls at narrow widths.

- [x] **Step 4: Verify**

Run:

```powershell
node --check app\web\js\keyboard_shortcuts.js
```

Expected: JavaScript parses. Manually inspect the UI at desktop and mobile widths before completion.

### Task 15: Guided Generate Form

**Covers:** Improvement 1

**Files:**
- Modify: `app/web/components/generate.html`
- Modify: `app/web/js/app_forms.js`
- Modify: `app/web/js/prompt_builder.js`
- Modify: `app/web/styles.css`

- [x] **Step 1: Reorder controls**

Put presets, archetype, action, direction, reference image, and prompt first. Move expert model/profile/seed controls into a collapsible section.

- [x] **Step 2: Add inline explanations**

Use compact helper text for model/profile tradeoffs and warnings. Do not add a marketing-style hero or tutorial page.

- [x] **Step 3: Preserve existing submit contract**

Confirm the request payload sent by Generate Sprite still matches current backend expectations.

- [x] **Step 4: Verify**

Run:

```powershell
node --check app\web\js\app_forms.js
node --check app\web\js\prompt_builder.js
```

Expected: JavaScript parses.

---

## Phase 6: Extensibility and Operations

### Task 16: Plugin Manager UI

**Covers:** Addition 8

**Files:**
- Modify: `app/services/plugin_manager.py`
- Modify: `app/web_routes/routes_misc.py`
- Modify: `app/web/components/setup.html`
- Modify: `app/web/js/marketplace_gallery.js`
- Modify: `app/docs/PLUGIN_GUIDE.md`
- Test: `tests/test_marketplace.py`

- [x] **Step 1: Test plugin discovery**

Assert plugins are discovered with name, file path, hooks, enabled status, and validation errors.

- [x] **Step 2: Add enable/disable persistence**

Store enabled plugin names in config and skip disabled hooks at runtime.

- [x] **Step 3: Add Setup UI panel**

List plugins, show hooks, validation status, and enable/disable controls.

- [x] **Step 4: Update plugin docs**

Document hook names, safety rules, expected return values, and the manager UI.

- [x] **Step 5: Verify**

Run:

```powershell
python -m pytest tests/test_marketplace.py -q
```

Expected: tests pass.

### Task 17: Notifications and Capped Notification Storage

**Covers:** Addition 9, frontend notification improvement

**Files:**
- Modify: `app/services/notification_service.py`
- Modify: `app/services/job_service.py`
- Modify: `app/web/js/app_notifications.js`
- Modify: `app/web/index.html`
- Test: `tests/test_spriteforge_jobs.py`

- [x] **Step 1: Test job notification events**

Assert generation success, failure, cancellation, and queue completion emit notification events.

- [x] **Step 2: Add delivery providers**

Support local drawer notification, optional webhook URL, and optional desktop notification where the browser allows it.

- [x] **Step 3: Cap stored frontend notifications**

Keep the newest 100 notifications and expire entries older than the configured retention window.

- [x] **Step 4: Verify**

Run:

```powershell
python -m pytest tests/test_spriteforge_jobs.py -q
node --check app\web\js\app_notifications.js
```

Expected: tests pass and JavaScript parses.

### Task 18: Frontend Namespace Cleanup

**Covers:** Improvement 19

**Files:**
- Modify: `app/web/js/app_status.js`
- Modify: `app/web/js/app_dashboard.js`
- Modify: `app/web/js/app_main.js`
- Modify: `app/web/index.html`

- [x] **Step 1: Identify duplicate globals**

Search for duplicated global function names and implicit load-order dependencies.

Run:

```powershell
rg "function updateHealthBar|window\\.|const .* =" app\web\js
```

- [x] **Step 2: Namespace shared app functions**

Move shared frontend functions onto a single `window.SpriteForge` namespace while preserving current script loading.

- [x] **Step 3: Remove duplicate health update names**

Rename duplicate health renderers to distinct names and update call sites.

- [x] **Step 4: Verify**

Run:

```powershell
Get-ChildItem app\web\js\*.js | ForEach-Object { node --check $_.FullName }
```

Expected: every JavaScript file parses.

---

## Phase 7: Ease-of-Use Fast Track

### Task 19: One-Click Sample Project and First-Sprite Wizard

**Covers:** Ease-of-use 1, 2, 10, and 15

**Files:**
- Create: `app/services/onboarding_service.py`
- Modify: `app/services/project_service.py`
- Modify: `app/config/character_archetypes.json`
- Modify: `app/web_routes/routes_onboarding.py`
- Modify: `app/web/components/guide.html`
- Modify: `app/web/components/launchpad.html`
- Modify: `app/web/components/generate.html`
- Modify: `app/web/js/app_guide.js`
- Modify: `app/web/js/app_forms.js`
- Modify: `app/docs/END_USER_GUIDE.md`
- Test: `tests/test_onboarding.py`

- [x] **Step 1: Test sample project creation**

Add a test that calls the onboarding service, creates a sample project in a temporary workspace, and asserts it contains a known-good sprite output, `spriteforge_project.json`, `sheet.json`, a QA report, and a release manifest.

Run:

```powershell
python -m pytest tests/test_onboarding.py::test_create_sample_project_contains_known_good_assets -q
```

Expected before implementation: FAIL because `app.services.onboarding_service` does not exist.

- [x] **Step 2: Implement `create_sample_project()`**

Create a service function that copies the existing demo sprite from `app/examples/prebuilt_demo_sprite` into a new project named `SampleProject`, writes project metadata, and returns a response shaped like:

```json
{
  "project": "SampleProject",
  "sprite_dir": "projects/SampleProject/sprites/prebuilt_demo_sprite",
  "next_view": "quality",
  "next_action": "Review the sample sprite in Quality Lab"
}
```

- [x] **Step 3: Test first-sprite wizard payload**

Add a test that submits beginner-mode wizard inputs such as archetype, action, direction, and color notes, then asserts the generated request uses safe defaults and hides expert-only fields unless explicitly requested.

- [x] **Step 4: Implement wizard orchestration**

Add a `build_first_sprite_request()` helper that resolves archetype defaults, hardware-safe model/profile choices, prompt text, action, direction, and project naming. The function must return the same payload shape already accepted by the existing Generate Sprite flow.

- [x] **Step 5: Add Guide and Launchpad entry points**

Add two primary actions: “Open sample project” and “Make my first sprite.” The first action opens the sample project and navigates to Quality Lab. The second opens the guided Generate Sprite state.

- [x] **Step 6: Add beginner, production, and expert mode behavior**

In Simple mode, show only archetype, action, direction, style, reference image, and generate. In Detailed mode, show QA and export choices. In Expert mode, show model, profile, seed, and advanced prompt controls.

- [x] **Step 7: Add inline mini-help**

Add short inline explanations for seed, profile, model tier, chroma key, deflicker, loop seam, and foot drift. Keep the explanations beside the controls they clarify.

- [x] **Step 8: Verify**

Run:

```powershell
python -m pytest tests/test_onboarding.py tests/test_spriteforge_projects.py -q
node --check app\web\js\app_guide.js
node --check app\web\js\app_forms.js
```

Expected: tests pass and JavaScript parses.

### Task 20: Smart Defaults and Plain-English Failure Recovery

**Covers:** Ease-of-use 3, 4, and 12

**Files:**
- Create: `app/services/failure_explainer_service.py`
- Modify: `app/services/advisor_service.py`
- Modify: `app/services/oom_recovery_service.py`
- Modify: `app/services/generation_intelligence.py`
- Modify: `app/services/job_service.py`
- Modify: `app/web/components/launchpad.html`
- Modify: `app/web/components/queues.html`
- Modify: `app/web/js/app_jobs.js`
- Modify: `app/web/js/app_status.js`
- Test: `tests/test_failure_explainer.py`
- Test: `tests/test_generation_intelligence.py`

- [x] **Step 1: Test smart default selection**

Add tests for GPU present, GPU missing, low disk, ComfyUI unreachable, model missing, and RTX 3060 12GB-style hardware. Assert the advisor returns model tier, profile, frame count, resolution, and a short reason.

- [x] **Step 2: Implement smart default advisor**

Extend `advisor_service.py` so the Generate Sprite form can ask for the safest available defaults based on hardware, models, disk, and ComfyUI state.

- [x] **Step 3: Test failure explanations**

Add tests that map common stderr/log fragments to structured explanations for CUDA OOM, missing model, FFmpeg failure, ComfyUI unreachable, bad path, permission denied, and malformed workflow JSON.

- [x] **Step 4: Implement failure explainer**

Return failure records shaped like:

```json
{
  "code": "cuda_oom",
  "title": "The GPU ran out of memory",
  "what_happened": "The selected model or resolution needs more VRAM than this system has available.",
  "fix": "Retry with a smaller profile or fewer frames.",
  "action": {"label": "Retry safely", "kind": "retry_with_safer_profile"}
}
```

- [x] **Step 5: Add quick safe repair action**

Create one “Fix all safe issues” action that runs only non-destructive cleanup steps: clean background, stabilize feet, reduce flicker, rebuild preview, and rerun QA. Require confirmation before any frame deletion or overwrite.

- [x] **Step 6: Surface recovery actions in the UI**

Show plain-English error cards in Queue Monitor, Result Preview, and Launchpad. Include direct actions such as “Launch ComfyUI,” “Install missing model,” “Retry safely,” and “Open output folder.”

- [x] **Step 7: Verify**

Run:

```powershell
python -m pytest tests/test_failure_explainer.py tests/test_generation_intelligence.py tests/test_spriteforge_jobs.py -q
node --check app\web\js\app_jobs.js
node --check app\web\js\app_status.js
```

Expected: tests pass and JavaScript parses.

### Task 21: Resume State, Better Empty States, Output Explainer, and Naming Assistant

**Covers:** Ease-of-use 5, 8, 11, and 14

**Files:**
- Modify: `app/services/project_service.py`
- Modify: `app/services/job_service.py`
- Modify: `app/services/web_helpers_listings.py`
- Modify: `app/services/open_path_service.py`
- Modify: `app/web_routes/routes_onboarding.py`
- Modify: `app/web/components/dashboard.html`
- Modify: `app/web/components/launchpad.html`
- Modify: `app/web/components/history.html`
- Modify: `app/web/js/app_dashboard.js`
- Modify: `app/web/js/app_listings.js`
- Test: `tests/test_onboarding.py`
- Test: `tests/test_spriteforge_jobs.py`

- [x] **Step 1: Test resume state**

Add tests that create a project, an unfinished job, and a latest sprite output, then assert the resume endpoint returns last project, current job, latest sprite, and recommended next action.

- [x] **Step 2: Implement resume summary**

Add a backend summary that reads current project state, active job state, recent outputs, and QA results. Return a compact response for Dashboard and Launchpad.

- [x] **Step 3: Add output folder explainer**

For a selected sprite output, return a labeled list of source video, processed frames, sprite sheet, metadata, QA report, engine exports, and release ZIP when present.

- [x] **Step 4: Implement naming assistant**

Add a deterministic naming helper that builds output names from project, character, action, direction, seed, and version. Example: `hero_walk_right_seed123_v003`.

- [x] **Step 5: Improve empty states**

Replace blank panels with contextual actions. Examples: Generate Sprite offers “Make my first sprite,” Quality Lab offers “Open sample project,” Release offers “Build release from latest passed sprite,” and Queue Monitor offers “Create a character pack queue.”

- [x] **Step 6: Verify**

Run:

```powershell
python -m pytest tests/test_onboarding.py tests/test_spriteforge_jobs.py tests/test_web_api.py -q
node --check app\web\js\app_dashboard.js
node --check app\web\js\app_listings.js
```

Expected: tests pass and JavaScript parses.

### Task 22: Global Command Palette

**Covers:** Ease-of-use 6

**Files:**
- Create: `app/services/action_command_service.py`
- Modify: `app/web_routes/routes_onboarding.py`
- Modify: `app/web/index.html`
- Create: `app/web/js/command_palette.js`
- Modify: `app/web/js/keyboard_shortcuts.js`
- Modify: `app/web/styles.css`
- Test: `tests/test_action_command_service.py`

- [x] **Step 1: Test command discovery**

Add tests that assert the command service returns actions for run QA, open latest output, build release, install model, retry failed jobs, create sample project, generate first sprite, and open docs.

- [x] **Step 2: Implement command service**

Each command record should include `id`, `label`, `description`, `view`, `enabled`, `disabled_reason`, and an execution descriptor that maps to an existing route or frontend action.

- [x] **Step 3: Add command API**

Add endpoints to list commands and execute safe commands. Destructive commands must return a confirmation requirement before executing.

- [x] **Step 4: Add `Ctrl+K` UI**

Create a searchable overlay with keyboard selection, mouse selection, disabled states, and visible shortcut hints. Add the script to `app/web/index.html`.

- [x] **Step 5: Verify**

Run:

```powershell
python -m pytest tests/test_action_command_service.py tests/test_web_api.py -q
node --check app\web\js\command_palette.js
node --check app\web\js\keyboard_shortcuts.js
```

Expected: tests pass and JavaScript parses.

### Task 23: Universal Undo for Destructive Actions

**Covers:** Ease-of-use 7

**Files:**
- Modify: `app/services/sprite_sheet_service.py`
- Modify: `app/services/project_service.py`
- Modify: `app/services/job_service.py`
- Modify: `app/web_routes/routes_sprites.py`
- Modify: `app/web_routes/routes_projects.py`
- Modify: `app/web/components/quality.html`
- Modify: `app/web/js/editor_history.js`
- Modify: `app/web/js/frame_review.js`
- Test: `tests/test_editor_history.py`

- [x] **Step 1: Test undo snapshots**

Add tests for delete frame, reject result, overwrite sheet, remove project asset, and cleanup purge. Assert each action creates a restorable snapshot before it changes files.

- [x] **Step 2: Implement undo snapshot manifest**

Before destructive actions, copy affected files into a hidden project undo folder and write a manifest with action, timestamp, affected paths, and restore instructions.

- [x] **Step 3: Add restore endpoint**

Add an endpoint that restores the most recent compatible snapshot and returns the restored file list.

- [x] **Step 4: Add undo UI**

After destructive actions, show a toast with an Undo button. Add an undo history panel in Quality Lab for frame and sheet edits.

- [x] **Step 5: Verify**

Run:

```powershell
python -m pytest tests/test_editor_history.py tests/test_spriteforge_projects.py -q
node --check app\web\js\editor_history.js
node --check app\web\js\frame_review.js
```

Expected: tests pass and JavaScript parses.

### Task 24: Drag-and-Drop Everywhere and Export Recipes

**Covers:** Ease-of-use 9 and 13

**Files:**
- Modify: `app/services/project_service.py`
- Modify: `app/services/export_service.py`
- Modify: `app/services/godot_export_service.py`
- Modify: `app/services/unity_export_service.py`
- Modify: `app/services/unreal_export_service.py`
- Modify: `app/web_routes/routes_onboarding.py`
- Modify: `app/web/components/release.html`
- Modify: `app/web/components/convert.html`
- Modify: `app/web/components/generate.html`
- Modify: `app/web/js/drag_drop.js`
- Modify: `app/web/js/app_forms.js`
- Modify: `app/docs/END_USER_GUIDE.md`
- Test: `tests/test_spriteforge_projects.py`
- Test: `tests/test_unreal_export.py`

- [x] **Step 1: Test dropped file classification**

Add tests that classify dropped `.mp4`, `.webm`, `.png`, sprite output folders, `.spriteforge` bundles, and release folders into import actions.

- [x] **Step 2: Implement drop handling backend**

Add a route that accepts dropped file metadata, validates paths, and returns the target action: convert video, attach reference image, import project bundle, open sprite output, or inspect release package.

- [x] **Step 3: Add global drop zones**

Make Generate Sprite accept reference images, Convert Video accept videos, Projects accept `.spriteforge` bundles, and Quality Lab accept sprite output folders.

- [x] **Step 4: Add export recipes**

Create release presets for Godot 4 character animation, Unity Animator, Unreal Paper2D, Aseprite handoff, web-game APNG, and web-game WebP. Each recipe should show only relevant export options.

- [x] **Step 5: Verify**

Run:

```powershell
python -m pytest tests/test_spriteforge_projects.py tests/test_unreal_export.py tests/test_pack_formats.py -q
node --check app\web\js\drag_drop.js
node --check app\web\js\app_forms.js
```

Expected: tests pass and JavaScript parses.

---

## Priority Order

### Start With Ease-of-Use Foundation

1. One-click sample project and first-sprite wizard.
2. Smart defaults and plain-English failure recovery.
3. Resume state, better empty states, output explainer, and naming assistant.
4. Global command palette.
5. Drag-and-drop everywhere and export recipes.

### Do First

1. Interactive animation preview.
2. Frame timeline editor.
3. Prompt linting and prompt history.
4. Status performance and startup self-test.
5. Loading states, error recovery, and toasts.

### Do Next

1. Side-by-side diff player and N-way compare.
2. Reference style lock and palette handoff.
3. Queue retry and failure grouping.
4. Animated APNG/WebP export.
5. API token protection and safer file writes.

### Plan After Core Workflow Stabilizes

1. Character pack wizard.
2. Seed reuse and best-seed persistence.
3. JSON schema validation.
4. Plugin manager UI.
5. Notifications and capped notification storage.

### Polish After Feature Completion

1. Accessibility and mobile polish.
2. Guided Generate form.
3. Frontend namespace cleanup.
4. Universal undo for destructive actions if it was not pulled forward during frame editing.

---

## Coverage Matrix

| Recommendation | Implemented By |
| --- | --- |
| Addition 1: interactive animation preview | Task 1 |
| Addition 2: prompt linting/scoring | Task 4 |
| Addition 3: reference style lock | Task 5 |
| Addition 4: frame timeline editor | Task 2 |
| Addition 5: side-by-side diff player | Task 3 |
| Addition 6: character pack wizard | Task 7 |
| Addition 7: animated APNG/WebP export | Task 8 |
| Addition 8: plugin manager | Task 16 |
| Addition 9: notification hooks | Task 17 |
| Addition 10: startup self-test | Task 11 |
| Improvement 1: guided Generate form | Task 15 |
| Improvement 2: loading/error states | Task 13 |
| Improvement 3: accessible statuses | Task 14 |
| Improvement 4: cache expensive status checks | Task 11 |
| Improvement 5: heartbeat/full diagnostics split | Task 11 |
| Improvement 6: global API error toasts | Task 13 |
| Improvement 7: Quality Lab before/after repair review | Task 2 |
| Improvement 8: configurable QA weights | Task 5 and follow-up in `qa_threshold_service.py` |
| Improvement 9: persist chroma/palette cleanup decisions | Task 5 |
| Improvement 10: better deflicker/stabilization defaults | Task 2 |
| Improvement 11: seed history/reuse | Task 6 |
| Improvement 12: N-way A/B comparison | Task 3 |
| Improvement 13: prompt favorites/history | Task 4 |
| Improvement 14: versioned project bundles | Task 12 and follow-up in `project_service.py` |
| Improvement 15: JSON schema validation | Task 12 |
| Improvement 16: safer state storage | Task 10 |
| Improvement 17: retry failed queue jobs | Task 9 |
| Improvement 18: mobile/tablet polish | Task 14 |
| Improvement 19: frontend organization | Task 18 |
| Improvement 20: local API token protection | Task 10 |
| Ease-of-use 1: one-click sample project | Task 19 |
| Ease-of-use 2: first-sprite wizard | Task 19 |
| Ease-of-use 3: smart default selector | Task 20 |
| Ease-of-use 4: plain-English failure explanations | Task 20 |
| Ease-of-use 5: resume where I left off | Task 21 |
| Ease-of-use 6: global command/search box | Task 22 |
| Ease-of-use 7: universal undo for destructive actions | Task 23 |
| Ease-of-use 8: better empty states | Task 21 |
| Ease-of-use 9: drag-and-drop everywhere | Task 24 |
| Ease-of-use 10: beginner/production/expert modes | Task 19 |
| Ease-of-use 11: output folder explainer | Task 21 |
| Ease-of-use 12: quick fix all safe issues | Task 20 |
| Ease-of-use 13: export recipes | Task 24 |
| Ease-of-use 14: naming assistant | Task 21 |
| Ease-of-use 15: inline mini-help on advanced controls | Task 19 |

---

## Verification Before Completion

- [x] Run focused tests for the task being implemented.
- [x] Run affected API smoke tests: `python -m pytest tests/test_web_api.py -q`
- [x] Run affected JavaScript syntax checks with `node --check`.
- [x] Inspect `git diff` and confirm unrelated files were not modified.
- [x] Update docs when behavior, setup, or user-facing workflow changes.
- [x] Commit each completed task separately with a message like `feat: add sprite animation preview` or `fix: cache status diagnostics`.

## Execution Recommendation

Use subagent-driven development for this roadmap. Dispatch one fresh agent per task, review the diff, run the focused verification, then continue to the next task. This keeps each feature slice small enough to understand and avoids turning the roadmap into one sprawling branch.
