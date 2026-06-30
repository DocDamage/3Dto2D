#!/usr/bin/env python3
"""
SpriteForge Unified v12: local orchestrator for ComfyUI + WAN + sprite conversion.

This package delegates its command logic to spriteforge_commands.py, keeping this
orchestrator file under 500 lines of code. It remains fully compatible with CLI commands
and the integration test suite.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

# Expose globals and imports for tests (monkeypatch compatibility)
from spriteforge_commands import (
    ROOT,
    run,
    Config,
    load_config,
    cmd_status,
    cmd_doctor,
    cmd_install_spriteforge,
    cmd_install_all,
    cmd_install_comfy,
    cmd_install_nodes,
    cmd_install_manager,
    cmd_launch_comfy,
    cmd_open_comfy,
    cmd_submit_wan,
    cmd_generate_sprite,
    cmd_watch_output,
    cmd_convert_video,
    cmd_download_wan_native,
    cmd_model_report,
    cmd_model_tiers,
    cmd_download_model_tier,
    cmd_qa_report,
    cmd_open_model_pages,
    cmd_validate_workflow,
    cmd_queue_status,
    cmd_history
)

PRODUCTION_PASSTHROUGH = {
    "project-init", "batch-plan", "run-batch", "qa", "atlas", "export-atlas-engine", "lock-env"
}

FINAL_PASSTHROUGH = {
    "next-step": "next",
    "preflight": "preflight",
    "asset-dashboard": "dashboard",
    "release-package": "release",
    "open-latest": "latest",
}

QUEUE_PASSTHROUGH = {
    "queue-create": "create",
    "queue-run": "run",
    "queue-status": "status",
    "queue-reset": "reset",
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Unified ComfyUI + WAN + SpriteForge tool v12")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("status")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("doctor", help="Run system, ComfyUI, model, node, and workflow diagnostics")
    s.add_argument("--manifest", default="model_manifests/wan21_t2v_1_3b_native.json")
    s.add_argument("--workflow", default=None)
    s.add_argument("--profile", default="auto")
    s.add_argument("--tier", default="wan21_safe")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("install-spriteforge", help="Install SpriteForge local Python dependencies")
    s.add_argument("--python", default="3.12")
    s.set_defaults(func=cmd_install_spriteforge)

    s = sub.add_parser("install-all", help="Install/update SpriteForge, ComfyUI, WAN nodes, Manager, and selected WAN model tier")
    s.add_argument("--python", default="3.12")
    s.add_argument("--torch-index", default="cu126", choices=["cu130", "cu126", "cu121"])
    s.add_argument("--skip-torch", action="store_true")
    s.add_argument("--model-tier", default="safe", help="safe/recommended=Wan2.1 1.3B, advanced=Wan2.1+Wan2.2 5B, wan22_only=only Wan2.2 5B, cloud=no local model download")
    s.add_argument("--manifest", default=None, help="Legacy/manual manifest override. Usually leave empty and use --model-tier.")
    s.add_argument("--force-models", action="store_true")
    s.add_argument("--allow-heavy-models", action="store_true", help="Allow cloud/heavy manifests if explicitly requested")
    s.add_argument("--skip-models", action="store_true", help="Install ComfyUI/nodes but do not download WAN weights")
    s.add_argument("--skip-doctor", action="store_true")
    s.add_argument("--skip-hardware-apply", action="store_true")
    s.add_argument("--snapshot", action="store_true", help="Create a rollback snapshot before updating ComfyUI/custom nodes")
    s.set_defaults(func=cmd_install_all)

    s = sub.add_parser("install-comfy", help="Install/update ComfyUI and optionally WAN/video nodes")
    s.add_argument("--python", default="3.12")
    s.add_argument("--torch-index", default="cu130", choices=["cu130", "cu126", "cu121"])
    s.add_argument("--skip-torch", action="store_true")
    s.add_argument("--nodes", action="store_true", help="Also install WanVideoWrapper and VideoHelperSuite")
    s.add_argument("--manager", action="store_true", help="Also install ComfyUI Manager into custom_nodes/comfyui-manager")
    s.set_defaults(func=cmd_install_comfy)

    s = sub.add_parser("install-nodes", help="Install/update WAN and video helper ComfyUI custom nodes")
    s.add_argument("--manager", action="store_true")
    s.set_defaults(func=cmd_install_nodes)

    s = sub.add_parser("install-manager", help="Install/update ComfyUI Manager")
    s.set_defaults(func=cmd_install_manager)

    s = sub.add_parser("launch-comfy", help="Launch ComfyUI")
    s.add_argument("extra", nargs=argparse.REMAINDER, help="Extra args passed to ComfyUI main.py")
    s.set_defaults(func=cmd_launch_comfy)

    s = sub.add_parser("open-comfy")
    s.set_defaults(func=cmd_open_comfy)

    def add_wan_args(s: argparse.ArgumentParser) -> None:
        s.add_argument("--workflow", default=None)
        s.add_argument("--tier", default=None, help="Model tier: wan21_safe, wan22_5b, or wan22_14b_cloud. Defaults to config default_model_tier. Aliases: safe, advanced, cloud.")
        s.add_argument("--mode", default="auto", choices=["auto", "t2v", "ti2v22", "i2v", "vace", "custom"], help="WAN mode. auto chooses the mode from --tier.")
        s.add_argument("--profile", default="auto", help="WAN preset. auto uses the profile recommended by --tier.")
        s.add_argument("--prompt", required=False)
        s.add_argument("--negative", default=None)
        s.add_argument("--action", default=None, help="Build prompt from sprite action: idle, walk, run, attack_light, attack_heavy, cast, jump, hurt, death")
        s.add_argument("--direction", default="right", help="Prompt direction: front, back, left, right, three_quarter")
        s.add_argument("--character", default=None, help="Character description used by automatic prompt builder")
        s.add_argument("--style", default=None)
        s.add_argument("--background", default=None)
        s.add_argument("--extra-prompt", default=None)
        s.add_argument("--reference-image", default=None, help="Image-to-video/reference image path. Patched into common LoadImage nodes.")
        s.add_argument("--clip-vision", default=None, help="CLIP vision model for I2V, default from config")
        s.add_argument("--pose-action", default=None, help="Generate a posepack for this action and attach/patch it when workflow supports pose input")
        s.add_argument("--pose-direction", default=None)
        s.add_argument("--pose-frames", type=int, default=None)
        s.add_argument("--pose-size", type=int, default=512)
        s.add_argument("--posepack", default=None, help="Existing posepack folder to attach/patch into a custom pose workflow")
        s.add_argument("--model", default=None)
        s.add_argument("--text-encoder", default=None)
        s.add_argument("--vae", default=None)
        s.add_argument("--width", type=int, default=None)
        s.add_argument("--height", type=int, default=None)
        s.add_argument("--frames", type=int, default=None)
        s.add_argument("--video-fps", type=int, default=None)
        s.add_argument("--steps", type=int, default=None)
        s.add_argument("--cfg", type=float, default=None)
        s.add_argument("--shift", type=float, default=None)
        s.add_argument("--sampler", default=None)
        s.add_argument("--scheduler", default=None)
        s.add_argument("--seed", type=int, default=-1)
        s.add_argument("--output-prefix", default=None)
        s.add_argument("--resolutions", default=None)
        s.add_argument("--preview", action="store_true")
        s.add_argument("--style-image", default=None)
        s.add_argument("--batch-size", type=int, default=None, help="VRAM fallback hint for workflows with batch controls")
        s.add_argument("--vram-fallback", default=None, help="Internal retry hint: fp8, batch, resolution, or cpu_offload")
        s.add_argument("--cpu-offload", default=None, help="Internal retry hint for CPU/offload mode")

    s = sub.add_parser("submit-wan", help="Submit the included native Wan 2.1 T2V API workflow to a running ComfyUI server")
    add_wan_args(s)
    s.set_defaults(func=cmd_submit_wan)

    s = sub.add_parser("generate-sprite", help="Submit Wan job, wait for exact ComfyUI history output, then convert to spritesheet")
    add_wan_args(s)
    s.add_argument("--start-comfy", action="store_true")
    s.add_argument("--stop-comfy", action="store_true")
    s.add_argument("--timeout", type=float, default=3600)
    s.add_argument("--comfy-timeout", type=float, default=180)
    s.add_argument("--poll-seconds", type=float, default=5)
    s.add_argument("--stable-seconds", type=float, default=5)
    s.add_argument("--no-history", action="store_true", help="Skip prompt_id /history tracking and use folder scan only")
    s.add_argument("--no-folder-fallback", action="store_true", help="Fail if prompt history does not resolve a usable output")
    s.add_argument("--quality-check", action="store_true", help="Run SpriteForge QC after converting the generated video")
    s.add_argument("--cell-size", default=None)
    s.add_argument("--fps", type=float, default=None)
    s.add_argument("--key-color", default=None)
    s.add_argument("--qa-threshold-loop-rmse", type=float, default=None)
    s.add_argument("--qa-threshold-foot-drift", type=float, default=None)
    s.add_argument("--qa-threshold-center-drift", type=float, default=None)
    s.add_argument("--power-of-two", action="store_true", help="Pad final sheet to power-of-two dimensions")
    s.set_defaults(func=cmd_generate_sprite)

    s = sub.add_parser("watch-output", help="Watch ComfyUI output and convert new videos into sprites")
    s.add_argument("--folder", default=None)
    s.add_argument("--output", default=None)
    s.add_argument("--pattern", default="*.webm")
    s.add_argument("--fps", type=float, default=None)
    s.add_argument("--cell-size", default=None)
    s.add_argument("--key-color", default=None)
    s.add_argument("--key-tolerance", type=float, default=None)
    s.add_argument("--anchor", default=None)
    s.add_argument("--pad", type=int, default=None)
    s.add_argument("--solidify", type=int, default=None)
    s.set_defaults(func=cmd_watch_output)

    s = sub.add_parser("convert-video", help="Convert one existing video to sprites")
    s.add_argument("--input", required=True)
    s.add_argument("--output", default=None)
    s.add_argument("extra", nargs=argparse.REMAINDER)
    s.set_defaults(func=cmd_convert_video)

    s = sub.add_parser("download-wan-native", help="Download model files from a selected manifest")
    s.add_argument("--manifest", default="model_manifests/wan21_t2v_1_3b_native.json")
    s.add_argument("--force", action="store_true")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--allow-heavy", action="store_true")
    s.set_defaults(func=cmd_download_wan_native)

    s = sub.add_parser("download-model-tier", help="Download a named model tier: safe, advanced, wan22_only, cloud")
    s.add_argument("--tier", default="safe")
    s.add_argument("--force", action="store_true")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--allow-heavy", action="store_true")
    s.set_defaults(func=cmd_download_model_tier)

    s = sub.add_parser("model-tiers", help="List available model tiers and local file status")
    s.set_defaults(func=cmd_model_tiers)

    s = sub.add_parser("model-report", help="Check required model files")
    s.add_argument("--manifest", default="model_manifests/wan21_t2v_1_3b_native.json")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_model_report)

    s = sub.add_parser("open-model-pages")
    s.set_defaults(func=cmd_open_model_pages)

    s = sub.add_parser("validate-workflow", help="Validate API workflow JSON links and optionally node classes against running ComfyUI")
    s.add_argument("--workflow", default=None)
    s.add_argument("--profile", default="auto")
    s.add_argument("--tier", default="wan21_safe")
    s.add_argument("--check-nodes", action="store_true")
    s.set_defaults(func=cmd_validate_workflow)

    s = sub.add_parser("queue-status", help="Print ComfyUI queue/history summary")
    s.add_argument("--max-chars", type=int, default=8000)
    s.set_defaults(func=cmd_queue_status)

    s = sub.add_parser("history", help="Print one ComfyUI prompt history entry and resolved output files")
    s.add_argument("prompt_id")
    s.add_argument("--max-chars", type=int, default=12000)
    s.set_defaults(func=cmd_history)

    s = sub.add_parser("build-prompt", help="Build a sprite-action prompt without running WAN")
    s.add_argument("--action", required=True)
    s.add_argument("--direction", default="right")
    s.add_argument("--character", default=None)
    s.add_argument("--style", default=None)
    s.add_argument("--background", default=None)
    s.add_argument("--extra", default="")
    s.add_argument("--reference", action="store_true")
    s.add_argument("--pose-guided", action="store_true")
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_prompts.py"), "build", "--action", a.action, "--direction", a.direction] + (["--character", a.character] if a.character else []) + (["--style", a.style] if a.style else []) + (["--background", a.background] if a.background else []) + (["--extra", a.extra] if a.extra else []) + (["--reference"] if a.reference else []) + (["--pose-guided"] if a.pose_guided else []) + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("make-posepack", help="Generate OpenPose-style guide frames for a sprite action")
    s.add_argument("--action", required=True)
    s.add_argument("--direction", default="right")
    s.add_argument("--frames", type=int, default=None)
    s.add_argument("--size", type=int, default=512)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_prompts.py"), "posepack", "--action", a.action, "--direction", a.direction, "--size", str(a.size)] + (["--frames", str(a.frames)] if a.frames else []) + (["--output", a.output] if a.output else [])))

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

    s = sub.add_parser("snapshot", help="Snapshot ComfyUI/custom-node git revisions before updates")
    s.add_argument("--name", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_maintenance.py"), "snapshot"] + (["--name", a.name] if a.name else [])))

    s = sub.add_parser("safe-update", help="Snapshot first, then git-pull ComfyUI and optionally custom nodes")
    s.add_argument("--custom-nodes", action="store_true")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_maintenance.py"), "safe-update"] + (["--custom-nodes"] if a.custom_nodes else [])))

    s = sub.add_parser("rollback", help="Rollback ComfyUI/custom-node git repos to a saved snapshot")
    s.add_argument("--snapshot", required=True)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_maintenance.py"), "rollback", "--snapshot", a.snapshot] + (["--dry-run"] if a.dry_run else [])))

    s = sub.add_parser("quality-check", help="Run QC on one SpriteForge output folder")
    s.add_argument("--sprite-dir", required=True)
    s.add_argument("--output", default=None)
    s.add_argument("--fail-under", type=float, default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_quality.py"), "quality", "--sprite-dir", a.sprite_dir] + (["--output", a.output] if a.output else []) + (["--fail-under", str(a.fail_under)] if a.fail_under is not None else []), check=False))

    s = sub.add_parser("quality-batch", help="Run QC over every SpriteForge output folder under a root")
    s.add_argument("--root", default="output")
    s.add_argument("--output", default=None)
    s.add_argument("--fail-under", type=float, default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_quality.py"), "batch", "--root", a.root] + (["--output", a.output] if a.output else []) + (["--fail-under", str(a.fail_under)] if a.fail_under is not None else []), check=False))

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
        if a.character: cmd += ["--character", a.character]
        if a.style: cmd += ["--style", a.style]
        if a.actions: cmd += ["--actions", a.actions]
        if a.output: cmd += ["--output", a.output]
        if a.pose: cmd += ["--pose"]
        run(cmd)
    s.set_defaults(func=_prod)

    s = sub.add_parser("cloud-package", help="Package a GPU cloud job bundle")
    s.add_argument("--prompt", required=True)
    s.add_argument("--mode", default="t2v", choices=["t2v", "i2v", "vace", "custom"])
    s.add_argument("--profile", default="quality_local")
    s.add_argument("--reference-image", default=None)
    s.add_argument("--posepack", default=None)
    s.add_argument("--workflow", default=None)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_cloud.py"), "package", "--prompt", a.prompt, "--mode", a.mode, "--profile", a.profile] + (["--reference-image", a.reference_image] if a.reference_image else []) + (["--posepack", a.posepack] if a.posepack else []) + (["--workflow", a.workflow] if a.workflow else []) + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("cloud-plan", help="Write a cloud GPU setup plan without storing API keys")
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_cloud.py"), "runpod-plan"] + (["--output", a.output] if a.output else [])))

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
    s.add_argument("--mode", default="t2v", choices=["t2v", "i2v", "vace", "custom"])
    s.add_argument("--profile", default="rtx3060_12gb")
    s.add_argument("--seed", type=int, default=-1)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_character.py"), "create", "--name", a.name, "--description", a.description, "--style", a.style, "--background", a.background, "--actions", a.actions, "--directions", a.directions, "--mode", a.mode, "--profile", a.profile, "--seed", str(a.seed)] + (["--reference-image", a.reference_image] if a.reference_image else []) + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("batch-actions", help="Create a sequential generation batch from a character_profile.json")
    s.add_argument("--profile", required=True, help="Path to character_profile.json")
    s.add_argument("--actions", default=None)
    s.add_argument("--directions", default=None)
    s.add_argument("--mode", default="t2v", choices=["t2v", "i2v", "vace", "custom"])
    s.add_argument("--local-profile", default=None)
    s.add_argument("--seed", type=int, default=-1)
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_character.py"), "batch", "--profile", a.profile, "--mode", a.mode, "--seed", str(a.seed)] + (["--actions", a.actions] if a.actions else []) + (["--directions", a.directions] if a.directions else []) + (["--local-profile", a.local_profile] if a.local_profile else []) + (["--output", a.output] if a.output else [])))

    s = sub.add_parser("export-atlas", help="Export TexturePacker/Phaser/PixiJS/Aseprite/CSS/XML atlas metadata")
    s.add_argument("--sprite-dir", required=True)
    s.add_argument("--format", required=True, choices=["texturepacker", "phaser", "pixijs", "aseprite", "css", "xml"])
    s.add_argument("--output", default=None)
    s.add_argument("--copy-image", action="store_true")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_pack_formats.py"), "export", "--sprite-dir", a.sprite_dir, "--format", a.format] + (["--output", a.output] if a.output else []) + (["--copy-image"] if a.copy_image else [])))

    s = sub.add_parser("remote-generate", help="Submit to a remote ComfyUI server, download exact output, and optionally convert to sprite locally")
    s.add_argument("--server", required=True)
    s.add_argument("--workflow", required=True)
    s.add_argument("--prompt", required=True)
    s.add_argument("--negative", default=None)
    s.add_argument("--reference-image", default=None)
    s.add_argument("--width", type=int, default=None)
    s.add_argument("--height", type=int, default=None)
    s.add_argument("--frames", type=int, default=None)
    s.add_argument("--video-fps", type=int, default=None)
    s.add_argument("--seed", type=int, default=-1)
    s.add_argument("--output-prefix", default="SpriteForge/remote_sprite")
    s.add_argument("--output", default=None)
    s.add_argument("--timeout", type=float, default=7200)
    s.add_argument("--convert", action="store_true")
    s.add_argument("--cell-size", default="512x512")
    s.add_argument("--key-color", default="auto")
    s.add_argument("extra", nargs=argparse.REMAINDER)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_remote.py"), "generate", "--server", a.server, "--workflow", a.workflow, "--prompt", a.prompt, "--output-prefix", a.output_prefix, "--timeout", str(a.timeout), "--cell-size", a.cell_size, "--key-color", a.key_color, "--seed", str(a.seed)] + (["--negative", a.negative] if a.negative else []) + (["--reference-image", a.reference_image] if a.reference_image else []) + (["--width", str(a.width)] if a.width else []) + (["--height", str(a.height)] if a.height else []) + (["--frames", str(a.frames)] if a.frames else []) + (["--video-fps", str(a.video_fps)] if a.video_fps else []) + (["--output", a.output] if a.output else []) + (["--convert"] if a.convert else []) + (a.extra or [])))

    s = sub.add_parser("hardware-advisor", help="Read nvidia-smi and recommend local/cloud WAN and sprite defaults")
    s.add_argument("--apply", action="store_true", help="Back up config and apply recommended sprite defaults")
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_hardware.py"), "apply"] if a.apply else [sys.executable, str(ROOT / "spriteforge_hardware.py"), "report"] + (["--output", a.output] if a.output else [])))

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    # Route rich subtools before argparse consumes their --flags.
    if argv and argv[0] in FINAL_PASSTHROUGH:
        mapped = FINAL_PASSTHROUGH[argv[0]]
        try:
            return run([sys.executable, str(ROOT / "spriteforge_final.py"), mapped] + argv[1:]).returncode
        except KeyboardInterrupt:
            print("Stopped.", file=sys.stderr)
            return 130
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    if argv and argv[0] in QUEUE_PASSTHROUGH:
        mapped = QUEUE_PASSTHROUGH[argv[0]]
        try:
            return run([sys.executable, str(ROOT / "spriteforge_queue.py"), mapped] + argv[1:]).returncode
        except KeyboardInterrupt:
            print("Stopped.", file=sys.stderr)
            return 130
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    if argv and argv[0] in PRODUCTION_PASSTHROUGH:
        try:
            return run([sys.executable, str(ROOT / "spriteforge_production.py")] + argv).returncode
        except KeyboardInterrupt:
            print("Stopped.", file=sys.stderr)
            return 130
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
