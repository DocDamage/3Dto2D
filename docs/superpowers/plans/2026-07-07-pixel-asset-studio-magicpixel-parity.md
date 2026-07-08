# Pixel Asset Studio: MagicPixel-Parity Roadmap

**Date:** 2026-07-07
**Product:** SpriteForge Studio v12+
**Goal:** Add a first-class Pixel Asset Studio that gives SpriteForge the practical game-asset capabilities of MagicPixel-style web tools while preserving SpriteForge's local-first pipeline, QA, export, history, and engine integration strengths.

## Executive Summary

SpriteForge already has strong pieces for AI sprite generation, video-to-spritesheet conversion, QA, history, export, cloud provider keys, LPC paper-doll composition, and LoRA training prep. What it does not yet have is one unified pixel-art creation surface that can generate, edit, style-lock, animate, tile, and package game assets as a cohesive set.

The Pixel Asset Studio should become that surface. It should let a game developer create characters, creatures, items, weapons, potions, UI icons, tilesets, backgrounds, direction sheets, animation sheets, and style-matched batches from text prompts, references, and saved project style profiles.

This plan is intentionally phased. Each phase should ship a useful slice without waiting for the whole studio to be complete.

## Product Principles

- Build actual game-asset workflows, not another landing page or generic image generator.
- Keep outputs game-ready: fixed resolution, transparent background, nearest-neighbor scaling, limited palette, metadata sidecars, and engine exports.
- Preserve style consistency across a project through palette locks, reference sprites, prompt fingerprints, and reusable style profiles.
- Reuse SpriteForge systems first: provider keys, cloud/local generation, prompt auto-fix, history, Library, Queue, Quality Lab, Release, and engine exporters.
- Make every generated asset inspectable, editable, and recoverable through history and sidecars.
- Prefer user-controllable workflows over black-box generation.

## Current SpriteForge Assets to Reuse

- **Sprite Lab:** text/image generation, multi-action, multi-direction, prompt preview, prompt auto-fix, ComfyUI startup.
- **Cloud Hub:** cloud image provider registry, local API key storage, prompt plan preview.
- **Quality Lab:** QA reports, repair actions, sprite preview, export validation.
- **History:** experiment records, prompt memory, winning prompts, seed reuse.
- **Library:** reusable project assets and prompt/style snippets.
- **LPC Tab and Training Lab:** paper-doll composition, LPC batch datasets, LoRA handoff.
- **Animation Player and Compare Player:** frame playback, comparison, winner selection.
- **Frame Editor:** existing frame-level edit surface.
- **Tilemap and Atlas services:** tile generation/export foundations.
- **Release:** clean package assembly.

## Competitive Capability Map

MagicPixel-like capabilities to cover:

- Text-to-pixel-art generation.
- Image/reference-to-pixel-art generation.
- Reference sprite style matching.
- Cohesive batches of related assets.
- Characters and creatures.
- Items, weapons, potions, props, and UI icons.
- 4-direction and 8-direction sheets.
- Palette-locked tiles.
- Browser pixel editor.
- Inpainting and local AI edits.
- Tilesets for top-down, side-scroller, and isometric maps.
- Text-to-animation.
- Attack animation generation.
- Existing animation transfer.
- Skeleton/bone animation tools.
- Sheet slicing and export.
- Marketplace/template/tutorial style workflows.

## Target Top-Level UX

Add a new top-level nav item:

```text
Pixel Studio
```

Primary sections inside the tab:

```text
Create
Style
Batch
Directions
Tiles
Edit
Animate
Packs
History
```

The first screen should be a usable generation workspace, not marketing copy. Suggested layout:

```text
Left sidebar:
  Asset type
  Mode
  Prompt
  Reference image
  Style profile
  Palette/resolution controls
  Provider/model controls

Center:
  Generated asset gallery
  Selected asset preview
  Pixel zoom controls

Right inspector:
  Metadata
  Palette
  QA summary
  Export actions
  Edit/variation actions
```

## Data Model

Every Pixel Studio output should have a sidecar:

