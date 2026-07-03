import os
import sys
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Sequence

from services.project_service import ProjectService
from services.config_service import ConfigService
from spriteforge_utils import (
    PYTHON, ALLOWED_SUBDIRS, VIDEO_SUFFIXES, IMAGE_SUFFIXES, AUDIO_SUFFIXES,
    safe_name
)
from services.web_path_proxy import ROOT, OUTPUT, INPUT, UPLOADS

def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False

def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")



def _comfy_output_root() -> Path:
    cfg = ConfigService.get_config()
    raw = cfg.get("paths", {}).get("comfyui_output", "vendor/ComfyUI/output") if isinstance(cfg, dict) else "vendor/ComfyUI/output"
    path = Path(str(raw))
    return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()

def _safe_preview_file(path: Path) -> bool:
    resolved = path.resolve()
    root = ROOT.resolve()
    if not _is_relative_to(resolved, root):
        return False
    try:
        rel_parts = resolved.relative_to(root).parts
    except ValueError:
        return False
    if rel_parts and rel_parts[0] in ALLOWED_SUBDIRS:
        return True
    return _is_relative_to(resolved, _comfy_output_root())

def _resolve_existing_file(value: str) -> Optional[Path]:
    if not value:
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    candidate = candidate.resolve()
    return candidate if candidate.exists() and candidate.is_file() and _safe_preview_file(candidate) else None

