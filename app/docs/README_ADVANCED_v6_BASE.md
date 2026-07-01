# SpriteForge Studio v6 Advanced Base Archive

Historical note: this document is retained for advanced CLI background and compatibility with older references. For the current v12 dashboard workflow, model-tier setup, API behavior, and release packaging rules, use `END_USER_GUIDE.md`, `WAN_MODEL_TIERS_v11.md`, `api.md`, and `FINAL_POLISH_v12.md`.

Unified Windows-oriented tool for:

```text
ComfyUI + WAN generation
        ↓
action prompt builder / pose guide / reference image support
        ↓
exact ComfyUI prompt history tracking
        ↓
video-to-sprite conversion
        ↓
spritesheet + metadata + QA report
        ↓
optional repair pass
        ↓
multi-animation atlas
        ↓
Godot / Unity helper export
```

It also keeps the true orthographic route:

```text
Blender 3D character / rig / animation
        ↓
orthographic transparent PNG frame render
        ↓
spritesheet export
```

## What changed in v6

v6 is the production-sprite pass. It keeps the v5 ComfyUI/WAN, posepack, reference-image, cloud-package, and snapshot tools, then adds the stuff you need before using the outputs in a real game.

1. **Sprite QA scoring**
   - Scores output folders for ground/foot jitter, center drift, duplicate frames, loop seam mismatch, alpha edge clipping, and bounding-box variation.
   - Writes `quality_report.json`, `quality_report.html`, and a visual overlay contact sheet.

2. **Sprite repair pass**
   - Re-crops each frame and re-anchors the subject into a stable cell.
   - Default is bottom-center anchoring, which is usually right for characters.
   - Can drop duplicate frames and duplicate loop endpoints.

3. **Character pack manifests**
   - Creates a full action/direction plan with prompts and optional posepacks.
   - Useful for packs like idle/walk/run/attack/hurt/death across front/right/back/left.

4. **Pack collection and atlas building**
   - Scans a folder full of generated SpriteForge outputs.
   - Builds `pack_index.json`, `pack_quality.json`, `atlas.png`, and `atlas.json`.

5. **Better engine helpers**
   - Godot export now supports `AnimatedSprite2D` runtime `SpriteFrames` generation as well as `Sprite2D` grid-frame playback.
   - Unity export now includes an editor tool to create an `.anim` AnimationClip from sliced sprites.

6. **Drag-and-drop QA tools**
   - Added `QA_Sprite.bat`, `Repair_Sprite.bat`, `Create_Character_Pack.bat`, and `Build_Pack_Atlas.bat`.

## First setup

Extract this ZIP.

Open Command Prompt inside the extracted folder and run:

```bat
setup_windows.bat
```

Then launch the GUI:

```bat
SpriteForge_Studio.bat
```

Recommended setup order:

```text
1. Install SpriteForge Python deps
2. Install/Update ComfyUI + WAN Nodes
3. Install/Update ComfyUI Manager optional
4. Download Native Wan 2.1 1.3B Model Files
5. Snapshot ComfyUI Before Updates
6. Run Doctor
7. Launch ComfyUI
8. Validate Included Workflow
9. Generate WAN → exact history output → build spritesheet
10. Run QA
11. Repair if needed
12. Pack an atlas
13. Export Godot/Unity helpers
```

## Safe local target for RTX 3060 12GB

Start here:

```bat
python spriteforge_unified.py generate-sprite --start-comfy --mode t2v --profile debug --action idle --direction front
```

Then:

```bat
python spriteforge_unified.py generate-sprite --start-comfy --mode t2v --profile rtx3060_12gb --action walk --direction right --character "single full body cyberpunk drummer character, black jacket, red shoes, clean silhouette"
```

The automatic prompt builder fills in a sprite-oriented positive/negative prompt when `--prompt` is omitted.

## v6 production QA commands

Score one generated sprite output:

```bat
python spriteforge_unified.py quality --sprite-dir output\hero_walk_sprite
```

Outputs:

```text
output/hero_walk_sprite/quality/quality_report.json
output/hero_walk_sprite/quality/quality_report.html
output/hero_walk_sprite/quality/quality_overlay.jpg
```

Repair foot jitter / re-anchor frames:

```bat
python spriteforge_unified.py repair-sprite --sprite-dir output\hero_walk_sprite --output output\hero_walk_repaired --anchor bottom-center --pad 8 --drop-loop-duplicate
```

Compare two versions:

```bat
python spriteforge_unified.py compare-sprites --a output\hero_walk_sprite --b output\hero_walk_repaired
```