```json
{
  "schema": "spriteforge.pixel_asset.v1",
  "asset_id": "pxa_...",
  "created_at": "2026-07-07T00:00:00",
  "asset_type": "character",
  "mode": "reference_batch",
  "prompt": "...",
  "negative": "...",
  "provider": "openai",
  "model": "gpt-image-1",
  "source_reference": "input/reference.png",
  "style_profile_id": "style_...",
  "resolution": [32, 32],
  "palette": {
    "max_colors": 24,
    "colors": ["#000000", "#ffffff"]
  },
  "pixel_rules": {
    "transparent_background": true,
    "nearest_neighbor": true,
    "anti_alias_cleanup": true,
    "outline": "dark-clean"
  },
  "outputs": {
    "png": "output/pixel_assets/.../asset.png",
    "preview": "output/pixel_assets/.../preview.png",
    "metadata": "output/pixel_assets/.../pixel_asset.json"
  },
  "qa": {
    "ok": true,
    "color_count": 18,
    "alpha_ok": true,
    "blur_score": 0.02
  }
}
```

Style profile:

```json
{
  "schema": "spriteforge.pixel_style_profile.v1",
  "style_id": "style_...",
  "name": "Cozy 16-bit RPG",
  "source_assets": ["output/pixel_assets/hero.png"],
  "palette": ["#1b1b1b", "#e8dcb5"],
  "max_colors": 24,
  "resolution_default": [32, 32],
  "outline_hint": "dark one-pixel outline",
  "shading_hint": "limited 16-bit cel shading",
  "camera_hint": "orthographic sprite view",
  "negative_prompt": "blur, antialiasing, painterly texture, photographic detail"
}
```

Batch manifest:

```json
{
  "schema": "spriteforge.pixel_asset_batch.v1",
  "batch_id": "pxb_...",
  "asset_type": "weapon",
  "count": 24,
  "style_profile_id": "style_...",
  "asset_ids": ["pxa_1", "pxa_2"],
  "output_dir": "output/pixel_assets/batches/..."
}
```

## API Surface

Initial endpoints:

```text
GET  /api/pixel-assets/modes
POST /api/pixel-assets/generate
POST /api/pixel-assets/normalize
POST /api/pixel-assets/style/extract
GET  /api/pixel-assets/style/list
POST /api/pixel-assets/style/save
GET  /api/pixel-assets/history
POST /api/pixel-assets/export
```

Later endpoints:

```text
POST /api/pixel-assets/directions
POST /api/pixel-assets/tileset
POST /api/pixel-assets/edit
POST /api/pixel-assets/inpaint
POST /api/pixel-assets/animate
POST /api/pixel-assets/animation-transfer
POST /api/pixel-assets/skeleton/render
POST /api/pixel-assets/pack/build
```

## Phase 0: Product Foundation

### Goal

Create the Pixel Studio shell, shared schemas, and mode vocabulary without changing generation behavior yet.

### User Stories

- As a user, I can open a Pixel Studio tab and see asset-specific controls.
- As a user, I can choose what kind of asset I want to create.
- As a developer, I can add new asset modes without rewriting the whole UI.

### UI Deliverables

- Add `Pixel Studio` to top-level nav.
- Add `app/web/components/pixel_studio.html`.
- Add mode tabs:
  - Characters
  - Creatures
  - Items
  - Weapons
  - Potions
  - UI Icons
  - Tilesets
  - Backgrounds
- Add empty-state gallery.
- Add project style profile selector.
- Add resolution selector:
  - 16x16
  - 24x24
  - 32x32
  - 48x48
  - 64x64
  - 128x128
- Add palette size selector:
  - 4
  - 8
  - 16
  - 24
  - 32
  - Custom

### Backend Deliverables

- Add `app/services/pixel_asset_schema.py`.
- Add `app/services/pixel_asset_service.py`.
- Add `GET /api/pixel-assets/modes`.
- Add schema constants for assets, batches, and style profiles.
- Add output folders:
  - `output/pixel_assets/assets/`
  - `output/pixel_assets/batches/`
  - `output/pixel_assets/styles/`

### Tests