def _pixel_animate_workflow_path() -> Optional[str]:
    candidates = [
        ROOT / "vendor" / "ComfyUI" / "models" / "workflows" / "wan2-2-video.json",
        ROOT / "workflows" / "wan2-2-video.json",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    return None

def _project_artifact_path(project_meta: Dict[str, str], folder: str, name: str) -> Path:
    project_root = (ROOT / str(project_meta["project_root"])).resolve()
    projects_root = (ROOT / "projects").resolve()
    if not _is_relative_to(project_root, projects_root):
        raise ValueError("Project root must be inside projects.")
    return project_root / folder / safe_name(name)


def _sprite_polish_args(payload: Dict[str, Any]) -> List[str]:
    args: List[str] = []
    for key, arg in [
        ("matting_engine", "--matting-engine"),
        ("alpha_refine_radius", "--alpha-refine-radius"),
        ("temporal_alpha_strength", "--temporal-alpha-strength"),
        ("pixel_cleanup_colors", "--pixel-cleanup-colors"),
        ("pixel_cleanup_palette", "--pixel-cleanup-palette"),
        ("pixel_cleanup_dither_mode", "--pixel-cleanup-dither-mode"),
        ("interpolate_fps", "--interpolate-fps"),
        ("interpolation_engine", "--interpolation-engine"),
        ("interpolation_skip_patterns", "--interpolation-skip-patterns"),
        ("normal_map_engine", "--normal-map-engine"),
        ("pack_mode", "--pack-mode"),
        ("segment_parts", "--segment-parts"),
    ]:
        value = str(payload.get(key) if payload.get(key) is not None else "").strip()
        if value:
            args += [arg, value]
    for key, arg in [
        ("alpha_refine", "--alpha-refine"),
        ("temporal_alpha_stabilize", "--temporal-alpha-stabilize"),
        ("pixel_cleanup", "--pixel-cleanup"),
        ("pixel_cleanup_dither", "--pixel-cleanup-dither"),
        ("interpolation_skip_pixel_art", "--interpolation-skip-pixel-art"),
        ("interpolation_skip_impact_frames", "--interpolation-skip-impact-frames"),
        ("generate_normal_maps", "--generate-normal-maps"),
    ]:
        if payload.get(key):
            args.append(arg)
    return args


def build_action_command(payload: Dict[str, Any]) -> Tuple[str, List[str]]:
    action = str(payload.get("action") or "")
    project_meta = ProjectService.metadata_for_path(str(payload.get("active_project") or "")) or {}
    if project_meta:
        payload.update(project_meta)
    table = {
        "install_all": ("Install everything + safe Wan 2.1 models", [PYTHON, "spriteforge_unified.py", "install-all", "--model-tier", "safe"]),
        "install_advanced": ("Install safe Wan 2.1 + advanced Wan 2.2 5B", [PYTHON, "spriteforge_unified.py", "install-all", "--model-tier", "advanced"]),
        "install_deps": ("Install SpriteForge dependencies", [PYTHON, "-m", "pip", "install", "--upgrade", "pip", "-r", "requirements.txt"]),
        "install_comfy": ("Install / update ComfyUI + WAN nodes + safe models", [PYTHON, "spriteforge_unified.py", "install-all", "--model-tier", "safe", "--skip-doctor"]),
        "install_manager": ("Install / update ComfyUI Manager", [PYTHON, "spriteforge_unified.py", "install-manager"]),
        "download_models": ("Repair / re-check safe Wan 2.1 model download", [PYTHON, "spriteforge_unified.py", "download-model-tier", "--tier", "safe"]),
        "download_wan22": ("Download advanced Wan 2.2 TI2V 5B model files", [PYTHON, "spriteforge_unified.py", "download-model-tier", "--tier", "wan22_only"]),
        "model_tiers": ("Show WAN model tiers", [PYTHON, "spriteforge_unified.py", "model-tiers"]),
        "doctor": ("Run Doctor", [PYTHON, "spriteforge_unified.py", "doctor"]),
        "validate_workflow": ("Validate included WAN workflow", [PYTHON, "spriteforge_unified.py", "validate-workflow", "--check-nodes"]),
        "hardware": ("Hardware Advisor", [PYTHON, "spriteforge_unified.py", "hardware-advisor"]),
        "demo": ("Make no-GPU demo sprite", [PYTHON, "spriteforge_demo.py"]),
        "support_bundle": ("Collect support bundle", [PYTHON, "spriteforge_support_bundle.py"]),
        "snapshot": ("Snapshot ComfyUI", [PYTHON, "spriteforge_unified.py", "snapshot", "--name", str(payload.get("label") or "web-ui")]),
        "safe_update": ("Safe update ComfyUI", [PYTHON, "spriteforge_unified.py", "safe-update", "--custom-nodes"]),
        "final_preflight": ("Final preflight report", [PYTHON, "spriteforge_unified.py", "preflight"]),
        "asset_dashboard": ("Build asset dashboard", [PYTHON, "spriteforge_unified.py", "asset-dashboard"]),
        "open_latest": ("Open latest sprite output", [PYTHON, "spriteforge_unified.py", "open-latest"]),
    }
    if action in table:
        return table[action]
    if action == "training_dataset":
        source = str(payload.get("source_dir") or payload.get("source") or "").strip()
        if not source:
            raise ValueError("No source sprite folder selected.")
        output = str(payload.get("output") or payload.get("dataset_output") or "").strip()
        trigger = str(payload.get("trigger") or "sakpix_style").strip()
        base_caption = str(payload.get("base_caption") or "premium pixel art RPG character").strip()
        cell_size = str(payload.get("cell_size") or "").strip()
        cmd = [
            PYTHON,
            "spriteforge_unified.py",
            "training-dataset",
            "--source",
            source,
        ]
        if output:
            cmd += ["--output", output]
        cmd += ["--trigger", trigger, "--base-caption", base_caption]
        if cell_size:
            cmd += ["--cell-size", cell_size]
        return "Build training dataset", cmd
    if action == "tile_training_dataset":
        source = str(payload.get("source_dir") or payload.get("source") or "").strip()
        if not source:
            raise ValueError("No tile-set source folder selected.")
        output = str(payload.get("output") or payload.get("dataset_output") or "").strip()
        trigger = str(payload.get("trigger") or "sakpix_tiles").strip()
        base_caption = str(payload.get("base_caption") or "premium top-down pixel art tileset").strip()
        cell_size = str(payload.get("cell_size") or "auto").strip()
        max_samples = str(payload.get("max_samples_per_source") or "32").strip()
        cmd = [
            PYTHON,
            "spriteforge_unified.py",
            "autotile-dataset",
            "--source",
            source,
        ]
        if output:
            cmd += ["--output", output]
        cmd += [
            "--trigger", trigger,
            "--base-caption", base_caption,
            "--cell-size", cell_size or "auto",
            "--max-samples-per-source", max_samples or "32",
        ]
        if payload.get("include_all"):
            cmd.append("--include-all")
        return "Build auto-tile training dataset", cmd
    if action == "lora_training":
        dataset = str(payload.get("dataset_dir") or payload.get("dataset") or "").strip()
        if not dataset:
            raise ValueError("No training dataset folder selected.")
        mode = str(payload.get("mode") or "prepare").strip().lower()
        run_now = mode == "run" or str(payload.get("run_now") or "").lower() in {"1", "true", "yes", "on"}
        cmd = [
            PYTHON,
            "spriteforge_unified.py",
            "lora-train",
            "--dataset",
            dataset,
        ]
        output = str(payload.get("output") or payload.get("run_output") or "").strip()
        if output:
            cmd += ["--output", output]
        for key, arg, default in [
            ("name", "--name", "sprite_lora"),
            ("model_family", "--model-family", "sdxl"),
            ("trainer", "--trainer", "auto"),
            ("base_model", "--base-model", ""),
            ("trigger", "--trigger", "sakpix_style"),
            ("resolution", "--resolution", "768"),
            ("max_train_steps", "--max-train-steps", "1200"),
            ("learning_rate", "--learning-rate", "1e-4"),
            ("network_dim", "--network-dim", "16"),
            ("repeats", "--repeats", "10"),
            ("batch_size", "--batch-size", ""),
            ("trainer_dir", "--trainer-dir", ""),
        ]:
            value = str(payload.get(key) if payload.get(key) is not None else default).strip()
            if value:
                cmd += [arg, value]
        if run_now:
            cmd.append("--run")
        title = "Start LoRA training run" if run_now else "Prepare LoRA training run"
        return title, cmd
    if action == "generate_sprite":
        cmd = [PYTHON, "spriteforge_unified.py", "generate-sprite"]
        if payload.get("start_comfy", True):
            cmd.append("--start-comfy")
        tier = str(payload.get("tier") or "wan22_5b")
        cmd += ["--tier", tier]
        mode = str(payload.get("mode") or "").strip()
        if mode:
            cmd += ["--mode", mode]
        cmd += ["--profile", str(payload.get("profile") or "auto")]
        if not payload.get("workflow") and payload.get("existing_sprite_model") == "pixel_animate_14b":
            workflow = _pixel_animate_workflow_path()
            if workflow:
                payload["workflow"] = workflow
        for key, arg in [("workflow", "--workflow"), ("sprite_action", "--action"), ("direction", "--direction"), ("character", "--character"), ("style", "--style"), ("background", "--background"), ("prompt", "--prompt"), ("negative", "--negative"), ("reference_image", "--reference-image"), ("seed", "--seed"), ("output_prefix", "--output-prefix"), ("lora_name", "--lora-name")]:
            value = str(payload.get(key) if payload.get(key) is not None else "").strip()
            if value:
                cmd += [arg, value]

        # Support preview flag
        if payload.get("preview", False):
            cmd.append("--preview")

        # Support style reference image (IP-Adapter)
        if payload.get("style_image"):
            cmd += ["--style-image", str(payload.get("style_image"))]

        # Forward custom preset builder parameters
        for key, arg in [
            ("fps", "--fps"),
            ("cell_size", "--cell-size"),
            ("key_color", "--key-color"),
            ("resolutions", "--resolutions"),
            ("qa_threshold_loop_rmse", "--qa-threshold-loop-rmse"),
            ("qa_threshold_foot_drift", "--qa-threshold-foot-drift"),
            ("qa_threshold_center_drift", "--qa-threshold-center-drift")
        ]:
            value = str(payload.get(key) or "").strip()
            if value:
                cmd += [arg, value]
        if payload.get("quality_check", True):
            cmd.append("--quality-check")
        if payload.get("power_of_two", False):
            cmd.append("--power-of-two")
        cmd += _sprite_polish_args(payload)
        return "Generate WAN sprite", cmd
    if action == "animate_existing_sprite":
        source = str(payload.get("source_sprite") or payload.get("existing_sprite_source") or payload.get("reference_image") or "").strip()
        if not source:
            raise ValueError("No source sprite image selected.")
        name_seed = str(payload.get("existing_sprite_name") or payload.get("name") or Path(source).stem or "existing_sprite")
        name = safe_name(name_seed)
        description = str(payload.get("existing_sprite_description") or payload.get("character") or "single full body game sprite").strip()
        style = str(payload.get("style") or "polished 2D game sprite, preserve the uploaded source sprite identity, exact outfit, palette, proportions, and silhouette").strip()
        if "preserve" not in style.lower():
            style += ", preserve the uploaded source sprite identity, exact outfit, palette, proportions, and silhouette"
        actions = str(payload.get("existing_sprite_actions") or payload.get("default_actions") or payload.get("actions") or payload.get("sprite_action") or "idle,walk,run,attack_light,hurt,death").strip()
        directions = str(payload.get("existing_sprite_directions") or payload.get("default_directions") or payload.get("directions") or payload.get("direction") or "right").strip()
        tier = str(payload.get("tier") or "wan22_5b").strip()
        mode = str(payload.get("mode") or "auto").strip()
        profile = str(payload.get("profile") or "wan22_5b_3060_best").strip()
        background = str(payload.get("background") or "plain bright green chroma key background").strip()
        seed = str(payload.get("seed") or "-1").strip() or "-1"
        workflow = str(payload.get("workflow") or "").strip()
        if not workflow and payload.get("existing_sprite_model") == "pixel_animate_14b":
            workflow = _pixel_animate_workflow_path() or ""
        cmd = [
            PYTHON,
            "spriteforge_unified.py",
            "character-pack",
            "--name",
            name,
            "--description",
            description,
            "--reference-image",
            source,
            "--style",
            style,
            "--background",
            background,
            "--actions",
            actions,
            "--directions",
            directions,
            "--tier",
            tier,
            "--mode",
            mode,
            "--profile",
            profile,
            "--seed",
            seed,
        ]
        if workflow:
            cmd += ["--workflow", workflow]
        if project_meta:
            cmd += ["--output", str(_project_artifact_path(project_meta, "characters", name))]
        return f"Create animation pack for {name}", cmd
    if action == "convert_video":
        inp = str(payload.get("input") or "").strip()
        if not inp:
            raise ValueError("No input video selected.")
        cmd = [PYTHON, "spriteforge_unified.py", "convert-video", "--input", inp]
        out = str(payload.get("output") or "").strip()
        if not out and project_meta:
            out = str(_project_artifact_path(project_meta, "sprites", f"{Path(inp).stem}_sprite"))
        if out:
            cmd += ["--output", out]
        extra: List[str] = []
        for key, arg in [("fps", "--fps"), ("cell_size", "--cell-size"), ("key_color", "--key-color")]:
            value = str(payload.get(key) or "").strip()
            if value:
                extra += [arg, value]
        extra += _sprite_polish_args(payload)
        if payload.get("drop_loop_duplicate", True):
            extra.append("--drop-loop-duplicate")
        if payload.get("preview_gif", True):
            extra.append("--preview-gif")
        if payload.get("report", True):
            extra.append("--report")
        if payload.get("power_of_two", False):
            extra.append("--power-of-two")
        if extra:
            cmd += ["--"] + extra
        return "Convert video to spritesheet", cmd
    if action in {"qa_report", "autofix", "export_godot", "export_unity", "export_unreal"}:
        sprite_dir = str(payload.get("sprite_dir") or "").strip()
        if not sprite_dir:
            raise ValueError("No sprite output folder selected.")
        if action == "qa_report":
            cmd = [PYTHON, "spriteforge_unified.py", "qa-report", "--input", sprite_dir]
            if project_meta:
                cmd += ["--output", str(_project_artifact_path(project_meta, "quality", Path(sprite_dir).name))]
            return "Analyze sprite quality", cmd
        if action == "autofix":
            cmd = [PYTHON, "spriteforge_unified.py", "autofix-sprite", "--input", sprite_dir]

            def get_bool(key, default):
                val = payload.get(key)
                if val is None:
                    return default
                return bool(val)

            if get_bool("stabilize_anchor", True):
                cmd.append("--stabilize-anchor")
            if get_bool("drop_loop_duplicate", True):
                cmd.append("--drop-loop-duplicate")
            if get_bool("deflicker", True):
                cmd.append("--deflicker")
            if get_bool("sharpen", False):
                cmd.append("--sharpen")

            solidify = payload.get("solidify")
            if solidify is None:
                solidify = 2
            cmd += ["--solidify", str(solidify)]

            blend = payload.get("blend_loop_frames")
            if blend is None:
                blend = 3
            cmd += ["--blend-loop-frames", str(blend)]

            if project_meta:
                cmd += ["--output", str(_project_artifact_path(project_meta, "sprites", f"{Path(sprite_dir).name}_fixed"))]
            return "Auto-fix sprite output", cmd

        # Determine engine
        if action == "export_godot":
            engine = "godot"
        elif action == "export_unity":
            engine = "unity"
        else:
            engine = "unreal"

        cmd = [PYTHON, "spriteforge_unified.py", "export-engine", "--engine", engine, "--sprite-dir", sprite_dir]
        if project_meta:
            cmd += ["--output", str(_project_artifact_path(project_meta, "exports", f"{Path(sprite_dir).name}_{engine}"))]
        for key, arg in [
            ("export_naming", "--naming-convention"),
            ("export_pivot", "--pivot-mode"),
            ("export_ppu", "--ppu"),
            ("export_filter", "--filter-mode"),
            ("export_loop_flag", "--loop-flag"),
            ("export_import_path", "--import-path"),
            ("export_clip_name", "--clip-name")
        ]:
            if key in payload:
                val = str(payload[key]).strip()
                if val:
                    cmd += [arg, val]
        return f"Export {engine.title()} helper", cmd
    if action == "character_pack":
        name = safe_name(str(payload.get("name") or "hero"))
        cmd = [
            PYTHON,
            "spriteforge_unified.py",
            "pack-init",
            "--name",
            name,
            "--character",
            str(payload.get("description") or "single full body platformer hero, professional character design"),
            "--actions",
            str(payload.get("actions") or "idle,walk,run,attack_light,hurt"),
            "--directions",
            str(payload.get("directions") or "right"),
            "--pose-guided",
            "--posepacks",
        ]
        if project_meta:
            cmd += ["--output", str(ROOT / project_meta["project_root"])]
        return "Create character production pack", cmd
    if action == "atlas":
        sprites = payload.get("sprites") or []
        if isinstance(sprites, str):
            sprites = [s.strip() for s in sprites.splitlines() if s.strip()]
        if not sprites:
            raise ValueError("No sprite outputs selected for atlas.")
        name = safe_name(str(payload.get("name") or "character"))
        output = str(payload.get("output") or "").strip()
        if not output:
            output = str(_project_artifact_path(project_meta, "exports", f"{name}_atlas")) if project_meta else f"output/{name}_atlas"
        return "Build multi-action atlas", [PYTHON, "spriteforge_unified.py", "atlas-build", "--sprites", *list(sprites), "--output", output, "--name", name]
    if action == "release_package":
        sprites = payload.get("sprites") or payload.get("sprite_dir") or []
        if isinstance(sprites, str):
            sprites = [s.strip() for s in sprites.splitlines() if s.strip()]
        if not sprites:
            raise ValueError("No sprite outputs selected for release package.")
        name = safe_name(str(payload.get("name") or "sprite_release"))
        cmd = [PYTHON, "spriteforge_unified.py", "release-package", "--name", name, "--zip"]
        if project_meta:
            cmd += ["--project", str(ROOT / project_meta["project_path"])]
            if not str(payload.get("output") or "").strip():
                cmd += ["--output", str(ROOT / project_meta["project_root"] / "releases" / name)]
        for sprite in sprites:
            cmd += ["--sprite-dir", sprite]
        return "Build release package", cmd
    if action == "queue_create":
        name = safe_name(str(payload.get("name") or "character"))
        project_path = ProjectService.resolve_project_path(str(payload.get("active_project") or ""))
        cmd = [PYTHON, "spriteforge_unified.py", "queue-create"]
        if project_path:
            cmd += ["--project", str(project_path)]
        cmd += ["--name", name, "--character", str(payload.get("description") or "single full body platformer hero"), "--actions", str(payload.get("actions") or "idle,walk,run"), "--directions", str(payload.get("directions") or "right"), "--tier", str(payload.get("tier") or "wan22_5b"), "--profile", str(payload.get("profile") or "wan22_5b_3060_best")]
        return "Create persistent production queue", cmd
    if action == "validate_export":
        sprite_dir = str(payload.get("sprite_dir") or "").strip()
        if not sprite_dir:
            raise ValueError("No sprite output folder selected.")
        engine = str(payload.get("engine") or "").strip() or None
        cmd = [PYTHON, "spriteforge_engine_export.py", "validate", "--sprite-dir", sprite_dir]
        if engine:
            cmd += ["--engine", engine]
        return "Validate export files", cmd
    raise ValueError(f"Unknown action: {action!r}")

def launch_detached(title: str, args: Sequence[str]) -> None:
    if os.name == "nt":
        subprocess.Popen(["cmd", "/c", "start", title, *list(args)], cwd=str(ROOT), shell=False)
    else:
        subprocess.Popen(list(args), cwd=str(ROOT))

def open_local_path(path: Path) -> None:
    from services.open_path_service import open_path
    open_path(path)