## v6 quality score interpretation

```text
88-100  excellent       usable with little cleanup
74-87   good            probably usable, inspect loop seam
55-73   needs_cleanup   repair/regenerate recommended
0-54    problematic     likely not production-ready
```

The score is not a beauty metric. It is a game-sprite usability metric: stable feet, stable center, no clipping, no dead frames, and cleaner loops.

## Character pack planning

Create a full character pack plan with prompts and posepacks:

```bat
python spriteforge_unified.py pack-init --name hero_pack --character "single full body cyberpunk drummer, black jacket, red shoes" --actions idle,walk,run,attack_light,hurt,death --directions front,right,back,left --pose-guided --posepacks
```

This writes:

```text
output/packs/hero_pack/pack_manifest.json
output/packs/hero_pack/prompts/*.json
output/packs/hero_pack/posepacks/*
```

Generate the actual WAN sprites using those prompt/pose assets, then collect and score the results:

```bat
python spriteforge_unified.py pack-collect --root output\packs\hero_pack
python spriteforge_unified.py pack-quality --root output\packs\hero_pack
```

Build one atlas texture from many SpriteForge outputs:

```bat
python spriteforge_unified.py pack-atlas --root output\packs\hero_pack --output output\packs\hero_pack\atlas
```

Outputs:

```text
atlas.png
atlas.json
ATLAS_NOTES.md
```

## Build a prompt without generating

```bat
python spriteforge_unified.py build-prompt --action walk --direction right --character "single full body original game hero, blue coat, boots"
```

Save it:

```bat
python spriteforge_unified.py build-prompt --action attack_light --direction right --output output\prompts\hero_attack_light.json
```

## Posepack generation

Create a pose guide sequence:

```bat
python spriteforge_unified.py make-posepack --action walk --direction right --frames 32 --size 512
```

Use it with a custom pose workflow:

```bat
python spriteforge_unified.py generate-sprite --start-comfy --mode custom --workflow workflows\your_pose_workflow_api.json --posepack output\posepacks\walk_right_YYYYMMDD_HHMMSS --action walk --direction right
```

Important: the generated posepack is a guide asset. True pose control still requires a ComfyUI workflow with pose/control nodes. Export that workflow using ComfyUI `File → Export (API)`, then pass it with `--workflow`.

## Image-to-video reference mode