- UI component includes all mode controls.
- API returns all modes.
- Service can create output folders.
- Existing Sprite Lab, LPC, Training Lab, and History views still load.

### Acceptance Criteria

- Pixel Studio tab appears in nav.
- User can switch modes.
- No generation action is required yet.
- Test suite passes.

## Phase 1: Reference-Based Batch Generation

### Goal

Generate cohesive sets of pixel assets from a prompt, reference image, style profile, and count.

### User Stories

- As a user, I can upload a reference sprite and generate 12 matching weapons.
- As a user, I can create 20 potion icons in the same palette.
- As a user, I can generate multiple character concepts from one style.
- As a user, I can save each output to History and Library.

### UI Deliverables

- Prompt field.
- Negative prompt field.
- Reference image input.
- Count control: 1-64.
- Provider selector:
  - Local ComfyUI
  - Hugging Face
  - OpenAI
  - Google/Gemini
  - Other configured provider slots
- Generate button.
- Batch gallery with:
  - thumbnail
  - asset type
  - provider
  - style profile
  - QA badge
  - open folder
  - export PNG
  - use as style reference
  - make variations

### Backend Deliverables

- Add `generate_pixel_asset_batch()`.
- Reuse cloud provider key service.
- Reuse prompt auto-fix service.
- Add prompt templates per mode.
- Add batch manifest writer.
- Add history record writer.
- Add provider plan preview.

### Prompt Template Examples

Weapon:

```text
single {weapon_type} weapon icon, {style_profile}, transparent background,
true pixel art, fixed {resolution} canvas, limited {palette_size} color palette,
clean one-pixel outline, centered, no text
```

Potion:

```text
single potion bottle icon, {liquid_color} liquid, cork stopper,
{style_profile}, transparent background, true pixel art,
fixed {resolution} canvas, limited palette, centered, no text
```

Character:

```text
single full-body game character sprite, {character_description},
orthographic sprite view, transparent background, true pixel art,
fixed {resolution} canvas, clean silhouette, limited palette
```

### Tests

- Generation request builds correct provider payload.
- Reference image path is validated.
- Batch manifest is written.
- History record is written.
- UI has gallery controls.
- Provider missing-key errors are user-readable.

### Acceptance Criteria

- User can generate at least one asset batch.
- Assets are saved under `output/pixel_assets`.
- Each output has metadata.
- Batch appears in History/Library.

## Phase 2: True Pixel Cleanup Pipeline

### Goal

Normalize generated images into actual game-ready pixel assets.

### User Stories

- As a user, I can force all outputs to 32x32.
- As a user, I can reduce a sprite to 24 colors.
- As a user, I can remove soft edges and antialiasing.
- As a user, I can ensure transparent backgrounds.

### UI Deliverables

- Normalize toggle.
- Palette reduction toggle.
- Max color control.
- Background removal mode:
  - transparent from provider
  - chroma key
  - alpha threshold
  - automatic
- Outline cleanup toggle.
- Before/after preview.
- QA summary:
  - final size
  - color count
  - alpha detected
  - blur/antialias score

### Backend Deliverables

- Add `pixel_normalization_service.py`.
- Implement:
  - resize to fixed canvas
  - nearest-neighbor scale
  - alpha cleanup
  - palette quantization
  - small-island removal
  - optional outline pass
  - contact sheet generation
- Add `POST /api/pixel-assets/normalize`.

### Tests

- Antialiased sample gets reduced color count.
- Transparent background remains transparent.
- Fixed dimensions are enforced.
- QA detects too many colors.
- QA detects non-transparent background.

### Acceptance Criteria

- Generated assets can be normalized to fixed dimensions.
- Normalized assets are saved separately from raw assets.
- Metadata records raw and normalized paths.

## Phase 3: 4-Direction and 8-Direction Character Generator

### Goal

Generate consistent character rotations from one prompt/reference.

### User Stories

- As a user, I can generate front/back/left/right from one character.
- As a user, I can generate all 8 RPG directions.
- As a user, I can export the rotation set as a sheet.
- As a user, I can QA whether directions match scale and palette.

### UI Deliverables

