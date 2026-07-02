#!/usr/bin/env python3
"""Web helper functions for SpriteForge Studio modular blueprints."""
from __future__ import annotations

import datetime as dt
import json
import math
import mimetypes
import os
import shutil
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Sequence

from services.config_service import ConfigService
from services.comfy_service import ComfyService
from services.model_service import ModelService
from services.job_service import JobService
from services.sprite_service import SpriteService
from services.export_service import ExportService
from services.experiment_service import ExperimentService
from services.project_service import ProjectService
from services.preview_manifest_service import build_frame_manifest
from services.audio_cue_service import load_audio_cues
from services.advisor_service import advise as advisor_advise
from services.generation_intelligence import (
    cleanup_suggestions,
    estimate_job_eta,
    explain_model_profile,
    mark_review_decision,
    preflight_generation,
    rerun_similar_payload,
    safer_retry_payload,
    summarize_qa_gates,
)
from spriteforge_utils import load_json, save_json, app_python, PYTHON, safe_name

# Re-exports from split helper services
from services.web_helpers_ab import (
    _ab_run_create as _ab_run_create_raw,
    _ab_run_list,
    _experiment_rows,
    _matching_experiment,
)
from services.web_helpers_versions import (
    _sprite_version_save,
    _sprite_version_list,
    _sprite_version_rollback,
)
from services.web_helpers_assets import (
    _list_queues,
    _list_releases,
    _list_packs,
    _list_quality_reports,
    _list_references,
    _list_planning_assets,
    _project_asset_counts,
    _sprite_search_roots,
    sprite_outputs,
    sprite_preview_bundle,
    _qa_batch_summary,
    _project_workspace,
    _resolve_queue_path,
    _resolve_sprite_output_dir,
    _get_failed_reason,
    _queue_job_progress,
    _queue_progress,
    _library_list,
    _library_save,
    _library_delete,
)
from services.web_helpers_cmd import (
    build_action_command,
    launch_detached,
    open_local_path,
    _project_artifact_path,
    _comfy_output_root,
    _safe_preview_file,
)

def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT / "projects"
WEB = ROOT / "web"
OUTPUT = ROOT / "output"
INPUT = ROOT / "input"
UPLOADS = INPUT / "uploaded_videos"
LOGS = ROOT / "logs"
CONFIG = ROOT / "config" / "spriteforge_config.json"
AB_RUNS_PATH = OUTPUT / "experiments" / "ab_runs.json"
VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
AUDIO_SUFFIXES = {".mp3", ".wav", ".ogg", ".m4a", ".flac"}
ALLOWED_SUBDIRS = {"output", "input", "projects", "releases", "workflows", "examples"}

DEFAULT_PRESETS = {
    "Classic Platformer (Side-Scroller)": {
        "character": "single full body platformer hero, professional appealing character design, heroic adult proportions, side view, distinctive outfit, boots, clean silhouette",
        "style": "pixel-art inspired game sprite, strong shape language, clean silhouette, cohesive palette",
        "tier": "wan22_5b",
        "profile": "wan22_5b_3060_best",
        "fps": "12",
        "cell_size": "512x512",
        "default_actions": "idle,walk,run,jump,hurt",
        "default_directions": "left,right",
        "negative": "camera movement, zoom, cuts, rotation, background details, childlike drawing, amateur doodle, crude sketch, bad anatomy, muddy colors",
        "qa_threshold_loop_rmse": "15.0",
        "qa_threshold_foot_drift": "2.0",
        "qa_threshold_center_drift": "5.0"
    },
    "Top-Down RPG Character": {
        "character": "single full body RPG adventurer, professional appealing character design, heroic adult proportions, distinctive outfit, top-down view, crisp details",
        "style": "polished 2D game sprite, professional character design, crisp silhouette, consistent outfit",
        "tier": "wan22_5b",
        "profile": "wan22_5b_3060_best",
        "fps": "12",
        "cell_size": "512x512",
        "default_actions": "idle,walk,attack_light,hurt,death",
        "default_directions": "front,back,left,right",
        "negative": "camera movement, zoom, cuts, rotation, shadow on floor, childlike drawing, amateur doodle, crude sketch, bad anatomy, muddy colors",
        "qa_threshold_loop_rmse": "18.0",
        "qa_threshold_foot_drift": "3.0",
        "qa_threshold_center_drift": "8.0"
    },
    "Animated Water Tile": {
        "character": "seamless top-down flowing water tile texture, animated liquid surface, ripples, pixel art style",
        "style": "clean tilemap tile, seamless looping, vibrant colors, clear fluid motion",
        "tier": "wan22_5b",
        "profile": "wan22_5b_3060_best",
        "fps": "8",
        "cell_size": "256x256",
        "default_actions": "flow",
        "default_directions": "down",
        "negative": "camera movement, perspective tilt, 3D orthographic view, black borders, non-looping seam",
        "qa_threshold_loop_rmse": "10.0",
        "qa_threshold_foot_drift": "999.0",
        "qa_threshold_center_drift": "999.0"
    },
    "Animated Lava Tile": {
        "character": "seamless top-down bubbling lava tile texture, animated magma surface, glowing veins, pixel art style",
        "style": "clean tilemap tile, seamless looping, red and orange embers, slow thick fluid motion",
        "tier": "wan22_5b",
        "profile": "wan22_5b_3060_best",
        "fps": "6",
        "cell_size": "256x256",
        "default_actions": "bubble",
        "default_directions": "still",
        "negative": "camera movement, perspective tilt, 3D orthographic view, black borders, non-looping seam",
        "qa_threshold_loop_rmse": "10.0",
        "qa_threshold_foot_drift": "999.0",
        "qa_threshold_center_drift": "999.0"
    },
    "Isometric RPG Character": {
        "character": "single full body isometric RPG adventurer, professional appealing character design, heroic adult proportions, distinctive outfit, isometric 2.5D view angled at 30 degrees, crisp details",
        "style": "polished 2D isometric game sprite, professional character design, crisp silhouette, consistent outfit, isometric angle projection",
        "tier": "wan22_5b",
        "profile": "wan22_5b_3060_best",
        "fps": "12",
        "cell_size": "512x512",
        "default_actions": "idle,walk,attack_light,hurt,death",
        "default_directions": "iso_front_left,iso_front_right,iso_back_left,iso_back_right",
        "negative": "camera movement, zoom, cuts, rotation, perspective tilt, 3D orthographic view, black borders, childlike drawing, amateur doodle, crude sketch, bad anatomy, muddy colors",
        "qa_threshold_loop_rmse": "18.0",
        "qa_threshold_foot_drift": "3.0",
        "qa_threshold_center_drift": "8.0"
    }
}