Put a character reference image in `input\`.

```bat
python spriteforge_unified.py generate-sprite --start-comfy --mode i2v --profile i2v_cloud_24gb_plus --reference-image input\hero_reference.png --action idle --direction front
```

Blunt hardware note: I2V 14B is not a comfortable RTX 3060 12GB workflow. Use the cloud job packaging if it stalls or crashes locally.

## Cloud GPU packaging

Create a portable job zip:

```bat
python spriteforge_unified.py cloud-package --mode i2v --profile i2v_cloud_24gb_plus --reference-image input\hero_reference.png --prompt "single full body character idle animation, preserve reference identity, locked camera, green background"
```

Write a safe RunPod-style plan file:

```bat
python spriteforge_unified.py cloud-plan
```

No cloud API keys are stored by SpriteForge.

## Godot export

After creating a sprite output folder that contains `sheet.png` and `sheet.json`:

```bat
python spriteforge_unified.py export-engine --engine godot --sprite-dir output\hero_walk_repaired --project C:\Path\To\GodotProject --name hero_walk --godot-mode animatedsprite2d
```

Use `--godot-mode sprite2d` if you prefer grid-frame playback through `Sprite2D.hframes`, `vframes`, and `frame`.

## Unity export

```bat
python spriteforge_unified.py export-engine --engine unity --sprite-dir output\hero_walk_repaired --project C:\Path\To\UnityProject --name hero_walk
```

Inside Unity:

```text
1. Select sheet.png.
2. Run Tools > SpriteForge > Slice Selected SpriteForge Sheet.
3. Run Tools > SpriteForge > Create Animation Clip From Selected Sheet.
```

## Unreal Engine export

```bat
python spriteforge_unified.py export-engine --engine unreal --sprite-dir output\hero_walk_repaired --project C:\Path\To\UnrealProject --name hero_walk --import-path /Game/Characters/Hero
```

The Unreal export copies `sheet.png` and `sheet.json`, then writes `unreal_import_helper.py` and `UNREAL_IMPORT_NOTES.md`. Run the helper from Unreal's Python console after enabling the Python Editor Script and Paper2D plugins. The helper imports the texture, configures sprite-friendly filtering, slices frames from the SpriteForge metadata, and creates a Paper2D flipbook.

## Snapshot / rollback

Before major ComfyUI/custom-node updates:

```bat
python spriteforge_unified.py snapshot
python spriteforge_unified.py safe-update --custom-nodes
```

Rollback:

```bat
python spriteforge_unified.py rollback SNAPSHOT_NAME
```

## Troubleshooting

### Speccy says RTX 3060 has 4095MB

Ignore it. Use `nvidia-smi`, Task Manager, GPU-Z, or NVIDIA Control Panel.

### WAN output changes character details frame-to-frame

Use reference-image workflows if possible, reduce prompt complexity, use a simpler outfit, and keep camera/view/action language rigid.

### The sprite jumps around

Run:

```bat
python spriteforge_unified.py repair-sprite --sprite-dir output\YOUR_SPRITE --anchor bottom-center --pad 8 --drop-loop-duplicate
```

Then run:

```bat
python spriteforge_unified.py quality --sprite-dir output\YOUR_SPRITE_repaired
```

### The sprite has a green/blue box around it

Use a solid background in WAN, then convert with chroma key. The video converter supports `--key-color auto` and manual `--key-color R,G,B` through `spriteforge.py`.

## Additional v6 hardening commands

These commands focus on practical cleanup and consistency after generation.

### Hardware advisor

```bat
python spriteforge_unified.py hardware-advisor
```

This reads `nvidia-smi` when available and recommends local/cloud WAN usage plus safe sprite defaults. To back up `config/spriteforge_config.json` and apply recommended sprite defaults:

```bat
python spriteforge_unified.py hardware-advisor --apply
```

### QA report and auto-fix

```bat
python spriteforge_unified.py qa-report --input output\hero_walk_sprite
python spriteforge_unified.py autofix-sprite --input output\hero_walk_sprite --output output\hero_walk_fixed --drop-loop-duplicate --stabilize-anchor --deflicker --solidify 2
```

`qa-report` uses the active project's `quality_gates` by default. You can also force a named preset or override individual gates:

```bat
python spriteforge_unified.py qa-report --input output\hero_walk_sprite --qa-preset "Top-Down RPG Character"
python spriteforge_unified.py qa-report --input output\hero_walk_sprite --foot-drift-threshold 4 --loop-rmse-threshold 18
```

The test suite includes visual regression coverage through `services.visual_regression_service.compare_sprite_to_golden`, which compares a current `sheet.png` against a golden SpriteForge output folder and records pixel-delta metrics.

The report checks loop seam distance, duplicate frames, foot/ground drift, horizontal jitter, silhouette popping, blank frames, and brightness flicker.

### Character consistency pack

```bat
python spriteforge_unified.py character-pack --name Hero --description "single full body cyberpunk drummer, black jacket, red shoes" --reference-image input\hero_ref.png --actions idle,walk,run,attack_light,hurt,death --directions right,left
```

This creates:

```text
characters/Hero/
  character_profile.json
  action_batch.json
  run_action_batch.bat
  palette.png optional
  references/
```

### Fresh action batch from a character profile

```bat
python spriteforge_unified.py batch-actions --profile characters\Hero\character_profile.json --actions idle,walk,attack_light --directions right,left
```

### Remote ComfyUI generation

For cloud or another machine running ComfyUI:

```bat
python spriteforge_unified.py remote-generate --server http://YOUR_REMOTE_HOST:8188 --workflow workflows\your_exported_api_workflow.json --prompt "single full body character walk cycle, locked camera, green background" --convert
```

This submits the workflow to the remote ComfyUI API, waits for exact `/history` output, downloads the output through `/view`, and optionally converts it locally into a spritesheet.

### Extra atlas metadata formats

```bat
python spriteforge_unified.py export-atlas --sprite-dir output\hero_walk_sprite --format texturepacker --copy-image
python spriteforge_unified.py export-atlas --sprite-dir output\hero_walk_sprite --format phaser
python spriteforge_unified.py export-atlas --sprite-dir output\hero_walk_sprite --format pixijs
python spriteforge_unified.py export-atlas --sprite-dir output\hero_walk_sprite --format aseprite
python spriteforge_unified.py export-atlas --sprite-dir output\hero_walk_sprite --format css
python spriteforge_unified.py export-atlas --sprite-dir output\hero_walk_sprite --format xml
```

Use these when your engine or web renderer expects common atlas JSON instead of the default SpriteForge `sheet.json`.