- Direction mode:
  - 1 direction
  - 4 directions
  - 8 directions
- Direction grid preview.
- Lock controls:
  - same outfit
  - same palette
  - same silhouette height
  - same weapon/accessories
- Export:
  - PNG grid
  - SpriteForge `sheet.json`
  - Godot/Unity metadata

### Backend Deliverables

- Add `pixel_direction_service.py`.
- Reuse existing direction constants from Sprite Lab.
- Add direction prompt builder.
- Add consistency scoring:
  - canvas size
  - color palette overlap
  - silhouette height
  - alpha bbox position
- Add `POST /api/pixel-assets/directions`.

### Tests

- Direction list expands correctly.
- 4-direction and 8-direction sheet metadata is valid.
- QA flags mismatched dimensions.
- UI exposes All directions.

### Acceptance Criteria

- User can generate and export a 4-direction sheet.
- User can generate and export an 8-direction sheet.
- Output opens in Animation/Preview surfaces.

## Phase 4: Asset-Type Workflows

### Goal

Make each asset category purpose-built instead of generic prompt-only generation.

### User Stories

- As a user, I can generate weapons by class/material/rarity.
- As a user, I can generate potions by bottle shape and liquid color.
- As a user, I can generate UI icons with consistent border/background rules.
- As a user, I can generate creatures with size and behavior hints.

### UI Deliverables

Character controls:

- body type
- outfit
- role/class
- pose
- view
- scale

Creature controls:

- species
- size
- threat level
- body parts
- color family

Item controls:

- category
- rarity
- material
- glow/no glow
- icon silhouette

Weapon controls:

- class
- material
- angle
- handedness
- effects

Potion controls:

- bottle shape
- liquid color
- cork/stopper
- label
- rarity

UI controls:

- button/icon/bar/window
- border style
- fill color
- text/no text
- hover/disabled variants

Background controls:

- scene type
- perspective
- parallax layer
- target resolution
- tileable/no tileable

### Backend Deliverables

- Add per-mode config files:
  - `app/config/pixel_asset_modes.json`
  - `app/config/pixel_prompt_templates.json`
- Add mode-specific validation.
- Add mode-specific prompt expansion.

### Tests

- Every mode has required controls.
- Every mode has at least one prompt template.
- Invalid mode options are rejected.

### Acceptance Criteria

- User can create meaningful assets without writing a perfect prompt.
- Prompt preview shows the expanded prompt before generation.

## Phase 5: Tileset Generator

### Goal

Generate tile-ready top-down, side-scroller, and isometric tilesets.

### User Stories

- As a user, I can generate a dungeon tileset with floors, walls, corners, doors, and props.
- As a user, I can create side-scroller ground/platform tiles with seamless edges.
- As a user, I can preview tile seams before export.
- As a user, I can export an atlas for Godot or Unity.

### UI Deliverables

- Tileset mode selector:
  - top-down
  - side-scroller
  - isometric
- Tile size selector.
- Tile list:
  - ground
  - wall
  - edge
  - inner corner
  - outer corner
  - water/lava
  - door
  - decoration
  - prop
- Seam preview.
- Tilemap mock preview.
- Atlas export.

### Backend Deliverables

- Add `pixel_tileset_service.py`.
- Add tile prompt templates.
- Add tile seam QA:
  - left/right seam delta
  - top/bottom seam delta
  - corner compatibility
- Add atlas packing.
- Add Godot TileSet metadata export where feasible.

### Tests

- Tile atlas has expected dimensions.
- Seam QA flags obvious bad seams.
- Tile metadata names each tile role.
- Export ZIP includes atlas and manifest.

### Acceptance Criteria

- User can generate a small top-down tileset and preview repeated seams.
- User can export a tile atlas with metadata.

## Phase 6: Browser Pixel Editor

### Goal

Let users directly edit generated assets without leaving SpriteForge.

### User Stories

- As a user, I can zoom in and edit individual pixels.
- As a user, I can change colors from the palette.
- As a user, I can undo and redo edits.
- As a user, I can save edits as a new version.

### UI Deliverables

