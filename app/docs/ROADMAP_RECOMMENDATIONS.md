# SpriteForge Studio Roadmap & Extended Recommendations

Current status note: this document is retained as a planning archive. Many items have since shipped in v12, including API session-token protection, prompt linting, palette workflows, onboarding, command palette, notifications, startup diagnostics, schema validation, queue retry, plugin manager UI, and frontend polish. Use `FINAL_POLISH_v12.md` and `END_USER_GUIDE.md` for the current product state.

This document combines the two recommendation notes provided for SpriteForge Studio:

- **SpriteForge Studio - 10 Additions & 20 Improvements**
- **SpriteForge Studio - Extended Recommendations**

---

# SpriteForge Studio - 10 Additions & 20 Improvements

After a deep read of the full codebase (~60+ modules, 62 services, 23 test files, dual GUI/web frontends), here are concrete, actionable recommendations.

## 10 Feature Additions

### 1. Live In-Browser Animation Preview with Speed/Scale Controls

**What:** Add a real-time sprite animation player directly in the web UI (and optionally Tkinter) that loads `sheet.json` and plays the animation on a configurable background at adjustable speed and zoom. Currently you output `preview.gif` and static contact sheets, but there's no interactive "see it in-game" preview.

**Why:** Game devs need to evaluate animation timing, loop seam, and ground contact interactively, not from a static GIF. This is the single most requested feature in any sprite tool.

**Where:** New web component `animation_player.html` plus JS module. Feed it `sheet.json` metadata.

### 2. AI-Assisted Prompt Refinement / Prompt Scoring

**What:** Before submitting to WAN, run the positive prompt through a lightweight text analysis that scores it for sprite-quality heuristics, such as missing "locked camera", contradictory terms like "dynamic camera" plus "locked camera", prompt length warnings, and chroma key presence.

**Why:** `spriteforge_prompts.py` builds excellent templates, but users frequently override with custom prompts that break generation. A score/lint before submission would prevent many bad outputs.

**Where:** New `services/prompt_linter_service.py`, integrated into the Generate Sprite web view and the `submit-wan` CLI path.

### 3. Multi-Character Scene Compositor

**What:** Go beyond the existing `scene_compositor_service.py` stub to support placing multiple animated sprites on a grid/canvas with Z-ordering, background tiles, and camera viewports, exporting a composite preview GIF or engine scene file.

**Why:** The current compositor is minimal. Game devs want to see how their idle/walk/attack sprites look together in a mock game scene before importing into Godot/Unity.

**Where:** Extend `scene_compositor_service.py` plus new web component `scene_preview.html`.

### 4. Sprite Diffing / Version Comparison Side-by-Side Player

**What:** Build on `spriteforge_compare.py` to add a synchronized side-by-side animation player in the web UI. Show two sprite outputs frame-by-frame with a diff overlay, alpha difference heatmap, and QA score comparison.

**Why:** When iterating across different seeds, prompts, and models, users need to visually compare runs, not just look at numbers. The compare module exists but has no interactive frontend.

**Where:** New web component `compare_player.html`, integrated with the existing A/B Runs view.

### 5. Sprite Palette Extraction + Palette-Locked Generation

**What:** Extract the dominant N-color palette from a reference sprite/image and inject those exact colors as a constraint for future generations. The `palette_harmonizer_service.py` exists but doesn't bridge to generation. Add a "lock palette" workflow where post-processing quantizes output frames to the locked palette.

**Why:** Color consistency across a character pack is a major production pain point. The harmonizer service is there but disconnected from the generation and post-processing pipeline.

**Where:** Connect `palette_harmonizer_service.py` to `sprite_processing_pipeline.py`; the palette arg already exists but is not wired from the UI.

### 6. Sprite NPC/Enemy Template Library

**What:** Ship a curated library of 20-30 pre-built prompt templates for common game archetypes, such as skeleton, slime, goblin, dragon, and shopkeeper, with recommended actions, poses, and style tokens. Users pick an archetype, customize colors/weapons, and generate a full pack.

**Why:** Currently `ACTION_TEMPLATES` in `spriteforge_prompts.py` covers actions well, but there's no concept of character archetypes. New users don't know what prompt to write.

**Where:** New `config/character_archetypes.json` and expose it in the Pose Library / Generate views.

### 7. Webhook / Notification System for Long Generations

