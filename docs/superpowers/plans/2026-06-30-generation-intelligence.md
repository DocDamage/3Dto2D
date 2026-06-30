# Generation Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exact ComfyUI progress, generation review, QA gates, visual reports, ETA, preflight warnings, safer retry, model explainers, reference flow support, and cleanup suggestions.

**Architecture:** Keep the work in existing SpriteForge service boundaries. Add one backend generation-intelligence helper module, wire it into `JobService` and `spriteforge_web.py`, and render the new metadata in the existing generation form, task center, cleanup manager, and result preview modal.

**Tech Stack:** Python stdlib services, optional `websocket-client` for ComfyUI `/ws`, Pillow for contact sheets, existing vanilla JS UI.

---

### Task 1: Backend Contract Tests

**Files:**
- Create: `tests/test_generation_intelligence.py`

- [x] **Step 1: Write failing tests**

Covered websocket event application, ETA bucketing, QA gate summaries, contact-sheet report creation, star/reject/rerun review decisions, preflight and safer retry advice, model explainers, and cleanup suggestions.

- [x] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests\test_generation_intelligence.py -q`

Expected: FAIL with missing `services.generation_intelligence`.

### Task 2: Generation Intelligence Service

**Files:**
- Create: `app/services/generation_intelligence.py`
- Modify: `app/requirements.txt`

- [x] **Step 1: Implement service helpers**

Added Comfy websocket message application, ETA estimation, QA gate summaries, visual report/contact sheet generation, review decisions, rerun payload creation, preflight checks, safer retry payloads, model/profile explainers, and cleanup suggestions.

- [x] **Step 2: Add websocket dependency**

Added `websocket-client>=1.8.0`.

- [x] **Step 3: Verify targeted tests pass**

Run: `python -m pytest tests\test_generation_intelligence.py -q`

Expected: PASS.

### Task 3: Job And API Integration

**Files:**
- Modify: `app/services/job_service.py`
- Modify: `app/spriteforge_web.py`

- [x] **Step 1: Add ComfyUI websocket watcher**

When logs expose the Comfy prompt id, `JobService` starts an optional `/ws` bridge and updates job progress from Comfy messages.

- [x] **Step 2: Attach generation metadata**

Generation jobs now carry tier/profile/action ETA and preflight metadata. Completed generation jobs write visual reports and attach QA gate summaries.

- [x] **Step 3: Add API routes**

Added model explain, generation preflight, safer retry, review decision, and rerun-similar endpoints. Sprite preview bundles now include QA gate, visual report, contact sheet URL, and matching experiment record.

### Task 4: UI Integration

**Files:**
- Modify: `app/web/index.html`
- Modify: `app/web/js/globals.js`
- Modify: `app/web/js/app_main.js`

- [x] **Step 1: Show preflight warnings**

Generation requests call `/api/preflight/generation` and show plain-English reasons before starting.

- [x] **Step 2: Show ETA and exact-progress mode**

Task progress shows per-job ETA and labels websocket-backed progress as exact ComfyUI progress.

- [x] **Step 3: Extend result review modal**

The modal now shows pass/warning/fail QA gates, reasons, contact sheet link, star/reject controls, and rerun-similar.

- [x] **Step 4: Add model/profile explainer**

The generation form explains why the selected model/profile is in use and its tradeoffs.

- [x] **Step 5: Add safer retry action**

Failed jobs expose one-click retry with safer settings through the recovery advisor.

### Task 5: Verification

- [x] **Step 1: Run targeted and smoke tests**

Run: `python -m pytest tests\test_generation_intelligence.py tests\test_smoke.py -q`

Expected: PASS.

- [x] **Step 2: Run full test suite**

Run: `python -m pytest -q`

Expected: PASS.

- [x] **Step 3: Parse changed JavaScript**

Run: `node --check app\web\js\globals.js; node --check app\web\js\app_main.js`

Expected: exit 0.