- Pixel canvas.
- Zoom/pan.
- Tools:
  - pencil
  - eraser
  - fill
  - eyedropper
  - line
  - rectangle
  - selection
  - move
- Palette panel.
- Undo/redo.
- Flip/rotate.
- Import/export PNG.
- Version save.

### Backend Deliverables

- Add edit history sidecar.
- Add `POST /api/pixel-assets/edit/save`.
- Add `POST /api/pixel-assets/version/save`.
- Reuse existing sprite versioning where possible.

### Tests

- Canvas component loads.
- Save endpoint writes PNG.
- Version endpoint preserves previous file.
- Undo history is capped and serializable.

### Acceptance Criteria

- User can manually edit and save an asset.
- Edited version appears in History/Library.

## Phase 7: AI Edit and Inpainting

### Goal

Allow masked local edits while preserving style.

### User Stories

- As a user, I can paint a mask over a helmet and ask for a hood instead.
- As a user, I can recolor armor without changing the pose.
- As a user, I can add an accessory while keeping the palette.
- As a user, I can compare variants and accept the best one.

### UI Deliverables

- Mask brush.
- Mask opacity toggle.
- Inpaint instruction input.
- Variant count.
- Before/after compare.
- Accept/reject buttons.
- Re-normalize after edit.

### Backend Deliverables

- Add `pixel_inpaint_service.py`.
- Add provider capability detection for image edit/inpaint.
- Add fallback strategy:
  - if provider supports masks, use mask edit
  - otherwise generate variants with source reference and crop/merge where possible
- Add `POST /api/pixel-assets/inpaint`.

### Tests

- Mask upload is validated.
- Provider without inpaint returns clear error or fallback plan.
- Accepted variant becomes new version.
- Metadata records original, mask, prompt, and result.

### Acceptance Criteria

- User can run at least one masked edit workflow.
- Accepted edit remains style-normalized.

## Phase 8: Text-to-Animation Generator

### Goal

Generate animation sheets from text and references.

### User Stories

- As a user, I can ask for a 4-frame walk cycle.
- As a user, I can generate a slash animation from a character sprite.
- As a user, I can set FPS and frame count.
- As a user, I can preview the animation immediately.

### UI Deliverables

- Animation type:
  - idle
  - walk
  - run
  - jump
  - slash
  - thrust
  - cast
  - shoot
  - hurt
  - custom
- Frame count.
- FPS.
- Direction.
- Reference sprite.
- Animation preview.
- Onion skin.
- Export sheet/GIF/APNG/WebP.

### Backend Deliverables

- Add `pixel_animation_service.py`.
- Reuse existing animation/player/export logic.
- Generate or assemble frame strips.
- Add frame consistency QA:
  - bbox jitter
  - palette drift
  - alpha stability
  - loop continuity

### Tests

- Animation metadata validates.
- Preview GIF is generated.
- QA flags severe jitter.
- Export sidecars are written.

### Acceptance Criteria

- User can generate, preview, and export a simple animation sheet.

## Phase 9: Animation Transfer

### Goal

Transfer an existing spritesheet's motion/layout to a new character.

### User Stories

- As a user, I can upload an existing walk sheet and generate a new character using the same frame poses.
- As a user, I can preserve frame count, grid layout, and timing.
- As a user, I can compare source and generated animation side by side.

### UI Deliverables

- Source spritesheet upload/path.
- Sheet slicing controls:
  - rows
  - columns
  - frame size
  - auto-detect
- New character prompt/reference.
- Source/new comparison player.
- Export same layout.

### Backend Deliverables

- Reuse sheet slicing utilities.
- Add pose caption extraction heuristics.
- Add per-frame generation queue.
- Add consistency repair pass.
- Add `POST /api/pixel-assets/animation-transfer`.

### Tests

- Sheet slicing returns expected frames.
- Output preserves frame count.
- Metadata maps source frame to generated frame.
- Export uses source layout.

### Acceptance Criteria

- User can transfer a simple idle/walk sheet to a new character prompt.

## Phase 10: Skeleton/Bone Workflow

### Goal

Add a lightweight rig workflow for reusable animation.

### User Stories