**What:** When a `generate-sprite` job finishes or fails, fire a configurable webhook such as Discord, Slack, email, or system notification. Currently users must watch the log or poll the queue.

**Why:** WAN generation can take 5-30 minutes depending on profile. Users walk away. `job_service.py` tracks status but has no notification hooks.

**Where:** New `services/notification_service.py` with configurable hooks in `spriteforge_config.json`.

### 8. GIF/APNG/WebP Animated Export

**What:** Beyond `preview.gif`, add proper animated PNG (APNG) and animated WebP export with correct frame timing from `sheet.json`. These are lossless and widely used in web games.

**Why:** The current pipeline outputs a low-quality preview GIF and a static sheet. Many web game engines and social platforms need animated WebP/APNG.

**Where:** Extend `sprite_sheet_service.py` with `export_apng()` and `export_webp_anim()`.

### 9. Interactive Frame Editor

**What:** In the web UI, show the extracted frames as a draggable timeline. Users can delete bad frames, reorder them, adjust per-frame duration, and re-pack the sheet without re-generating.

**Why:** WAN output frequently has a few junk frames: duplicates, glitches, or partial morphs. Currently users must run `autofix-sprite --drop-loop-duplicate` blindly.

**Where:** New web component `frame_editor.html` plus `/api/repack-sheet` endpoint.

### 10. CI/CD Integration & Headless Batch Runner

**What:** Add a formal `spriteforge ci-check` command that runs all QA checks on a directory of sprite outputs and exits non-zero if any fail below a threshold. Support JUnit XML output for CI dashboards.

**Why:** The `quality-batch` command exists but doesn't emit machine-readable CI output. Game studios with automated build pipelines can't gate sprite quality without it.

**Where:** New `--junit-xml` flag on `quality-batch` plus new `ci-check` CLI subcommand.

## 20 Improvements

### Architecture & Code Quality

1. **Eliminate duplicated CLI argument blocks**  
   WAN arguments are copy-pasted across `spriteforge_commands.py` and `spriteforge_unified_parser.py`. Extract and reuse `add_wan_args(parser)`.

2. **Replace shell-delegating lambda handlers with direct service calls**  
   Many commands spawn subprocesses for Python code that could be called directly. Import and call service functions instead.

3. **Centralize `ROOT`, `load_config()`, and `load_json()` definitions**  
   Use `spriteforge_utils.py` as the single source of truth.

4. **Add type-safe config dataclass everywhere**  
   Move the `Config` dataclass to a shared module such as `config_model.py` and use it across the app.

5. **Test coverage for critical paths**  
   Add parameterized tests for `process_common()`, `normalize_frames()`, `apply_chroma_key()`, and QA scoring with synthetic images.

### Generation Pipeline

6. **Automatic OOM retry with profile downgrade**  
   Wire `oom_recovery_service.py` and `safer_retry_payload()` directly into `generate-sprite`.

7. **Progress bar / ETA in the CLI**  
   Surface `generation_intelligence.py` ETA and ComfyUI progress in CLI output.

8. **Seed persistence across character pack**  
   After QA pass, write winning seeds back to `pack_manifest.json`. Add `--reuse-best-seeds` to `batch-plan`.

### Quality & Post-Processing

9. **QA score formula should be configurable**  
   Move hardcoded QA weights to `spriteforge_config.json` under `qa_weights` presets.

10. **Auto-detect chroma key color with feedback**  
   Persist `detected_key_color` to `sheet.json` and show it in QA reports.

11. **Deflicker should be more aggressive by default**  
   Add a light temporal smoothing pass as a default pipeline step, configurable via `sprite_defaults.deflicker`.

12. **Power-of-two sheet padding should preserve metadata**  
   Add `padded_to_pot` and `original_size` to `sheet.json`.

### UI / UX

13. **Web UI needs a consistent error toast system**  
   Catch fetch/API errors and display them to users.

14. **Easy Mode Tkinter GUI needs generation progress**  
   Parse progress log lines and update a `ttk.Progressbar`.

15. **Tkinter Studio GUI has duplicate "Build atlas" buttons**  
   Remove the duplicate or make the buttons contextually distinct.

16. **Web UI CSS is split across many files**  
   Consolidate or bundle smaller CSS files to reduce first-load cost and style conflicts.

### Configuration & DevOps

