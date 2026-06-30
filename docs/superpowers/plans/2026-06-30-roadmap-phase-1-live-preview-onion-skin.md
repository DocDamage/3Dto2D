# Roadmap Phase 1 Live Preview And Onion Skin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first working roadmap slice: metadata-driven live sprite playback and onion-skin frame overlays in the Generate Sprite result preview and Quality Lab inspector.

**Architecture:** Extend the existing `/api/sprite/preview` bundle so the browser receives ordered frame URLs and normalized frame rectangles derived from `sheet.json` and `frames_processed`. Reuse the current Quality Lab inspector canvas, adding playback via `requestAnimationFrame` and onion-skin controls that draw adjacent frames behind the selected frame.

**Tech Stack:** Flask, Python `pathlib`, existing `web_helpers.py` helpers, vanilla JavaScript, existing `gallery.js`/`editor.js`, CSS.

---

### Task 1: Preview API Frame Manifest

**Files:**
- Modify: `app/web_helpers.py`
- Test: `tests/test_advanced_features.py`

- [ ] **Step 1: Write a test for frame URLs**

Add a test that creates `sheet.json`, `sheet.png`, and `frames_processed/frame_0000.png` plus `frame_0001.png`, then calls `sprite_preview_bundle()` and asserts `frames[0].url`, `frames[0].index`, and `frame_manifest.frame_count`.

- [ ] **Step 2: Run the focused test**

Run: `python -m pytest tests/test_advanced_features.py::test_sprite_preview_bundle_includes_frame_manifest -q`

Expected: the test fails before implementation because `frames` and `frame_manifest` are missing.

- [ ] **Step 3: Implement frame manifest creation**

Add a helper in `web_helpers.py` that resolves `frames_processed` first, falls back to `frames`, and returns ordered PNG frame records with URL, relative path, index, and optional sheet rectangle metadata.

- [ ] **Step 4: Run the focused test again**

Run: `python -m pytest tests/test_advanced_features.py::test_sprite_preview_bundle_includes_frame_manifest -q`

Expected: one passing test.

### Task 2: Quality Lab Onion Skin Controls

**Files:**
- Modify: `app/web/components/quality.html`
- Modify: `app/web/styles.css`
- Modify: `app/web/js/gallery.js`

- [ ] **Step 1: Add controls**

Add toggles for previous and next onion-skin frames and an opacity range beside the existing playback controls.

- [ ] **Step 2: Render adjacent frames**

Update `renderInspectorFrame(index)` so it draws selected adjacent frames at the requested opacity before drawing the current frame. Use `frames_processed` URLs when available and fall back to the sheet crop when needed.

- [ ] **Step 3: Refresh on control changes**

Wire control changes to re-render the current frame and keep the scrubber label stable.

### Task 3: Live Playback Loop

**Files:**
- Modify: `app/web/js/editor.js`

- [ ] **Step 1: Replace interval playback**

Change playback from `setInterval` to `requestAnimationFrame`, using elapsed time and the selected FPS to advance frames.

- [ ] **Step 2: Keep controls synchronized**

When playback starts, update the button label, scrubber value, and rendered frame. When playback stops, cancel the animation frame and restore the play label.

### Task 4: Verification

**Files:**
- Test: `tests/test_advanced_features.py`

- [ ] **Step 1: Run focused tests**

Run: `python -m pytest tests/test_advanced_features.py -q`

- [ ] **Step 2: Run API smoke tests**

Run: `python -m pytest tests/test_web_api.py -q`

- [ ] **Step 3: Inspect changed files**

Run: `git diff -- app/web_helpers.py app/web/components/quality.html app/web/js/gallery.js app/web/js/editor.js app/web/styles.css tests/test_advanced_features.py`

Confirm that the diff only contains Phase 1 preview/onion-skin changes.
