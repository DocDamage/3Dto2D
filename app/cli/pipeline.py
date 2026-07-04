import argparse
import sys
from pathlib import Path
from spriteforge_commands import ROOT, run, cmd_qa_report


def add_parsers(sub: argparse._SubParsersAction) -> None:
    import spriteforge_unified_parser

    s = sub.add_parser("training-dataset", help="Build an image/caption dataset from owned sprite assets for LoRA training")
    s.add_argument("--source", required=True, help="Folder containing purchased/owned sprite PNGs or sheets")
    s.add_argument("--output", default=None, help="Output dataset folder. Defaults to output/training_datasets/<name>_<timestamp>.")
    s.add_argument("--name", default="sprite_dataset")
    s.add_argument("--trigger", default="sakpix_style")
    s.add_argument("--base-caption", default="premium pixel art RPG character")
    s.add_argument("--cell-size", default=None, help="Optional sprite cell size for sheet slicing, e.g. 92x92 or 128x128")
    s.set_defaults(func=spriteforge_unified_parser.cmd_training_dataset)

    s = sub.add_parser("autotile-dataset", help="Build an image/caption dataset from owned stage tile sheets for auto-tile LoRA training")
    s.add_argument("--source", required=True, help="Folder containing purchased/owned tile-set sheets")
    s.add_argument("--output", default=None, help="Output dataset folder. Defaults to output/training_datasets/<name>_<timestamp>.")
    s.add_argument("--name", default="sakpix_autotiles")
    s.add_argument("--trigger", default="sakpix_tiles")
    s.add_argument("--base-caption", default="premium top-down pixel art tileset")
    s.add_argument("--cell-size", default="auto", help="auto or explicit tile cell size, e.g. 128x128")
    s.add_argument("--max-samples-per-source", default="32", help="Maximum cells kept from each source sheet; use 0 for no cap")
    s.add_argument("--include-all", action="store_true", help="Include prop/object sheets too, not just tile-like sheet names")
    s.set_defaults(func=spriteforge_unified_parser.cmd_autotile_dataset)

    s = sub.add_parser("tilemap", help="Generate game-ready autotile or Wang tile sheets")
    s.add_argument("--mode", choices=["autotile_16", "wang_16"], default="autotile_16")
    s.add_argument("--base", default="", help="Base tile for autotile_16 mode")
    s.add_argument("--border", default="", help="Border tile for autotile_16 mode")
    s.add_argument("--north", default="", help="North material tile for wang_16 mode")
    s.add_argument("--east", default="", help="East material tile for wang_16 mode")
    s.add_argument("--south", default="", help="South material tile for wang_16 mode")
    s.add_argument("--west", default="", help="West material tile for wang_16 mode")
    s.add_argument("--tile-size", type=int, default=0)
    s.add_argument("--output", default="output/tilesets/autotile_16.png")
    s.set_defaults(func=spriteforge_unified_parser.cmd_tilemap)

    s = sub.add_parser("lora-train", help="Prepare or launch an SDXL/Flux LoRA trainer run from a SpriteForge training dataset")
    s.add_argument("--dataset", required=True, help="Training dataset folder created by training-dataset")
    s.add_argument("--output", default=None, help="Output training run folder. Defaults to output/training_runs/<name>_<timestamp>.")
    s.add_argument("--name", default="sprite_lora")
    s.add_argument("--model-family", default="sdxl", choices=["sdxl", "flux"])
    s.add_argument("--trainer", default="auto", choices=["auto", "kohya", "ai_toolkit"])
    s.add_argument("--base-model", default="", help="Base checkpoint path or Hugging Face model id used by the trainer")
    s.add_argument("--trigger", default="sakpix_style")
    s.add_argument("--resolution", default="768")
    s.add_argument("--max-train-steps", default="1200")
    s.add_argument("--learning-rate", default="1e-4")
    s.add_argument("--network-dim", default="16")
    s.add_argument("--repeats", default="10")
    s.add_argument("--batch-size", default="1")
    s.add_argument("--trainer-dir", default=None, help="Installed trainer folder. Defaults to vendor/kohya_ss or vendor/ai-toolkit.")
    s.add_argument("--run", action="store_true", help="Start the external trainer after writing configs")
    s.add_argument("--native-only", action="store_true", help="Run through SpriteForge native-only LoRA training runtime instead of external trainer.")
    s.set_defaults(func=spriteforge_unified_parser.cmd_lora_train)

    s = sub.add_parser("export-engine", help="Create Godot or Unity helper files from a SpriteForge output folder")
    s.add_argument("--sprite-dir", required=True)
    s.add_argument("--engine", required=True, choices=["godot", "unity", "unreal"])
    s.add_argument("--output", default=None)
    s.add_argument("--project", default=None)
    s.add_argument("--name", default=None)
    s.add_argument("--res-path", default=None)
    s.add_argument("--godot-mode", choices=["animatedsprite2d", "sprite2d"], default="animatedsprite2d")
    s.add_argument("--naming-convention", default="default")
    s.add_argument("--pivot-mode", default="bottom-center")
    s.add_argument("--ppu", type=int, default=100)
    s.add_argument("--filter-mode", default="nearest")
    s.add_argument("--loop-flag", default="true")
    s.add_argument("--import-path", default=None)
    s.add_argument("--clip-name", default=None)

    def _export_engine(a):
        cmd = [sys.executable, str(ROOT / "spriteforge_engine_export.py"), "export", "--sprite-dir", a.sprite_dir, "--engine", a.engine]
        for name in ["output", "project", "name", "res_path", "naming_convention", "pivot_mode", "ppu", "filter_mode", "loop_flag", "import_path", "clip_name"]:
            val = getattr(a, name, None)
            if val is not None:
                cmd += [f"--{name.replace('_', '-')}", str(val)]
        if a.engine == "godot":
            cmd += ["--godot-mode", a.godot_mode]
        run(cmd)

    s.set_defaults(func=_export_engine)

    s = sub.add_parser("quality-check", help="Run QC on one SpriteForge output folder")
    s.add_argument("--sprite-dir", required=True)
    s.add_argument("--output", default=None)
    s.add_argument("--fail-under", type=float, default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_quality.py"), "quality", "--sprite-dir", a.sprite_dir] + (["--output", a.output] if a.output else []) + (["--fail-under", str(a.fail_under)] if a.fail_under is not None else []), check=False))

    s = sub.add_parser("quality-batch", help="Run QC over every SpriteForge output folder under a root")
    s.add_argument("--root", default="output")
    s.add_argument("--output", default=None)
    s.add_argument("--fail-under", type=float, default=None)
    s.add_argument("--junit-xml", default=None, help="Write JUnit XML report for CI dashboards")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_quality.py"), "batch", "--root", a.root] + (["--output", a.output] if a.output else []) + (["--fail-under", str(a.fail_under)] if a.fail_under is not None else []) + (["--junit-xml", a.junit_xml] if a.junit_xml else []), check=False))

    s = sub.add_parser("atlas-build", help="Build one multi-animation atlas from multiple SpriteForge output folders")
    s.add_argument("--sprites", nargs="*", default=[])
    s.add_argument("--root", default=None, help="Discover SpriteForge outputs under this root when --sprites is omitted")
    s.add_argument("--output", required=True)
    s.add_argument("--columns", type=int, default=None)
    s.add_argument("--cell-size", default=None)
    s.add_argument("--name", default="spriteforge_atlas")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_atlas.py"), "atlas", "--output", a.output, "--name", a.name] + (["--root", a.root] if a.root else []) + (["--columns", str(a.columns)] if a.columns else []) + (["--cell-size", a.cell_size] if a.cell_size else []) + (["--sprites"] + a.sprites if a.sprites else [])))

    s = sub.add_parser("workflow-slots", help="Inspect an exported ComfyUI API workflow and write a slot map")
    s.add_argument("--workflow", required=True)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_workflows.py"), "slots", "--workflow", a.workflow] + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("workflow-patch", help="Patch a ComfyUI API workflow using detected workflow slots")
    s.add_argument("--workflow", required=True)
    s.add_argument("--mapping", default=None)
    s.add_argument("--output", default=None)
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--prompt", default=None)
    s.add_argument("--negative", default=None)
    s.add_argument("--seed", type=int, default=None)
    s.add_argument("--steps", type=int, default=None)
    s.add_argument("--cfg", type=float, default=None)
    s.add_argument("--sampler", default=None)
    s.add_argument("--scheduler", default=None)
    s.add_argument("--width", type=int, default=None)
    s.add_argument("--height", type=int, default=None)
    s.add_argument("--frames", type=int, default=None)
    s.add_argument("--fps", type=int, default=None)
    s.add_argument("--output-prefix", default=None)
    s.add_argument("--reference-image", default=None)
    s.add_argument("--model", default=None)
    s.add_argument("--text-encoder", default=None)
    s.add_argument("--vae", default=None)
    s.add_argument("--clip-vision", default=None)

    def _wf_patch(a):
        cmd = [sys.executable, str(ROOT / "spriteforge_workflows.py"), "patch", "--workflow", a.workflow]
        for name in ["mapping", "output", "prompt", "negative", "output_prefix", "reference_image", "model", "text_encoder", "vae", "clip_vision", "sampler", "scheduler"]:
            val = getattr(a, name)
            if val is not None:
                cmd += ["--" + name.replace("_", "-"), str(val)]
        for name in ["seed", "steps", "cfg", "width", "height", "frames", "fps"]:
            val = getattr(a, name)
            if val is not None:
                cmd += ["--" + name.replace("_", "-"), str(val)]
        if a.dry_run:
            cmd += ["--dry-run"]
        run(cmd)

    s.set_defaults(func=_wf_patch)

    s = sub.add_parser("production-plan", help="Create prompts/posepacks/commands for a full character action set")
    s.add_argument("--character", default=None)
    s.add_argument("--style", default=None)
    s.add_argument("--direction", default="right")
    s.add_argument("--actions", default=None)
    s.add_argument("--output", default=None)
    s.add_argument("--pose", action="store_true")
    s.add_argument("--seeds", type=int, default=1)

    def _prod(a):
        cmd = [sys.executable, str(ROOT / "spriteforge_batch.py"), "plan", "--direction", a.direction, "--seeds", str(a.seeds)]
        if a.character:
            cmd += ["--character", a.character]
        if a.style:
            cmd += ["--style", a.style]
        if a.actions:
            cmd += ["--actions", a.actions]
        if a.output:
            cmd += ["--output", a.output]
        if a.pose:
            cmd += ["--pose"]
        run(cmd)

    s.set_defaults(func=_prod)

    s = sub.add_parser("quality", help="Score one sprite output for jitter, loop seam, edge clipping, duplicates, and alpha problems")
    s.add_argument("--sprite-dir", required=True)
    s.add_argument("--output", default=None)
    s.add_argument("--alpha-threshold", type=int, default=8)
    s.add_argument("--duplicate-threshold", type=float, default=0.006)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_quality.py"), "quality", "--sprite-dir", a.sprite_dir] + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("repair-sprite", help="Repair a sprite output by re-anchoring frames into a stable bottom-center cell")
    s.add_argument("--sprite-dir", required=True)
    s.add_argument("--output", default=None)
    s.add_argument("--cell-size", default=None)
    s.add_argument("--anchor", default="bottom-center", choices=["bottom-center", "bottom-left", "bottom-right", "center"])
    s.add_argument("--pad", type=int, default=8)
    s.add_argument("--floor-pad", type=int, default=0)
    s.add_argument("--drop-duplicates", action="store_true")
    s.add_argument("--drop-loop-duplicate", action="store_true")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_qc.py"), "autofix", "--input", a.sprite_dir, "--solidify", "2"] + (["--output", a.output] if a.output else []) + (["--drop-loop-duplicate"] if a.drop_loop_duplicate else []) + (["--stabilize-anchor"] if True else [])))

    s = sub.add_parser("compare-sprites", help="Compare two sprite outputs frame-by-frame")
    s.add_argument("--a", required=True)
    s.add_argument("--b", required=True)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_compare.py"), "compare", "--a", a.a, "--b", a.b] + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("pack-init", help="Create a multi-action/multi-direction character pack plan with prompts and optional posepacks")
    s.add_argument("--name", default="character_pack")
    s.add_argument("--character", default="single full body original game character, professional appealing character design, heroic adult proportions, distinctive outfit, clean silhouette")
    s.add_argument("--style", default="high quality 2D game sprite animation, polished concept-art quality, crisp cel-shaded edges, readable silhouette")
    s.add_argument("--background", default="plain bright green chroma key background")
    s.add_argument("--extra", default="")
    s.add_argument("--actions", default="idle,walk,run,attack_light,hurt,death")
    s.add_argument("--directions", default="front,right,back,left")
    s.add_argument("--output", default=None)
    s.add_argument("--reference", action="store_true")
    s.add_argument("--pose-guided", action="store_true")
    s.add_argument("--posepacks", action="store_true")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_pack.py"), "init", "--name", a.name, "--character", a.character, "--style", a.style, "--background", a.background, "--extra", a.extra, "--actions", a.actions, "--directions", a.directions] + (["--output", a.output] if a.output else []) + (["--reference"] if a.reference else []) + (["--pose-guided"] if a.pose_guided else []) + (["--posepacks"] if a.posepacks else [])))

    s = sub.add_parser("pack-collect", help="Collect finished sprite outputs into a pack index")
    s.add_argument("--root", required=True)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_pack.py"), "collect", "--root", a.root] + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("pack-atlas", help="Build one atlas.png + atlas.json from many SpriteForge sprite outputs")
    s.add_argument("--root", default=None)
    s.add_argument("--sprite-dir", action="append", default=[])
    s.add_argument("--output", required=True)
    s.add_argument("--max-width", type=int, default=4096)
    s.add_argument("--padding", type=int, default=4)

    def _pack_atlas(a):
        cmd = [sys.executable, str(ROOT / "spriteforge_pack.py"), "atlas", "--output", a.output, "--max-width", str(a.max_width), "--padding", str(a.padding)]
        if a.root:
            cmd += ["--root", a.root]
        for sd in a.sprite_dir or []:
            cmd += ["--sprite-dir", sd]
        return run(cmd)

    s.set_defaults(func=_pack_atlas)

    s = sub.add_parser("pack-quality", help="Run quality scoring across all sprite outputs in a pack/root folder")
    s.add_argument("--root", required=True)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_pack.py"), "qa", "--root", a.root] + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("qa-report", help="Analyze a SpriteForge output folder for loop seams, jitter, duplicates, flicker, and anchor drift")
    s.add_argument("--input", required=True, help="SpriteForge output folder or image-frame folder")
    s.add_argument("--output", default=None)
    s.add_argument("--duplicate-threshold", type=float, default=1.25)
    s.add_argument("--qa-preset", default="auto", help="Named QA preset or 'auto' to use active/project quality gates")
    s.add_argument("--loop-rmse-threshold", type=float, default=None)
    s.add_argument("--foot-drift-threshold", type=float, default=None)
    s.add_argument("--center-drift-threshold", type=float, default=None)
    s.set_defaults(func=cmd_qa_report)

    s = sub.add_parser("autofix-sprite", help="Create a stabilized fixed copy of a sprite output folder")
    s.add_argument("--input", required=True)
    s.add_argument("--output", default=None)
    s.add_argument("--drop-loop-duplicate", action="store_true")
    s.add_argument("--stabilize-anchor", action="store_true")
    s.add_argument("--deflicker", action="store_true")
    s.add_argument("--solidify", type=int, default=2)
    s.add_argument("--blend-loop-frames", type=int, default=3)
    s.add_argument("--sharpen", action="store_true", help="Sharpen sprite edges")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_qc.py"), "autofix", "--input", a.input] + (["--output", a.output] if a.output else []) + (["--drop-loop-duplicate"] if a.drop_loop_duplicate else []) + (["--stabilize-anchor"] if a.stabilize_anchor else []) + (["--deflicker"] if a.deflicker else []) + ["--solidify", str(a.solidify)] + ["--blend-loop-frames", str(a.blend_loop_frames)] + (["--sharpen"] if a.sharpen else [])))

    s = sub.add_parser("character-pack", help="Create a character consistency pack: reference, palette, identity rules, actions, and batch BAT")
    s.add_argument("--name", required=True)
    s.add_argument("--description", required=True)
    s.add_argument("--reference-image", default=None)
    s.add_argument("--style", default="polished 2D game sprite, professional character design, crisp cel-shaded edges, consistent palette")
    s.add_argument("--background", default="plain bright green background")
    s.add_argument("--actions", default="idle,walk,run,attack_light,attack_heavy,hurt,death")
    s.add_argument("--directions", default="right")
    s.add_argument("--tier", default="wan22_5b")
    s.add_argument("--mode", default="auto", choices=["auto", "t2v", "ti2v22", "i2v", "vace", "custom"])
    s.add_argument("--profile", default="rtx3060_12gb")
    s.add_argument("--workflow", default=None)
    s.add_argument("--seed", type=int, default=-1)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_character.py"), "create", "--name", a.name, "--description", a.description, "--style", a.style, "--background", a.background, "--actions", a.actions, "--directions", a.directions, "--tier", a.tier, "--mode", a.mode, "--profile", a.profile, "--seed", str(a.seed)] + (["--workflow", a.workflow] if a.workflow else []) + (["--reference-image", a.reference_image] if a.reference_image else []) + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("batch-actions", help="Create a sequential generation batch from a character_profile.json")
    s.add_argument("--profile", required=True, help="Path to character_profile.json")
    s.add_argument("--actions", default=None)
    s.add_argument("--directions", default=None)
    s.add_argument("--tier", default=None)
    s.add_argument("--mode", default="auto", choices=["auto", "t2v", "ti2v22", "i2v", "vace", "custom"])
    s.add_argument("--local-profile", default=None)
    s.add_argument("--workflow", default=None)
    s.add_argument("--seed", type=int, default=-1)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_character.py"), "batch", "--profile", a.profile, "--mode", a.mode, "--seed", str(a.seed)] + (["--workflow", a.workflow] if a.workflow else []) + (["--tier", a.tier] if a.tier else []) + (["--actions", a.actions] if a.actions else []) + (["--directions", a.directions] if a.directions else []) + (["--local-profile", a.local_profile] if a.local_profile else []) + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("export-atlas", help="Export TexturePacker/Phaser/PixiJS/Aseprite/CSS/XML atlas metadata")
    s.add_argument("--sprite-dir", required=True)
    s.add_argument("--format", required=True, choices=["texturepacker", "phaser", "pixijs", "aseprite", "css", "xml"])
    s.add_argument("--output", default=None)
    s.add_argument("--copy-image", action="store_true")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_pack_formats.py"), "export", "--sprite-dir", a.sprite_dir, "--format", a.format] + (["--output", a.output] if a.output else []) + (["--copy-image"] if a.copy_image else [])))

    s = sub.add_parser("export-animation", help="Export APNG, animated WebP, or bitmap-backed Lottie animation")
    s.add_argument("--sprite-dir", required=True)
    s.add_argument("--format", required=True, choices=["apng", "webp", "lottie"])
    s.add_argument("--output", default=None)
    s.add_argument("--quality", type=int, default=85)

    def _export_animation(a):
        from services.animated_export_service import export_animation
        result = export_animation(Path(a.sprite_dir), a.format, Path(a.output) if a.output else None, quality=a.quality)
        print(json.dumps(result, indent=2))

    s.set_defaults(func=_export_animation)

    s = sub.add_parser("export-skeletal", help="Export segmented sprite parts as Spine/DragonBones-style JSON")
    s.add_argument("--sprite-dir", required=True)
    s.add_argument("--output", default=None)
    s.add_argument("--name", default="")

    def _export_skeletal(a):
        from services.skeletal_export_service import export_skeletal_parts
        result = export_skeletal_parts(Path(a.sprite_dir), Path(a.output) if a.output else None, name=a.name)
        print(json.dumps(result, indent=2))

    s.set_defaults(func=_export_skeletal)

    s = sub.add_parser("ci-check", help="CI quality-gate check")
    s.add_argument("--fail-under", type=float, default=95.0)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "app" / "services" / "ci_check_service.py"), "--fail-under", str(a.fail_under)]))