17. **Config file uses mixed line endings**  
   Normalize to LF and add `.editorconfig` or `.gitattributes`.

18. **No JSON Schema validation for config files**  
   Add schemas for config, presets, pack manifests, and project files.

19. **Plugin system is vestigial**  
   Document plugin APIs, add more examples, and expose plugin management in Setup.

20. **`save_json()` has a race condition on Windows**  
   Add file locking for shared JSON writes such as experiment history, job state, and config.

## Priority Matrix

| Priority | Additions | Improvements |
| --- | --- | --- |
| Do First | #1 Animation Preview, #5 Palette Lock, #8 APNG/WebP Export | #1 Deduplicate CLI args, #3 Centralize ROOT, #15 Duplicate button, #17 Line endings |
| Do Next | #2 Prompt Linter, #9 Frame Editor, #10 CI Integration | #6 Auto OOM retry, #7 CLI progress, #9 Configurable QA, #13 Error toasts |
| Plan Later | #3 Scene Compositor, #4 Diff Player, #6 Archetype Library | #2 Direct service calls, #4 Type-safe config, #5 Test coverage, #19 Plugin docs |
| Nice to Have | #7 Webhooks | #8 Seed persistence, #10-12, #14, #16, #18, #20 |

---

# SpriteForge Studio - Extended Recommendations

Beyond the initial 10 additions and 20 improvements, these are deeper findings from the web routes, JS frontend, job service, ComfyUI integration, and test infrastructure.

## Security & Safety

### 1. API Routes Have No Authentication or CSRF Protection

**Severity:** High  
**Where:** All routes in `routes_jobs.py`, `routes_misc.py`, and `routes_sprites.py`

The Flask API has no authentication. Any process on the machine, or on the network if `--listen 0.0.0.0` is used, can POST to `/api/run`, `/api/cleanup/purge`, or `/api/open`.

**Fix:** Add a session token or shared secret header for API calls. For network-exposed mode, add API key auth or origin checking.

### 2. Path Traversal Risk in `/api/sprite/frame/save`

**Severity:** Medium  
**Where:** `routes_sprites.py`

The `frame_name` parameter is directly used to write a file. A crafted name could overwrite unintended files.

**Fix:** Validate `frame_name` with `safe_name()` or `Path(frame_name).name`.

### 3. SSE `/api/status/stream` Uses Infinite Blocking Loops

**Severity:** Medium  
**Where:** `routes_jobs.py`

The status stream loops forever and sleeps without clear connection-close handling.

**Fix:** Detect disconnects, add cleanup, or migrate to WebSocket for real-time updates.

## Performance

### 4. `refreshAll()` Polls `/api/status` Every 3 Seconds with a Full Payload

The endpoint returns model summary, GPU info, disk checks, sprite outputs, cleanup suggestions, project workspace, and current job. This can also trigger `nvidia-smi` frequently.

**Fix:** Split into a lightweight `/api/heartbeat` and heavier `/api/full-status`, with caching.

### 5. Duplicate `updateHealthBar` Function Across Two Files

**Where:** `app_dashboard.js` and `app_status.js`

Two functions with the same global name can overwrite one another depending on script order.

**Fix:** Rename them to distinct names such as `updateHealthDots` and `updateHealthPercentBar`.

### 6. `ModelService.get_summary()` Is Called Too Often

Model file presence checks hit the filesystem repeatedly.

**Fix:** Cache model scan results with a TTL and invalidate on install/download.

### 7. Duplicate `ModelService` Import in `routes_jobs.py`

Remove the duplicated import.

## Architecture & API Design

### 8. Job Service Is a Singleton with Class-Level State

`JobService._active_job` and `_current_proc` are class-level mutable state, and retries spawn recursive worker threads.

**Fix:** Extract a `JobRunner` class with explicit state transitions and a queue-based retry flow.

### 9. `build_action_command()` Should Validate Action Names

Invalid actions can construct bad commands and fail cryptically.

**Fix:** Whitelist valid action names.

### 10. No Request Rate Limiting on Destructive Endpoints

Endpoints such as `/api/cleanup/purge`, `/api/run`, and `/api/cancel` can be spammed.

**Fix:** Add in-memory or Flask-Limiter rate limiting.

## Frontend Architecture

### 11. Many JavaScript Files Loaded Without Bundling or a Module System

