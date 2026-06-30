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
from spriteforge_utils import load_json, save_json, app_python, PYTHON

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT / "projects"
AB_RUNS_PATH = ROOT / "output" / "experiments" / "ab_runs.json"
WEB = ROOT / "web"
OUTPUT = ROOT / "output"
INPUT = ROOT / "input"
UPLOADS = INPUT / "uploaded_videos"
LOGS = ROOT / "logs"
CONFIG = ROOT / "config" / "spriteforge_config.json"
VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
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
    }
}

def _get_presets() -> Dict[str, Any]:
    presets = dict(DEFAULT_PRESETS)
    user_presets_path = ROOT / "config" / "user_presets.json"
    if user_presets_path.exists():
        user_presets = load_json(user_presets_path, {})
        presets.update(user_presets)
    return presets

def _get_failed_reason(log_path_str: Optional[str]) -> Optional[str]:
    if not log_path_str:
        return None
    try:
        log_path = Path(log_path_str)
        if not log_path.is_absolute():
            log_path = ROOT / log_path
        if log_path.exists() and log_path.is_file():
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in reversed(lines):
                line = line.strip()
                if line:
                    return line
    except Exception:
        pass
    return None

def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")

def safe_name(value: str) -> str:
    cleaned = "".join(ch for ch in value.strip() if ch.isalnum() or ch in "._- ").strip().replace(" ", "_")
    return cleaned or "file"