- As a user, I can define simple bones over a character.
- As a user, I can keyframe poses.
- As a user, I can render rig motion into a spritesheet.
- As a user, I can export skeletal metadata where supported.

### UI Deliverables

- Rig editor overlay.
- Bone list.
- Joint handles.
- Keyframe timeline.
- Pose copy/paste.
- Render-to-frames button.
- Export:
  - PNG sheet
  - SpriteForge metadata
  - optional Spine/DragonBones-style metadata

### Backend Deliverables

- Extend existing skeletal export service.
- Add `pixel_rig_service.py`.
- Add rig JSON schema.
- Add rasterizer/render pass.

### Tests

- Rig schema validates.
- Keyframe interpolation works for simple transforms.
- Render creates expected frame count.
- Export metadata is stable.

### Acceptance Criteria

- User can create a simple two-keyframe rig animation and export frames.

## Phase 11: Style Profiles and Persistent Memory

### Goal

Make generated assets across a whole project look like they belong together.

### User Stories

- As a user, I can save a style from a good sprite.
- As a user, I can generate new items that match my current project.
- As a user, I can see whether an asset matches the selected style.
- As a user, I can reuse successful prompts and seeds.

### UI Deliverables

- Style profile manager.
- Extract style from selected asset.
- Palette preview.
- Style consistency score.
- "Generate more like this."
- "Make this match project."
- Prompt/seed memory panel.

### Backend Deliverables

- Add `pixel_style_service.py`.
- Extract:
  - palette
  - dominant colors
  - outline color
  - canvas size
  - alpha bbox/proportions
  - prompt terms
- Add style comparison service.
- Connect to ExperimentService and Library.

### Tests

- Style profile writes JSON.
- Palette extraction is deterministic.
- Similar assets score higher than unrelated assets.
- History search returns pixel assets.

### Acceptance Criteria

- User can save and reuse a style profile.
- New generation requests can target that profile.

## Phase 12: Pack Builder

### Goal

Generate and export complete game asset packs.

### User Stories

- As a user, I can ask for an RPG starter pack.
- As a user, I can generate a hero, enemies, weapons, potions, UI icons, and tiles in one queued batch.
- As a user, I can QA and export the whole pack.

### UI Deliverables

- Pack recipe selector:
  - RPG hero starter
  - dungeon crawler pack
  - platformer starter
  - potion/item shop pack
  - UI HUD pack
- Counts per asset type.
- Shared style profile.
- Queue preview.
- Batch progress.
- QA gate.
- Release export.

### Backend Deliverables

- Add `pixel_pack_service.py`.
- Add pack recipe schema.
- Reuse queue/job system.
- Reuse release package builder.
- Add pack manifest.

### Tests

- Recipe expands to queue jobs.
- Failed jobs are resumable.
- Pack manifest references all outputs.
- Release ZIP excludes local keys, logs, vendor payloads, and model weights.

### Acceptance Criteria

- User can generate a small pack and export a ZIP.

## Phase 13: Marketplace and Template Library

### Goal

Make repeatable workflows easy to discover and reuse.

### User Stories

- As a user, I can pick a template and generate assets without knowing prompts.
- As a user, I can save my own recipe.
- As a user, I can import/export recipes.

### UI Deliverables

- Recipe cards.
- Search/filter.
- Save current settings as recipe.
- Import recipe JSON.
- Export recipe JSON.
- Tutorial links/cards.

### Backend Deliverables

- Add `pixel_recipe_service.py`.
- Add recipe validation.
- Add local recipe folder.
- Optional integration with existing marketplace service.

### Tests

- Built-in recipes validate.
- User recipe round-trips.
- Invalid recipe fails with clear messages.

### Acceptance Criteria

- User can generate from a built-in recipe and save a custom recipe.

## Phase 14: Documentation, QA, and Polish

### Goal

Make Pixel Studio dependable enough to be part of the normal product.

### Deliverables

- Update:
  - `README.md`
  - `app/docs/END_USER_GUIDE.md`
  - `app/docs/api.md`
  - `app/docs/ONE_PAGE_CHEAT_SHEET.md`
  - `app/docs/TROUBLESHOOTING_v8.md`