The UI uses many global scripts with implicit load-order dependencies.

**Fix:** Migrate to ES modules or add a simple bundling/concatenation step. If staying script-based, namespace globals.

### 12. No Loading/Skeleton States for Async Views

Some views show stale data until the next refresh.

**Fix:** Show a skeleton/spinner immediately on view switches.

### 13. Notification System Stores Everything in `localStorage`

Notifications can accumulate indefinitely.

**Fix:** Cap stored notifications and expire old entries.

### 14. View Component Loading Has No Error Recovery

Failed component fetches leave views empty.

**Fix:** Insert a visible "Failed to load - Click to retry" message.

## Accessibility

### 15. Web UI Has No Keyboard Navigation Between Views

Add `Alt+1` through `Alt+9`, better tab navigation, and visible sidebar focus indicators.

### 16. Color-Only Status Indicators

Health dots, progress bars, and badges rely on color alone.

**Fix:** Add icons and text alternatives, and verify WCAG AA contrast.

## Developer Experience & DevOps

### 17. No Root Dependency Manifest

There is no root `requirements.txt` or `pyproject.toml`.

**Fix:** Add dependency metadata for Flask, Pillow, websocket-client, numpy, and related packages.

### 18. Many Silent `except Exception: pass` Blocks

Errors are swallowed across services.

**Fix:** Add logging to broad exception handlers, especially around file writes and API calls.

### 19. No Shared Test Fixtures

Tests lack a shared `conftest.py`.

**Fix:** Add fixtures for temp output directories, sample `sheet.json`, synthetic frames, mock ComfyUI, and clean experiment history.

### 20. No `.editorconfig` or Linting Configuration

Add `.editorconfig` and a linter config such as Ruff or Flake8.

## Documentation

### 21. No API Documentation or OpenAPI Spec

The web UI has many API endpoints but no endpoint reference.

**Fix:** Add OpenAPI or a `docs/api.md`.

### 22. Guided Setup Should Explain Why Each Step Matters

Add a conceptual overview of the pipeline: text to WAN video, frame extraction, chroma key, sheet packing, and QA.

## Data Architecture

### 23. Experiment History and Job History Use Flat JSON Files

Both services rewrite JSON arrays repeatedly.

**Fix:** Move structured job and experiment data to SQLite, while keeping JSON export optional.

### 24. Job Logs Are Stored In-Memory and on Disk Without Pruning

Disk log files can grow without bound.

**Fix:** Add log rotation or cap disk log files with cleanup support.

## Workflow Automation

### 25. No Batch Retry for Failed Queue Jobs

**Fix:** Add `/api/queues/retry_failed` and a "Retry All Failed" button.

### 26. A/B Runs Cannot Compare More Than Two Variants

**Fix:** Add an N-way comparison grid with synchronized playback.

### 27. No Favorite Prompts or Prompt History

**Fix:** Add autocomplete from experiment history and a "Pin Prompt" feature.

## Operational Excellence

### 28. ComfyUI Health Check Shells Out to `nvidia-smi` on Every Status Poll

**Fix:** Cache GPU info for 30-60 seconds.

### 29. WebSocket Bridge to ComfyUI Has No Reconnection Logic

**Fix:** Add exponential backoff reconnects, capped at a few retries.

### 30. No Startup Self-Test / Smoke Check

**Fix:** Add startup diagnostics for config loading, output writability, PIL availability, ComfyUI reachability, and model presence.

## Extended Priority Matrix

| Priority | Items |
| --- | --- |
| Urgent | #1 API Auth, #2 Path Traversal, #3 SSE Thread Leak |
| High Impact | #4 Polling Optimization, #6 Model Cache, #8 Job Runner Refactor, #23 SQLite Migration, #28 GPU Cache, #29 WS Reconnect |
| Important | #5 Duplicate Function, #7 Duplicate Import, #9 Action Whitelist, #17 Requirements File, #18 Silent Exceptions, #19 Test Fixtures, #30 Startup Check |
| Valuable | #11 JS Modules, #12 Loading States, #14 View Error Recovery, #15 Keyboard Nav, #25 Batch Retry, #27 Prompt History |
| Nice to Have | #10 Rate Limiting, #13 Notification Cap, #16 A11y Colors, #20 Linting, #21 API Docs, #22 Guide Content, #24 Log Pruning, #26 N-Way Compare |