def _get_presets() -> Dict[str, Any]:
    presets = dict(DEFAULT_PRESETS)
    user_presets_path = ROOT / "config" / "user_presets.json"
    if user_presets_path.exists():
        user_presets = load_json(user_presets_path, {})
        presets.update(user_presets)
    return presets

def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")



def _ab_run_create(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _ab_run_create_raw(payload, build_action_command)

def _project_meta_from_query(query: Dict[str, List[str]]) -> Optional[Dict[str, str]]:
    project_value = (query.get("project") or [""])[0]
    if project_value:
        return ProjectService.metadata_for_path(project_value)
    active = ProjectService.get_active_project()
    if active:
        return ProjectService.metadata_for_path(str(active.get("path") or ""))
    return None

def _sprite_edit_frames(sprite_dir_str: str, actions: List[Dict[str, Any]], new_fps: Optional[int]) -> Dict[str, Any]:
    # Lite editor repack helper delegation
    # (Since this is a heavy frame processing logic, let's keep it here or delegate)
    # Wait, let's keep it here because it uses job services and local commands.
    # It is about 70 LOC, keeping it keeps web_helpers.py self-contained for route actions.
    import math
    sprite_dir = _resolve_sprite_output_dir(sprite_dir_str)
    frames_dir = sprite_dir / "frames_processed"
    if not frames_dir.exists():
        raise FileNotFoundError("Processed frames directory not found. Lite Editor requires frames_processed directory.")

    frame_files = sorted(list(frames_dir.glob("*.png")))
    temp_dir = sprite_dir / "temp_edit_frames"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)

    current_frames = list(frame_files)

    for act in actions:
        atype = act.get("type")
        if atype == "delete":
            indices = set(act.get("indices") or [])
            current_frames = [f for idx, f in enumerate(current_frames) if idx not in indices]
        elif atype == "hold":
            idx = int(act.get("index"))
            count = int(act.get("count", 1))
            if 0 <= idx < len(current_frames):
                frame_to_hold = current_frames[idx]
                current_frames = current_frames[:idx] + [frame_to_hold] * (count + 1) + current_frames[idx+1:]
        elif atype == "reorder":
            mapping = act.get("mapping")
            if mapping:
                current_frames = [current_frames[i] for i in mapping if 0 <= i < len(current_frames)]
        elif atype == "trim":
            start = int(act.get("start", 0))
            end = int(act.get("end", len(current_frames)))
            current_frames = current_frames[start:end]

    for idx, f in enumerate(current_frames):
        shutil.copy2(f, temp_dir / f"frame_{idx:04d}.png")

    shutil.rmtree(frames_dir)
    shutil.copytree(temp_dir, frames_dir)
    shutil.rmtree(temp_dir)

    meta_file = sprite_dir / "sheet.json"
    meta = load_json(meta_file, {})
    if new_fps:
        meta["fps"] = float(new_fps)

    new_count = len(current_frames)
    meta["frame_count"] = new_count

    cols = int(meta.get("columns", 4))
    rows = int(math.ceil(new_count / cols))
    meta["columns"] = cols
    meta["rows"] = rows

    save_json(meta_file, meta)

    cmd = [
        sys.executable, "spriteforge.py", "pack",
        "--input", str(frames_dir),
        "--output", str(sprite_dir),
        "--fps", str(meta["fps"]),
        "--cell-size", f"{meta.get('frame_width', 256)}x{meta.get('frame_height', 256)}",
        "--animation", str(meta.get("animation", "demo_idle")),
        "--anchor", str(meta.get("anchor", "bottom-center")),
        "--solidify", "0",
        "--preview-gif",
        "--report"
    ]

    ok, job_id_or_err = JobService.start_job(f"Repack edited frames: {sprite_dir.name}", cmd)
    return {"ok": ok, "job_id": job_id_or_err if ok else None, "message": "Repack job started." if ok else job_id_or_err}

def next_step_status() -> Dict[str, Any]:
    try:
        from spriteforge_final import recommended_next_step
        return recommended_next_step()
    except Exception as exc:
        return {"step": "Run Preflight", "reason": f"Could not compute recommendation: {exc}", "action": "final_preflight"}