- Add tutorial cards in-app.
- Add failure explainers:
  - missing provider key
  - provider does not support image edit
  - image not square
  - too many colors
  - no alpha
  - style mismatch
  - tile seam failure
- Add visual QA pages.
- Add regression coverage for every phase.

### Acceptance Criteria

- Full test suite passes.
- API docs include all Pixel Studio endpoints.
- User guide includes first asset, first tileset, first animation, and first pack workflows.

## Recommended Delivery Order

The fastest useful path:

1. Phase 0: Product Foundation
2. Phase 1: Reference-Based Batch Generation
3. Phase 2: True Pixel Cleanup Pipeline
4. Phase 3: 4/8 Direction Character Generator
5. Phase 5: Tileset Generator
6. Phase 6: Browser Pixel Editor
7. Phase 7: AI Edit and Inpainting
8. Phase 8: Text-to-Animation Generator
9. Phase 11: Style Profiles and Persistent Memory
10. Phase 12: Pack Builder
11. Phase 13: Marketplace and Template Library
12. Phase 14: Documentation, QA, and Polish

Phases 4, 9, and 10 can be pulled earlier if the immediate priority becomes specialized asset controls, animation transfer, or skeleton editing.

## Engineering Milestones

### Milestone A: Studio Shell

- Pixel Studio tab.
- Mode selector.
- Style/resolution/palette controls.
- Empty gallery.
- API modes endpoint.

### Milestone B: Generate and Normalize

- Batch generation endpoint.
- Provider integration.
- Normalization service.
- Gallery output.
- Metadata sidecars.

### Milestone C: Directions and Tiles

- 4/8 direction generator.
- Direction sheet export.
- Tileset generator.
- Seam preview.

### Milestone D: Edit and Inpaint

- Pixel editor.
- Masked edit.
- Version history.
- Before/after compare.

### Milestone E: Animate and Pack

- Text-to-animation.
- Animation transfer.
- Pack recipes.
- Release exports.

## Risk Register

### Provider Capability Drift

Cloud providers change model names, quotas, image-edit support, and pricing.

Mitigation:

- Centralize provider metadata.
- Detect capability at runtime where possible.
- Keep friendly failure messages.
- Keep local ComfyUI as an option.

### Pixel Art Quality

Generic models may produce high-res pixel-looking art, not true pixel art.

Mitigation:

- Normalize every output.
- Enforce fixed canvas sizes.
- Add palette/blur QA.
- Provide manual pixel editor.

### Style Inconsistency

Batches may drift in palette, outline, pose, or proportions.

Mitigation:

- Use style profiles.
- Compare palette overlap and silhouette metrics.
- Provide regenerate/repair actions.
- Save accepted winners as stronger references.

### Tileset Seams

AI-generated tiles may not tile cleanly.

Mitigation:

- Generate edge/corner roles explicitly.
- Add seam QA.
- Add seam preview.
- Add repair/regenerate selected tile action.

### Scope Creep

Pixel Studio can grow into a full art suite.

Mitigation:

- Ship phase-by-phase.
- Keep every phase independently useful.
- Reuse existing SpriteForge services.
- Avoid building a second unrelated app inside the app.

## First Implementation Slice Recommendation

Start with **Milestone A + part of Milestone B**:

- Add Pixel Studio tab.
- Add mode selector.
- Add prompt/reference/count/style controls.
- Add `/api/pixel-assets/modes`.
- Add `/api/pixel-assets/generate` as a dry-run/plan endpoint first.
- Reuse cloud provider plan generation to show exactly what would be sent.
- Add gallery placeholder and saved metadata schema.

This gives immediate product shape and lets the next slice turn the plan into real generation without redesigning the UI.

## Definition of Done for Each Phase

- Feature works through the browser UI.
- API is documented.
- Output has sidecar metadata.
- History/Library receives the output when relevant.
- Tests cover service, route, and UI wiring.
- Existing Sprite Lab, LPC, Training Lab, Quality Lab, and Release workflows still pass regression tests.
- User-facing failure messages are plain English.