def _sprite_version_save(sprite_dir_str: str, label: str) -> Dict[str, Any]:
    sprite_dir = _resolve_sprite_output_dir(sprite_dir_str)
    versions_dir = sprite_dir / ".versions"
    versions_dir.mkdir(exist_ok=True)
    vfile = versions_dir / "versions.json"
    data = load_json(vfile, {"versions": []})
    
    vid = f"v_{int(time.time())}"
    v_subdir = versions_dir / vid
    v_subdir.mkdir(exist_ok=True)
    
    # Copy files
    for name in ["sheet.png", "sheet.json", "preview.gif", "report.html", "qa_report.json", "quality_report.json"]:
        f = sprite_dir / name
        if f.exists():
            shutil.copy2(f, v_subdir / name)
            
    # Copy qa directory files
    qa_dir = sprite_dir / "qa"
    if qa_dir.exists():
        v_qa_dir = v_subdir / "qa"
        shutil.copytree(qa_dir, v_qa_dir, dirs_exist_ok=True)
            
    # Copy frames_processed
    frames_dir = sprite_dir / "frames_processed"
    if frames_dir.exists():
        v_frames_dir = v_subdir / "frames_processed"
        shutil.copytree(frames_dir, v_frames_dir, dirs_exist_ok=True)
        
    data["versions"].append({
        "id": vid,
        "label": label or f"Snapshot {len(data['versions'])+1}",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    data["active_version"] = vid
    save_json(vfile, data)
    return {"ok": True, "version_id": vid, "versions": data["versions"]}

def _sprite_version_list(sprite_dir_str: str) -> Dict[str, Any]:
    sprite_dir = _resolve_sprite_output_dir(sprite_dir_str)
    versions_dir = sprite_dir / ".versions"
    vfile = versions_dir / "versions.json"
    data = load_json(vfile, {"active_version": "current", "versions": []})
    
    # Load quality metrics for each version to display in trend graphs
    for v in data.get("versions", []):
        vid = v.get("id")
        v_subdir = versions_dir / vid
        qa_data = {}
        for p in ["qa/qa_report.json", "qa_report.json", "quality_report.json"]:
            p_path = v_subdir / p
            if p_path.exists():
                try:
                    qa_data = json.loads(p_path.read_text(encoding="utf-8"))
                    break
                except Exception:
                    pass
        v["metrics"] = qa_data.get("metrics", {}) if qa_data else {}
        
    return data

def _sprite_version_rollback(sprite_dir_str: str, vid: str) -> Dict[str, Any]:
    sprite_dir = _resolve_sprite_output_dir(sprite_dir_str)
    v_subdir = sprite_dir / ".versions" / vid
    if not v_subdir.exists():
        raise FileNotFoundError(f"Version backup {vid} not found.")
        
    # Copy files back
    for name in ["sheet.png", "sheet.json", "preview.gif", "report.html", "qa_report.json", "quality_report.json"]:
        f = v_subdir / name
        dest = sprite_dir / name
        if f.exists():
            shutil.copy2(f, dest)
        elif dest.exists():
            dest.unlink()
            
    # Copy qa back
    v_qa_dir = v_subdir / "qa"
    dest_qa_dir = sprite_dir / "qa"
    if v_qa_dir.exists():
        if dest_qa_dir.exists():
            shutil.rmtree(dest_qa_dir)
        shutil.copytree(v_qa_dir, dest_qa_dir)
        
    # Copy frames_processed back
    v_frames_dir = v_subdir / "frames_processed"
    dest_frames_dir = sprite_dir / "frames_processed"
    if v_frames_dir.exists():
        if dest_frames_dir.exists():
            shutil.rmtree(dest_frames_dir)
        shutil.copytree(v_frames_dir, dest_frames_dir)
        
    vfile = sprite_dir / ".versions" / "versions.json"
    data = load_json(vfile, {"versions": []})
    data["active_version"] = vid
    save_json(vfile, data)
    return {"ok": True, "active_version": vid}

def _ab_run_create(payload: Dict[str, Any]) -> Dict[str, Any]:
    import uuid
    ab_id = str(uuid.uuid4())
    name = str(payload.get("name") or f"A/B Run {time.strftime('%Y%m%d_%H%M%S')}")
    
    variant_a = payload.get("variant_a", {})
    variant_b = payload.get("variant_b", {})
    
    title_a, cmd_a = build_action_command(variant_a)
    title_b, cmd_b = build_action_command(variant_b)
    
    q_data = {
        "schema": "spriteforge_queue_v12",
        "name": name,
        "ab_id": ab_id,
        "project_name": payload.get("project_name", ""),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "jobs": [
            {
                "id": f"ab_{ab_id}_A",
                "action": variant_a.get("action", "generate_sprite"),
                "command": cmd_a,
                "status": "pending",
                "variant_label": "Variant A"
            },
            {
                "id": f"ab_{ab_id}_B",
                "action": variant_b.get("action", "generate_sprite"),
                "command": cmd_b,
                "status": "pending",
                "variant_label": "Variant B"
            }
        ]
    }
    
    q_dir = ROOT / "output" / "jobs"
    q_dir.mkdir(parents=True, exist_ok=True)
    q_path = q_dir / f"ab_run_{ab_id}_queue.json"
    save_json(q_path, q_data)
    
    runs = load_json(AB_RUNS_PATH, [])
    runs.insert(0, {
        "id": ab_id,
        "name": name,
        "project_name": payload.get("project_name", ""),
        "queue_path": str(q_path.relative_to(ROOT)).replace("\\", "/"),
        "variant_a": variant_a,
        "variant_b": variant_b,
        "created_at": q_data["created_at"]
    })
    save_json(AB_RUNS_PATH, runs)
    
    cmd = [sys.executable, "spriteforge_queue.py", "run", "--queue", str(q_path), "--continue-on-error"]
    ok, job_id_or_err = JobService.start_job(f"A/B Run Queue: {name}", cmd, metadata={"ab_id": ab_id})
    return {"ok": ok, "ab_id": ab_id, "job_id": job_id_or_err if ok else None, "message": "A/B Run queue started." if ok else job_id_or_err}

def _ab_run_list() -> List[Dict[str, Any]]:
    return load_json(AB_RUNS_PATH, [])

def _qa_batch_summary(project_meta: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    sprites = sprite_outputs(80, project_meta)
    summary_list = []
    
    for s in sprites:
        sprite_path_str = s.get("path")
        if not sprite_path_str:
            continue
        sprite_dir = ROOT / sprite_path_str
        name = sprite_dir.name
        
        qa_data = None
        for report_name in ["qa_report.json", "quality_report.json", "qa/qa_report.json"]:
            p = sprite_dir / report_name
            if p.exists():
                try:
                    qa_data = json.loads(p.read_text(encoding="utf-8"))
                    break
                except Exception:
                    pass
        
        metrics = qa_data.get("metrics", {}) if qa_data else {}
        
        godot_files = list(sprite_dir.glob("*.gd")) + list(sprite_dir.glob("godot_export/*.gd")) + list(sprite_dir.glob("*.tscn"))
        unity_files = list(sprite_dir.glob("*.cs")) + list(sprite_dir.glob("unity_export/*.cs"))
        unreal_files = list(sprite_dir.glob("*.py")) + list(sprite_dir.glob("unreal_export/*.py"))
        has_exports = bool(godot_files or unity_files or unreal_files)
        
        from spriteforge_final import get_project_quality_gates
        gates = get_project_quality_gates(sprite_dir)
        
        passed_gates = True
        gate_details = {}
        
        drift = metrics.get("foot_y_stdev_px", 0.0)
        max_drift = gates.get("max_foot_drift")
        gate_details["foot_drift"] = {"value": drift, "threshold": max_drift, "ok": max_drift is None or drift <= float(max_drift)}
        if not gate_details["foot_drift"]["ok"]:
            passed_gates = False
            
        flicker = metrics.get("brightness_stdev", 0.0)
        max_flicker = gates.get("max_flicker")
        gate_details["flicker"] = {"value": flicker, "threshold": max_flicker, "ok": max_flicker is None or flicker <= float(max_flicker)}
        if not gate_details["flicker"]["ok"]:
            passed_gates = False
            
        seam = metrics.get("loop_seam_rmse", 0.0)
        max_seam = gates.get("loop_seam_threshold")
        gate_details["loop_quality"] = {"value": seam, "threshold": max_seam, "ok": max_seam is None or seam <= float(max_seam)}
        if not gate_details["loop_quality"]["ok"]:
            passed_gates = False
            
        frames_cnt = metrics.get("frame_count")
        req_frames = gates.get("required_frame_count")
        gate_details["frame_count"] = {"value": frames_cnt, "threshold": req_frames, "ok": req_frames is None or frames_cnt is None or int(frames_cnt) == int(req_frames)}
        if not gate_details["frame_count"]["ok"]:
            passed_gates = False
            
        cleanliness = metrics.get("alpha_cleanliness")
        if cleanliness is None and qa_data:
            sheet_png = sprite_dir / qa_data.get("metadata", {}).get("image", "sheet.png")
            if sheet_png.exists():
                try:
                    from PIL import Image
                    import numpy as np
                    with Image.open(sheet_png) as img:
                        arr = np.asarray(img.convert("RGBA"))
                        alpha = arr[:, :, 3]
                        cleanliness = float(((alpha > 0) & (alpha < 16)).sum() / max(1, alpha.size))
                except Exception:
                    cleanliness = 0.0
            else:
                cleanliness = 0.0
        cleanliness = cleanliness or 0.0
        max_clean = gates.get("alpha_cleanliness")
        gate_details["alpha_cleanliness"] = {"value": cleanliness, "threshold": max_clean, "ok": max_clean is None or cleanliness <= float(max_clean)}
        if not gate_details["alpha_cleanliness"]["ok"]:
            passed_gates = False
            
        sheet_json_path = sprite_dir / "sheet.json"
        missing_frames = False
        if sheet_json_path.exists():
            try:
                sheet_json = json.loads(sheet_json_path.read_text(encoding="utf-8"))
                exp_cnt = sheet_json.get("frame_count", 0)
                if exp_cnt and frames_cnt and frames_cnt < exp_cnt:
                    missing_frames = True
            except Exception:
                pass
                
        # Version metrics history for sparklines
        version_history = []
        versions_dir = sprite_dir / ".versions"
        vfile = versions_dir / "versions.json"
        if vfile.exists():
            try:
                v_data = json.loads(vfile.read_text(encoding="utf-8"))
                for v in v_data.get("versions", []):
                    vid = v.get("id")
                    v_subdir = versions_dir / vid
                    v_qa = {}
                    for p in ["qa/qa_report.json", "qa_report.json", "quality_report.json"]:
                        p_path = v_subdir / p
                        if p_path.exists():
                            try:
                                v_qa = json.loads(p_path.read_text(encoding="utf-8"))
                                break
                            except Exception:
                                pass
                    v_metrics = v_qa.get("metrics", {}) if v_qa else {}
                    version_history.append({
                        "version_id": vid,
                        "label": v.get("label"),
                        "created_at": v.get("created_at"),
                        "loop_seam_rmse": v_metrics.get("loop_seam_rmse"),
                        "foot_y_stdev_px": v_metrics.get("foot_y_stdev_px"),
                        "brightness_stdev": v_metrics.get("brightness_stdev"),
                        "alpha_cleanliness": v_metrics.get("alpha_cleanliness"),
                    })
            except Exception:
                pass
                
        # Append current version to history
        version_history.append({
            "version_id": "current",
            "label": "Current",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "loop_seam_rmse": seam,
            "foot_y_stdev_px": drift,
            "brightness_stdev": flicker,
            "alpha_cleanliness": cleanliness,
        })
                
        summary_list.append({
            "name": name,
            "path": sprite_path_str,
            "has_qa": qa_data is not None,
            "loop_quality": seam,
            "foot_drift": drift,
            "flicker": flicker,
            "alpha_coverage": metrics.get("mean_alpha_coverage", 0.0),
            "alpha_cleanliness": cleanliness,
            "missing_frames": missing_frames,
            "has_exports": has_exports,
            "passed_gates": passed_gates,
            "gate_details": gate_details,
            "ready": passed_gates and has_exports,
            "history": version_history
        })
        
    return {"summary": summary_list}

def _library_json_path(project_name: str) -> Path:
    p_dir = PROJECTS / safe_name(project_name)
    p_dir.mkdir(parents=True, exist_ok=True)
    return p_dir / "library.json"

def _library_list(project_name: str) -> List[Dict[str, Any]]:
    if not project_name:
        return []
    pfile = _library_json_path(project_name)
    return load_json(pfile, [])

def _library_save(project_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    import uuid
    pfile = _library_json_path(project_name)
    library = load_json(pfile, [])
    
    asset_id = payload.get("id") or str(uuid.uuid4())
    existing = None
    for item in library:
        if item["id"] == asset_id:
            existing = item
            break
            
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    item_data = {
        "id": asset_id,
        "title": payload.get("title", "Untitled Asset"),
        "category": payload.get("category", "pose"),
        "content": payload.get("content", ""),
        "reference_path": payload.get("reference_path", ""),
        "updated_at": now
    }
    
    if existing:
        existing.update(item_data)
    else:
        item_data["created_at"] = now
        library.insert(0, item_data)
        
    save_json(pfile, library)
    return {"ok": True, "asset": item_data}

def _library_delete(project_name: str, asset_id: str) -> Dict[str, Any]:
    pfile = _library_json_path(project_name)
    library = load_json(pfile, [])
    updated = [item for item in library if item["id"] != asset_id]
    save_json(pfile, updated)
    return {"ok": True}

def _sprite_edit_frames(sprite_dir_str: str, actions: List[Dict[str, Any]], new_fps: Optional[int]) -> Dict[str, Any]:
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

def _sprite_search_roots(project_meta: Optional[Dict[str, str]] = None) -> List[Path]:
    roots = [OUTPUT]
    if project_meta and project_meta.get("project_root"):
        root = (ROOT / str(project_meta["project_root"]) / "sprites").resolve()
        if _is_relative_to(root, (ROOT / "projects").resolve()):
            roots.insert(0, root)
    elif (ROOT / "projects").exists():
        roots.append(ROOT / "projects")
    return roots

def sprite_outputs(limit: int = 60, project_meta: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen: set[Path] = set()
    for root in _sprite_search_roots(project_meta):
        if not root.exists():
            continue
        for meta in root.rglob("sheet.json"):
            try:
                meta = meta.resolve()
                if meta in seen:
                    continue
                seen.add(meta)
                folder = meta.parent
                data = load_json(meta, {})
                preview = folder / "preview.gif"
                sheet = folder / "sheet.png"
                report = folder / "report.html"
                mtime = folder.stat().st_mtime
                
                godot_files = list(folder.glob("*.gd")) + list(folder.glob("godot_export/*.gd")) + list(folder.glob("*.tscn"))
                unity_files = list(folder.glob("*.cs")) + list(folder.glob("unity_export/*.cs"))
                unreal_files = list(folder.glob("*.py")) + list(folder.glob("unreal_export/*.py"))
                exports_ready = bool(godot_files or unity_files or unreal_files)
                
                row = {
                    "name": folder.name,
                    "path": rel(folder),
                    "mtime": mtime,
                    "modified": dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                    "frame_count": data.get("frame_count", "?"),
                    "fps": data.get("fps", "?"),
                    "frame_width": data.get("frame_width", data.get("w", "?")),
                    "frame_height": data.get("frame_height", data.get("h", "?")),
                    "columns": data.get("columns", "?"),
                    "rows": data.get("rows", "?"),
                    "preview_url": "/file/" + rel(preview) if preview.exists() else None,
                    "sheet_url": "/file/" + rel(sheet) if sheet.exists() else None,
                    "report_url": "/file/" + rel(report) if report.exists() else None,
                    "json_url": "/file/" + rel(meta),
                    "project_name": data.get("project_name", ""),
                    "project_path": data.get("project_path", ""),
                    "project_root": data.get("project_root", ""),
                    "exports_ready": exports_ready,
                }
                if ProjectService.item_matches_project(row, project_meta):
                    rows.append(row)
            except Exception:
                continue
    rows.sort(key=lambda item: item["mtime"], reverse=True)
    return rows[:limit]

def _queue_progress(counts: Dict[str, int], total: int) -> Dict[str, Any]:
    if total <= 0:
        return {"percent": 0, "done": 0, "running": 0, "remaining": 0, "total": 0}
    done = int(counts.get("done", 0))
    failed = int(counts.get("failed", 0))
    running = int(counts.get("running", 0))
    complete_units = done + failed
    percent = min(100.0, ((complete_units + (0.35 if running else 0.0)) / total) * 100.0)
    remaining = max(0, total - complete_units - running)
    return {
        "percent": round(percent, 1),
        "done": done,
        "failed": failed,
        "running": running,
        "remaining": remaining,
        "total": total,
    }

def _queue_job_progress(job: Dict[str, Any]) -> Dict[str, Any]:
    status = str(job.get("status") or "pending").lower()
    if status == "done":
        percent = 100.0
    elif status == "failed":
        percent = 100.0
    elif status == "running":
        percent = 35.0
        log_value = str(job.get("log") or "")
        try:
            log_path = Path(log_value)
            if not log_path.is_absolute():
                log_path = ROOT / log_path
            if log_path.exists():
                text = log_path.read_text(encoding="utf-8", errors="replace")[-12000:]
                import re
                matches = re.findall(r"(?:(\d+)%\s*\|)|(?:(?:step|steps|ksampler|progress)?[:\s]*(\d+)\s*/\s*(\d+))", text, flags=re.IGNORECASE)
                for pct, curr, total in reversed(matches):
                    if pct:
                        percent = max(percent, min(99.0, float(pct)))
                        break
                    if curr and total and int(total) > 0:
                        percent = max(percent, min(99.0, (int(curr) / int(total)) * 100.0))
                        break
        except Exception:
            pass
    elif status in {"interrupted", "cancelled"}:
        percent = 0.0
    else:
        percent = 0.0
    return {"percent": round(percent, 1), "status": status}

def _list_queues(project_meta: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    jobs_dir = OUTPUT / "jobs"
    if not jobs_dir.exists():
        return []
    results: List[Dict[str, Any]] = []
    for qfile in sorted(jobs_dir.glob("*_queue.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(qfile.read_text(encoding="utf-8"))
            counts: Dict[str, int] = {}
            for job in data.get("jobs", []):
                s = job.get("status", "unknown")
                counts[s] = counts.get(s, 0) + 1
            total = len(data.get("jobs", []))
            row = {
                "name": data.get("name", qfile.stem),
                "path": rel(qfile),
                "created_at": data.get("created_at", ""),
                "total": total,
                "counts": counts,
                "progress": _queue_progress(counts, total),
                "project_name": data.get("project_name", ""),
                "project_path": data.get("project_path", ""),
                "project_root": data.get("project_root", ""),
            }
            if ProjectService.item_matches_project(row, project_meta):
                results.append(row)
        except Exception:
            continue
    return results

def _list_releases(project_meta: Optional[Dict[str, str]] = None, limit: int = 40) -> List[Dict[str, Any]]:
    search_roots = [ROOT / "projects", ROOT / "releases", OUTPUT]
    seen: set[Path] = set()
    results: List[Dict[str, Any]] = []
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for manifest in search_root.rglob("manifest.json"):
            try:
                manifest = manifest.resolve()
                if manifest in seen:
                    continue
                seen.add(manifest)
                data = load_json(manifest, {})
                if data.get("schema") != "spriteforge_release_v12":
                    continue
                folder = manifest.parent
                mtime = folder.stat().st_mtime
                zip_path = folder.with_suffix(".zip")
                row = {
                    "name": data.get("name") or folder.name,
                    "path": rel(folder),
                    "manifest_url": "/file/" + rel(manifest),
                    "zip_path": rel(zip_path) if zip_path.exists() else "",
                    "zip_url": "/file/" + rel(zip_path) if zip_path.exists() else "",
                    "created_at": data.get("created_at", ""),
                    "modified": dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                    "mtime": mtime,
                    "sprite_count": data.get("sprite_count", len(data.get("sprites", []))),
                    "project_name": data.get("project_name", ""),
                    "project_path": data.get("project_path", ""),
                    "project_root": data.get("project_root", ""),
                }
                if ProjectService.item_matches_project(row, project_meta):
                    results.append(row)
            except Exception:
                continue
    results.sort(key=lambda item: item["mtime"], reverse=True)
    return results[:limit]

def _list_packs(project_meta: Optional[Dict[str, str]] = None, limit: int = 40) -> List[Dict[str, Any]]:
    search_roots = [ROOT / "projects", OUTPUT / "packs", OUTPUT]
    seen: set[Path] = set()
    results: List[Dict[str, Any]] = []
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for manifest in search_root.rglob("pack_manifest.json"):
            try:
                manifest = manifest.resolve()
                if manifest in seen:
                    continue
                seen.add(manifest)
                data = load_json(manifest, {})
                if data.get("schema") != "spriteforge_pack.v1":
                    continue
                folder = manifest.parent
                mtime = folder.stat().st_mtime
                entries = data.get("entries", [])
                row = {
                    "name": data.get("pack_name") or data.get("character") or folder.name,
                    "path": rel(folder),
                    "manifest_path": rel(manifest),
                    "manifest_url": "/file/" + rel(manifest),
                    "created_at": data.get("created_at", ""),
                    "modified": dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                    "mtime": mtime,
                    "actions": data.get("actions", []),
                    "directions": data.get("directions", []),
                    "entries": len(entries) if isinstance(entries, list) else 0,
                    "project_name": data.get("project_name", ""),
                    "project_path": data.get("project_path", ""),
                    "project_root": data.get("project_root", ""),
                }
                if ProjectService.item_matches_project(row, project_meta):
                    results.append(row)
            except Exception:
                continue
    results.sort(key=lambda item: item["mtime"], reverse=True)
    return results[:limit]

def _quality_source_path(folder: Path, project_meta: Optional[Dict[str, str]]) -> str:
    if (folder / "sheet.json").is_file():
        return rel(folder)
    if folder.name in {"qa", "quality"} and (folder.parent / "sheet.json").is_file():
        return rel(folder.parent)
    if project_meta and project_meta.get("project_root"):
        project_root = ROOT / str(project_meta["project_root"])
        candidate = project_root / "sprites" / folder.name
        if (candidate / "sheet.json").is_file():
            return rel(candidate)
    candidate = OUTPUT / folder.name
    if (candidate / "sheet.json").is_file():
        return rel(candidate)
    return rel(folder)

def _list_quality_reports(project_meta: Optional[Dict[str, str]] = None, limit: int = 40) -> List[Dict[str, Any]]:
    search_roots = [ROOT / "projects", OUTPUT]
    seen: set[Path] = set()
    results: List[Dict[str, Any]] = []
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for pattern in ("qa_report.json", "quality_report.json"):
            for report in search_root.rglob(pattern):
                try:
                    report = report.resolve()
                    if report in seen:
                        continue
                    seen.add(report)
                    data = load_json(report, {})
                    folder = report.parent
                    html_report = folder / report.name.replace(".json", ".html")
                    mtime = report.stat().st_mtime
                    metrics = data.get("metrics", {}) if isinstance(data.get("metrics"), dict) else {}
                    issues = data.get("issues", []) if isinstance(data.get("issues"), list) else []
                    score = data.get("score")
                    row = {
                        "name": folder.name,
                        "path": rel(folder),
                        "source_path": _quality_source_path(folder, project_meta),
                        "report_path": rel(report),
                        "report_url": "/file/" + rel(report),
                        "html_url": "/file/" + rel(html_report) if html_report.exists() else "",
                        "kind": "QA report" if report.name == "qa_report.json" else "Quality report",
                        "modified": dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                        "mtime": mtime,
                        "score": score,
                        "issue_count": len(issues),
                        "loop_seam_rmse": metrics.get("loop_seam_rmse"),
                        "foot_y_stdev_px": metrics.get("foot_y_stdev_px"),
                        "project_name": data.get("project_name", ""),
                        "project_path": data.get("project_path", ""),
                        "project_root": data.get("project_root", ""),
                    }
                    if ProjectService.item_matches_project(row, project_meta):
                        results.append(row)
                except Exception:
                    continue
    results.sort(key=lambda item: item["mtime"], reverse=True)
    return results[:limit]

def _list_references(project_meta: Optional[Dict[str, str]] = None, limit: int = 80) -> List[Dict[str, Any]]:
    allowed = VIDEO_SUFFIXES | IMAGE_SUFFIXES
    if project_meta and project_meta.get("project_root"):
        root = (ROOT / str(project_meta["project_root"]) / "references").resolve()
        if not _is_relative_to(root, (ROOT / "projects").resolve()):
            return []
    else:
        root = UPLOADS
    if not root.exists():
        return []
    results: List[Dict[str, Any]] = []
    for path in sorted(root.glob("*"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
        try:
            if not path.is_file() or path.suffix.lower() not in allowed:
                continue
            kind = "video" if path.suffix.lower() in VIDEO_SUFFIXES else "image"
            mtime = path.stat().st_mtime
            results.append({
                "name": path.name,
                "path": rel(path),
                "url": "/file/" + rel(path),
                "kind": kind,
                "size": path.stat().st_size,
                "modified": dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                "mtime": mtime,
                "project_name": project_meta.get("project_name", "") if project_meta else "",
                "project_path": project_meta.get("project_path", "") if project_meta else "",
                "project_root": project_meta.get("project_root", "") if project_meta else "",
            })
        except Exception:
            continue
    return results[:limit]

def _list_planning_assets(project_meta: Optional[Dict[str, str]] = None, limit: int = 120) -> Dict[str, List[Dict[str, Any]]]:
    empty: Dict[str, List[Dict[str, Any]]] = {"prompts": [], "posepacks": []}
    if not project_meta or not project_meta.get("project_root"):
        return empty
    project_root = (ROOT / str(project_meta["project_root"])).resolve()
    if not _is_relative_to(project_root, (ROOT / "projects").resolve()) or not project_root.exists():
        return empty

    prompts: List[Dict[str, Any]] = []
    prompts_dir = project_root / "prompts"
    if prompts_dir.exists():
        for path in sorted(prompts_dir.glob("*.json"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
            try:
                data = load_json(path, {})
                mtime = path.stat().st_mtime
                prompts.append({
                    "name": path.stem,
                    "path": rel(path),
                    "url": "/file/" + rel(path),
                    "action": data.get("action", ""),
                    "direction": data.get("direction", ""),
                    "modified": dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                    "mtime": mtime,
                })
            except Exception:
                continue

    posepacks: List[Dict[str, Any]] = []
    posepacks_dir = project_root / "posepacks"
    if posepacks_dir.exists():
        for path in sorted(posepacks_dir.glob("*/posepack.json"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
            try:
                data = load_json(path, {})
                mtime = path.stat().st_mtime
                frames = data.get("frames", [])
                posepacks.append({
                    "name": path.parent.name,
                    "path": rel(path.parent),
                    "manifest_path": rel(path),
                    "manifest_url": "/file/" + rel(path),
                    "action": data.get("action", ""),
                    "direction": data.get("direction", ""),
                    "frames": len(frames) if isinstance(frames, list) else 0,
                    "modified": dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                    "mtime": mtime,
                })
            except Exception:
                continue

    return {"prompts": prompts[:limit], "posepacks": posepacks[:limit]}

def _project_asset_counts(project_meta: Optional[Dict[str, str]]) -> Dict[str, int]:
    counts = {"references": 0, "packs": 0, "prompts": 0, "posepacks": 0}
    if not project_meta:
        return counts
    project_root = str(project_meta.get("project_root") or "")
    if not project_root:
        return counts
    root = (ROOT / project_root).resolve()
    if not _is_relative_to(root, (ROOT / "projects").resolve()) or not root.exists():
        return counts
    allowed_refs = VIDEO_SUFFIXES | IMAGE_SUFFIXES
    counts["references"] = sum(1 for path in (root / "references").glob("*") if path.is_file() and path.suffix.lower() in allowed_refs) if (root / "references").exists() else 0
    counts["packs"] = sum(1 for path in root.rglob("pack_manifest.json") if path.is_file())
    counts["prompts"] = sum(1 for path in (root / "prompts").glob("*.json") if path.is_file()) if (root / "prompts").exists() else 0
    counts["posepacks"] = sum(1 for path in (root / "posepacks").glob("*/posepack.json") if path.is_file()) if (root / "posepacks").exists() else 0
    return counts

def _project_meta_from_query(query: Dict[str, List[str]]) -> Optional[Dict[str, str]]:
    project_value = (query.get("project") or [""])[0]
    if project_value:
        return ProjectService.metadata_for_path(project_value)
    active = ProjectService.get_active_project()
    if active:
        return ProjectService.metadata_for_path(str(active.get("path") or ""))
    return None

def _project_workspace(project_meta: Optional[Dict[str, str]]) -> Dict[str, Any]:
    experiments = [
        rec for rec in ExperimentService.get_history()
        if ProjectService.item_matches_project(rec, project_meta)
    ] if project_meta else ExperimentService.get_history()
    outputs = sprite_outputs(500, project_meta)
    queues = _list_queues(project_meta)
    releases = _list_releases(project_meta)
    packs = _list_packs(project_meta)
    quality = _list_quality_reports(project_meta)
    assets = _project_asset_counts(project_meta)
    return {
        "active": project_meta,
        "outputs": len(outputs),
        "experiments": len(experiments),
        "queues": len(queues),
        "releases": len(releases),
        "quality": len(quality),
        **assets,
        "packs": len(packs),
        "starred": sum(1 for rec in experiments if rec.get("starred")),
    }

def _experiment_rows(project_meta: Optional[Dict[str, str]]) -> List[Dict[str, Any]]:
    rows = ExperimentService.get_history()
    return [rec for rec in rows if ProjectService.item_matches_project(rec, project_meta)] if project_meta else rows

def _comfy_output_root() -> Path:
    cfg = ConfigService.get_config()
    raw = cfg.get("paths", {}).get("comfyui_output", "vendor/ComfyUI/output") if isinstance(cfg, dict) else "vendor/ComfyUI/output"
    path = Path(str(raw))
    return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()

def _file_url(path: Optional[Path]) -> Optional[str]:
    if not path or not path.exists() or not path.is_file():
        return None
    return "/file/" + rel(path)

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

def _matching_experiment(sprite_rel: str) -> Optional[Dict[str, Any]]:
    wanted = sprite_rel.replace("\\", "/").strip("/")
    for rec in ExperimentService.get_history():
        if str(rec.get("sprite_folder") or "").replace("\\", "/").strip("/") == wanted:
            return rec
    return None

def _infer_source_video(sprite_dir: Path, meta: Dict[str, Any]) -> Optional[Path]:
    source = meta.get("extra", {}).get("source", {}) if isinstance(meta.get("extra"), dict) else {}
    if isinstance(source, dict):
        found = _resolve_existing_file(str(source.get("source_path") or ""))
        if found:
            return found

    sprite_rel = rel(sprite_dir)
    rec = _matching_experiment(sprite_rel)
    if rec:
        found = _resolve_existing_file(str(rec.get("output_video") or ""))
        if found:
            return found

    source_names = []
    frames = meta.get("frames", [])
    if isinstance(frames, list):
        source_names = [str(f.get("source_name") or "") for f in frames if isinstance(f, dict)]

    stems = []
    name = sprite_dir.name
    for suffix in ("_sprite_clean", "_sprite_fixed", "_sprite", "_fixed"):
        if name.endswith(suffix):
            stems.append(name[: -len(suffix)])
    stems.append(name)
    for source_name in source_names[:3]:
        cleaned = source_name.rsplit("_", 1)[0] if "_" in source_name else source_name
        if cleaned:
            stems.append(cleaned)

    roots = [_comfy_output_root(), INPUT, UPLOADS]
    candidates: List[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for file in root.rglob("*"):
            if file.suffix.lower() in VIDEO_SUFFIXES:
                candidates.append(file)
    for stem in stems:
        normalized = stem.lower()
        for file in candidates:
            file_stem = file.stem.lower()
            if file_stem == normalized or file_stem in normalized or normalized in file_stem:
                return file.resolve()
    return None

def sprite_preview_bundle(sprite_path: str) -> Dict[str, Any]:
    sprite_dir = _resolve_sprite_output_dir(sprite_path)
    meta_path = sprite_dir / "sheet.json"
    meta = load_json(meta_path, {})
    source_video = _infer_source_video(sprite_dir, meta)
    preview = sprite_dir / "preview.gif"
    sheet = sprite_dir / str(meta.get("image") or "sheet.png")
    report = sprite_dir / "report.html"
    qa_report = sprite_dir / "qa" / "qa_report.html"
    
    qa_data = {}
    for p in ["qa/qa_report.json", "qa_report.json", "quality_report.json"]:
        p_path = sprite_dir / p
        if p_path.exists():
            try:
                qa_data = json.loads(p_path.read_text(encoding="utf-8"))
                break
            except Exception:
                pass
    visual_json = sprite_dir / "visual_report" / "visual_report.json"
    visual_report = load_json(visual_json, {}) if visual_json.exists() else {}
    visual_contact = sprite_dir / "visual_report" / "contact_sheet.jpg"
    experiment = _matching_experiment(rel(sprite_dir))
                
    return {
        "name": sprite_dir.name,
        "path": rel(sprite_dir),
        "video_url": _file_url(source_video),
        "video_path": rel(source_video) if source_video else "",
        "preview_url": _file_url(preview),
        "sheet_url": _file_url(sheet),
        "report_url": _file_url(report),
        "qa_url": _file_url(qa_report),
        "qa_report": qa_data,
        "qa_gate": summarize_qa_gates(qa_data) if qa_data else {"status": "warning", "reasons": ["QA report has not been generated yet."], "score": None, "issue_count": 0},
        "visual_report": visual_report,
        "contact_sheet_url": _file_url(visual_contact),
        "experiment": experiment,
        "json_url": _file_url(meta_path),
        "frame_count": meta.get("frame_count", "?"),
        "fps": meta.get("fps", "?"),
        "frame_width": meta.get("frame_width", "?"),
        "frame_height": meta.get("frame_height", "?"),
        "columns": meta.get("columns", "?"),
        "rows": meta.get("rows", "?"),
        "source": meta.get("extra", {}).get("source", {}) if isinstance(meta.get("extra"), dict) else {},
    }

def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False

def _resolve_queue_path(value: str) -> Path:
    qpath = (ROOT / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    jobs_dir = (OUTPUT / "jobs").resolve()
    if not _is_relative_to(qpath, jobs_dir):
        raise ValueError("Queue path must be inside output/jobs.")
    if qpath.suffix.lower() != ".json" or not qpath.name.endswith("_queue.json"):
        raise ValueError("Queue path must be a *_queue.json file.")
    if not qpath.exists() or not qpath.is_file():
        raise FileNotFoundError("Queue file not found.")
    return qpath

def _resolve_sprite_output_dir(value: str) -> Path:
    sprite_dir = (ROOT / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    projects_dir = (ROOT / "projects").resolve()
    if not (_is_relative_to(sprite_dir, OUTPUT) or _is_relative_to(sprite_dir, projects_dir)):
        raise ValueError("Sprite path must be inside output or projects.")
    if not sprite_dir.is_dir() or not (sprite_dir / "sheet.json").is_file():
        raise FileNotFoundError("Sprite output folder not found.")
    return sprite_dir

def _project_artifact_path(project_meta: Dict[str, str], folder: str, name: str) -> Path:
    project_root = (ROOT / str(project_meta["project_root"])).resolve()
    projects_root = (ROOT / "projects").resolve()
    if not _is_relative_to(project_root, projects_root):
        raise ValueError("Project root must be inside projects.")
    return project_root / folder / safe_name(name)

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
    if action == "generate_sprite":
        cmd = [PYTHON, "spriteforge_unified.py", "generate-sprite"]
        if payload.get("start_comfy", True):
            cmd.append("--start-comfy")
        tier = str(payload.get("tier") or "wan22_5b")
        cmd += ["--tier", tier]
        cmd += ["--profile", str(payload.get("profile") or "auto")]
        for key, arg in [("sprite_action", "--action"), ("direction", "--direction"), ("character", "--character"), ("style", "--style"), ("prompt", "--prompt"), ("negative", "--negative"), ("reference_image", "--reference-image"), ("seed", "--seed")]:
            value = str(payload.get(key) or "").strip()
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
        return "Generate WAN sprite", cmd
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
        if payload.get("drop_loop_duplicate", True):
            extra.append("--drop-loop-duplicate")
        if payload.get("preview_gif", True):
            extra.append("--preview-gif")
        if payload.get("report", True):
            extra.append("--report")
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
    path = path.resolve()
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
