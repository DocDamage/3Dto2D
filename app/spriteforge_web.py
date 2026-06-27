#!/usr/bin/env python3
"""SpriteForge Studio v12 Final Polish Dashboard.

Dependency-free local browser UI for SpriteForge/ComfyUI.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import mimetypes
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from email.parser import BytesParser

from services.config_service import ConfigService
from services.comfy_service import ComfyService
from services.model_service import ModelService
from services.job_service import JobService
from services.sprite_service import SpriteService
from services.export_service import ExportService
from services.experiment_service import ExperimentService
from services.project_service import ProjectService
from services.advisor_service import advise as advisor_advise

ROOT = Path(__file__).resolve().parent
DEFAULT_PRESETS = {
    "Classic Platformer (Side-Scroller)": {
        "character": "single full body platformer hero, side view, simple outfit, boots, clean silhouette",
        "style": "pixel-art inspired game sprite, clean silhouette, simple palette",
        "tier": "wan21_safe",
        "profile": "rtx3060_12gb",
        "fps": "12",
        "cell_size": "512x512",
        "default_actions": "idle,walk,run,jump,hurt",
        "default_directions": "left,right",
        "negative": "camera movement, zoom, cuts, rotation, background details",
        "qa_threshold_loop_rmse": "15.0",
        "qa_threshold_foot_drift": "2.0",
        "qa_threshold_center_drift": "5.0"
    },
    "Top-Down RPG Character": {
        "character": "single full body RPG adventurer, top-down view, crisp details",
        "style": "clean 2D game sprite, crisp silhouette, consistent outfit",
        "tier": "wan21_safe",
        "profile": "rtx3060_12gb",
        "fps": "12",
        "cell_size": "512x512",
        "default_actions": "idle,walk,attack_light,hurt,death",
        "default_directions": "front,back,left,right",
        "negative": "camera movement, zoom, cuts, rotation, shadow on floor",
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

def _get_failed_reason(log_path_str: Optional[str]) -> Optional[str]:
    if not log_path_str:
        return None
    try:
        log_path = Path(log_path_str)
        if not log_path.is_absolute():
            log_path = ROOT / log_path
        if log_path.exists() and log_path.is_file():
            # Read last few lines to find the last non-empty line
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in reversed(lines):
                line = line.strip()
                if line:
                    return line
    except Exception:
        pass
    return None

WEB = ROOT / "web"
OUTPUT = ROOT / "output"
INPUT = ROOT / "input"
UPLOADS = INPUT / "uploaded_videos"
LOGS = ROOT / "logs"
CONFIG = ROOT / "config" / "spriteforge_config.json"
VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_SUBDIRS = {"output", "input", "projects", "releases", "workflows", "examples"}


from spriteforge_utils import load_json, save_json, app_python, PYTHON

write_json = save_json


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def safe_name(value: str) -> str:
    cleaned = "".join(ch for ch in value.strip() if ch.isalnum() or ch in "._- ").strip().replace(" ", "_")
    return cleaned or "file"


PROJECTS = ROOT / "projects"
AB_RUNS_PATH = ROOT / "output" / "experiments" / "ab_runs.json"

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
    for name in ["sheet.png", "sheet.json", "preview.gif", "report.html"]:
        f = sprite_dir / name
        if f.exists():
            shutil.copy2(f, v_subdir / name)
            
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
    return load_json(vfile, {"active_version": "current", "versions": []})

def _sprite_version_rollback(sprite_dir_str: str, vid: str) -> Dict[str, Any]:
    sprite_dir = _resolve_sprite_output_dir(sprite_dir_str)
    v_subdir = sprite_dir / ".versions" / vid
    if not v_subdir.exists():
        raise FileNotFoundError(f"Version backup {vid} not found.")
        
    # Copy files back
    for name in ["sheet.png", "sheet.json", "preview.gif", "report.html"]:
        f = v_subdir / name
        dest = sprite_dir / name
        if f.exists():
            shutil.copy2(f, dest)
        elif dest.exists():
            dest.unlink()
            
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
    
    # Build commands for both
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
        
        # Load quality report
        qa_data = None
        for report_name in ["qa_report.json", "quality_report.json"]:
            p = sprite_dir / report_name
            if p.exists():
                try:
                    qa_data = json.loads(p.read_text(encoding="utf-8"))
                    break
                except Exception:
                    pass
        
        metrics = qa_data.get("metrics", {}) if qa_data else {}
        
        # Determine export readiness / engine files
        godot_files = list(sprite_dir.glob("*.gd")) + list(sprite_dir.glob("godot_export/*.gd")) + list(sprite_dir.glob("*.tscn"))
        unity_files = list(sprite_dir.glob("*.cs")) + list(sprite_dir.glob("unity_export/*.cs"))
        has_exports = bool(godot_files or unity_files)
        
        # Load quality gates to check pass status
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
            # calculate on the fly
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
            
        # check missing frames
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
            "ready": passed_gates and has_exports
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
                exports_ready = bool(godot_files or unity_files)
                
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
    """Return summary info for all *_queue.json files in output/jobs/."""
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
    """Return release package summaries from project and global release folders."""
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
    """Return character pack summaries from project and global pack folders."""
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
    """Return QA/quality report summaries from project and sprite output folders."""
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
    """Return uploaded reference image/video files for the active project or global input."""
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
    """Return prompt and posepack planning files for the active project."""
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
    """Count project-local planning assets: references, packs, prompts, and posepacks."""
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


# Jobs are now managed persistently by JobService


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
        tier = str(payload.get("tier") or "wan21_safe")
        cmd += ["--tier", tier]
        cmd += ["--profile", str(payload.get("profile") or "auto")]
        for key, arg in [("sprite_action", "--action"), ("direction", "--direction"), ("character", "--character"), ("style", "--style"), ("prompt", "--prompt"), ("negative", "--negative"), ("reference_image", "--reference-image"), ("seed", "--seed")]:
            value = str(payload.get(key) or "").strip()
            if value:
                cmd += [arg, value]
        # Forward custom preset builder parameters
        for key, arg in [
            ("fps", "--fps"),
            ("cell_size", "--cell-size"),
            ("key_color", "--key-color"),
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
    if action in {"qa_report", "autofix", "export_godot", "export_unity"}:
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
        engine = "godot" if action == "export_godot" else "unity"
        cmd = [PYTHON, "spriteforge_unified.py", "export-engine", "--engine", engine, "--sprite-dir", sprite_dir]
        if project_meta:
            cmd += ["--output", str(_project_artifact_path(project_meta, "exports", f"{Path(sprite_dir).name}_{engine}"))]
        # Forward engine export profile fields
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
            str(payload.get("description") or "single full body original game hero"),
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
        cmd += ["--name", name, "--character", str(payload.get("description") or "single full body original game hero"), "--actions", str(payload.get("actions") or "idle,walk,run,attack_light,hurt"), "--directions", str(payload.get("directions") or "right"), "--tier", str(payload.get("tier") or "wan21_safe"), "--profile", str(payload.get("profile") or "auto")]
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


class Handler(BaseHTTPRequestHandler):
    server_version = "SpriteForgeVisual/12.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        LOGS.mkdir(exist_ok=True)
        with (LOGS / "web_server.log").open("a", encoding="utf-8") as fp:
            fp.write("%s - %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), fmt % args))

    def send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def send_bytes(self, payload: bytes, *, content_type: str, filename: Optional[str] = None, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(payload)

    def read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        return json.loads(self.rfile.read(length).decode("utf-8") or "{}") if length else {}

    def do_GET(self) -> None:
        path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        if path in {"/", "/index.html"}:
            return self.serve_static(WEB / "index.html")
        if path.startswith("/web/"):
            return self.serve_static((WEB / path[len("/web/"):]).resolve(), WEB)
        if path.startswith("/file/"):
            target_path = (ROOT / path[len("/file/"):]).resolve()
            if not _safe_preview_file(target_path):
                self.send_error(403, "Forbidden: Access to system directory is restricted.")
                return
            return self.serve_static(target_path, ROOT)
        if path == "/api/status":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            project_meta = _project_meta_from_query(qs)
            active_job = JobService.get_active_job()
            if active_job:
                job_status = dict(active_job)
                job_status["running"] = True
            else:
                history = JobService.get_history()
                if history:
                    job_status = dict(history[0])
                    job_status["running"] = False
                else:
                    job_status = {"running": False, "title": "Idle", "progress": 0.0, "exit_code": None, "logs": [], "started_at": None, "finished_at": None}
            
            return self.send_json({
                "version": "v12 Final Polish",
                "root": str(ROOT),
                "python": PYTHON,
                "comfy_url": ComfyService.get_url(),
                "comfy_running": ComfyService.is_running(),
                "gpu": ComfyService.get_gpu_info(),
                "models": ModelService.get_summary(),
                "disk": ModelService.get_disk_summary(),
                "next_step": next_step_status(),
                "outputs": sprite_outputs(24, project_meta),
                "project_workspace": _project_workspace(project_meta),
                "job": job_status,
                "time": time.strftime("%H:%M:%S")
            })
        if path == "/api/job":
            active_job = JobService.get_active_job()
            if active_job:
                job_status = dict(active_job)
                job_status["running"] = True
            else:
                history = JobService.get_history()
                if history:
                    job_status = dict(history[0])
                    job_status["running"] = False
                else:
                    job_status = {"running": False, "title": "Idle", "progress": 0.0, "exit_code": None, "logs": [], "started_at": None, "finished_at": None}
            return self.send_json(job_status)
        if path == "/api/job/history":
            return self.send_json({"history": JobService.get_history()})
        if path == "/api/job/detail":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            job_id = (qs.get("id") or [""])[0]
            if not job_id:
                self.send_error(400, "Missing job id")
                return
            job = JobService.get_job(job_id)
            if not job:
                active = JobService.get_active_job()
                if active and active.get("id") == job_id:
                    job = active
            if not job:
                self.send_error(404, "Job not found")
                return
            
            job_dict = dict(job)
            log_file = ROOT / job_dict.get("log_file", f"logs/web_job_{job_id}.log")
            if log_file.exists():
                try:
                    job_dict["full_logs"] = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
                except Exception:
                    job_dict["full_logs"] = job_dict.get("logs", [])
            else:
                job_dict["full_logs"] = job_dict.get("logs", [])
            return self.send_json(job_dict)
        if path == "/api/cleanup/scan":
            files = []
            comfy_out = _comfy_output_root()
            if comfy_out.exists():
                for f in comfy_out.rglob("*"):
                    if f.is_file() and f.suffix.lower() in {".mp4", ".webm", ".png", ".jpg", ".webp", ".gif"}:
                        files.append({
                            "path": rel(f),
                            "size": f.stat().st_size,
                            "mtime": f.stat().st_mtime,
                            "category": "ComfyUI Render Outputs",
                            "id": str(f.relative_to(ROOT)).replace("\\", "/")
                        })
            if UPLOADS.exists():
                for f in UPLOADS.rglob("*"):
                    if f.is_file() and f.suffix.lower() in VIDEO_SUFFIXES | IMAGE_SUFFIXES:
                        files.append({
                            "path": rel(f),
                            "size": f.stat().st_size,
                            "mtime": f.stat().st_mtime,
                            "category": "Uploaded Reference Videos",
                            "id": str(f.relative_to(ROOT)).replace("\\", "/")
                        })
            if OUTPUT.exists():
                for folder in OUTPUT.iterdir():
                    if folder.is_dir() and folder.name not in {"jobs", "packs", "sprite_compare", "temp"}:
                        if not (folder / "sheet.json").exists():
                            total_size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
                            files.append({
                                "path": rel(folder),
                                "size": total_size,
                                "mtime": folder.stat().st_mtime,
                                "category": "Failed / Incomplete Outputs",
                                "id": str(folder.relative_to(ROOT)).replace("\\", "/")
                            })
            if LOGS.exists():
                for f in LOGS.glob("*.log"):
                    if f.is_file() and f.name != "web_server.log":
                        files.append({
                            "path": rel(f),
                            "size": f.stat().st_size,
                            "mtime": f.stat().st_mtime,
                            "category": "Old Task Logs",
                            "id": str(f.relative_to(ROOT)).replace("\\", "/")
                        })
            return self.send_json({"files": files})
        if path == "/api/outputs":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            project_meta = _project_meta_from_query(qs)
            return self.send_json({"outputs": sprite_outputs(80, project_meta), "project_workspace": _project_workspace(project_meta)})
        if path == "/api/sprite/preview":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            sprite_path = (qs.get("path") or [""])[0]
            if not sprite_path:
                self.send_error(400, "Missing sprite path")
                return
            try:
                return self.send_json(sprite_preview_bundle(sprite_path))
            except Exception as exc:
                self.send_error(404, str(exc))
                return
        if path == "/api/config":
            return self.send_json(ConfigService.get_config())
        if path == "/api/experiments":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            project_meta = _project_meta_from_query(qs)
            return self.send_json({"experiments": _experiment_rows(project_meta), "project_workspace": _project_workspace(project_meta)})
        if path == "/api/experiments/export":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            project_meta = _project_meta_from_query(qs)
            data = ExperimentService.export_history(_experiment_rows(project_meta))
            payload = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
            stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            return self.send_bytes(payload, content_type="application/json; charset=utf-8", filename=f"spriteforge_experiment_history_{stamp}.json")
        if path == "/api/advisor":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            quality = (qs.get("quality") or ["balanced"])[0]
            try:
                return self.send_json(advisor_advise(quality))
            except Exception as exc:
                return self.send_json({"error": str(exc)}, 500)
        if path == "/api/queues":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            project_meta = _project_meta_from_query(qs)
            return self.send_json({"queues": _list_queues(project_meta), "project_workspace": _project_workspace(project_meta)})
        if path == "/api/packs":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            project_meta = _project_meta_from_query(qs)
            return self.send_json({"packs": _list_packs(project_meta), "project_workspace": _project_workspace(project_meta)})
        if path == "/api/quality":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            project_meta = _project_meta_from_query(qs)
            return self.send_json({"reports": _list_quality_reports(project_meta), "project_workspace": _project_workspace(project_meta)})
        if path == "/api/references":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            project_meta = _project_meta_from_query(qs)
            return self.send_json({"references": _list_references(project_meta), "project_workspace": _project_workspace(project_meta)})
        if path == "/api/planning":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            project_meta = _project_meta_from_query(qs)
            return self.send_json({**_list_planning_assets(project_meta), "project_workspace": _project_workspace(project_meta)})
        if path == "/api/releases":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            project_meta = _project_meta_from_query(qs)
            return self.send_json({"releases": _list_releases(project_meta), "project_workspace": _project_workspace(project_meta)})
        if path == "/api/projects":
            return self.send_json({"projects": ProjectService.list_projects(), "active": ProjectService.get_active_project()})
        if path == "/api/presets":
            return self.send_json({"presets": _get_presets()})
        if path == "/api/queues/detail":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            qpath_str = (qs.get("path") or [""])[0]
            if not qpath_str:
                return self.send_json({"error": "path required"}, 400)
            try:
                qpath = _resolve_queue_path(qpath_str)
                data = json.loads(qpath.read_text(encoding="utf-8"))
                counts: Dict[str, int] = {}
                for job in data.get("jobs", []):
                    status = job.get("status", "unknown")
                    counts[status] = counts.get(status, 0) + 1
                    job["progress"] = _queue_job_progress(job)
                    if job.get("status") == "failed":
                        job["failed_reason"] = _get_failed_reason(job.get("log"))
                data["progress"] = _queue_progress(counts, len(data.get("jobs", [])))
                return self.send_json(data)
            except FileNotFoundError as exc:
                return self.send_json({"error": str(exc)}, 404)
            except ValueError as exc:
                return self.send_json({"error": str(exc)}, 403)
            except Exception as exc:
                return self.send_json({"error": str(exc)}, 500)

        if path == "/api/project/config":
            active = ProjectService.get_active_project()
            if not active:
                return self.send_json({"error": "No active project"}, 400)
            p_path = ROOT / active["path"]
            if not p_path.exists():
                return self.send_json({"error": "Project file not found"}, 404)
            try:
                data = json.loads(p_path.read_text(encoding="utf-8"))
                if "quality_gates" not in data:
                    data["quality_gates"] = {
                        "max_foot_drift": 2.0,
                        "max_flicker": 1.0,
                        "loop_seam_threshold": 15.0,
                        "required_frame_count": None,
                        "alpha_cleanliness": 0.05
                    }
                return self.send_json(data)
            except Exception as exc:
                return self.send_json({"error": str(exc)}, 500)
                
        if path == "/api/library/list":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            project_name = (qs.get("project_name") or [""])[0]
            if not project_name:
                active = ProjectService.get_active_project()
                project_name = active["name"] if active else ""
            return self.send_json({"library": _library_list(project_name)})
            
        if path == "/api/sprite/version/list":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            sprite_path_str = (qs.get("path") or [""])[0]
            if not sprite_path_str:
                self.send_error(400, "Missing sprite path")
                return
            try:
                return self.send_json(_sprite_version_list(sprite_path_str))
            except Exception as exc:
                self.send_error(500, str(exc))
                return
                
        if path == "/api/ab_run/list":
            return self.send_json({"ab_runs": _ab_run_list()})
            
        if path == "/api/qa/batch_summary":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            project_meta = _project_meta_from_query(qs)
            return self.send_json(_qa_batch_summary(project_meta))
            
        if path == "/api/sprite/validate_engine":
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            sprite_path_str = (qs.get("path") or [""])[0]
            engine = (qs.get("engine") or [None])[0]
            if not sprite_path_str:
                self.send_error(400, "Missing sprite path")
                return
            try:
                sprite_dir = _resolve_sprite_output_dir(sprite_path_str)
                from spriteforge_engine_export import validate_export
                res = validate_export(sprite_dir, engine=engine, return_dict=True)
                return self.send_json(res)
            except Exception as exc:
                self.send_error(500, str(exc))
                return

        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        try:
            if path == "/api/run":
                payload = self.read_json()
                force = bool(payload.get("force", False))
                action = payload.get("action", "generate_sprite")
                
                # Disk Budget Guard check
                estimated_gb = 1.0
                if action == "generate_sprite":
                    act_list = [a.strip() for a in str(payload.get("default_actions") or "").split(",") if a.strip()]
                    dir_list = [d.strip() for d in str(payload.get("default_directions") or "").split(",") if d.strip()]
                    num_jobs = max(1, len(act_list) * len(dir_list))
                    estimated_gb = num_jobs * 0.8
                
                total, used, free = shutil.disk_usage(ROOT)
                free_gb = free / (1024**3)
                
                if not force and (free_gb - estimated_gb < 5.0):
                    return self.send_json({
                        "ok": False,
                        "warning": "low_disk",
                        "free_gb": round(free_gb, 2),
                        "estimated_gb": round(estimated_gb, 2),
                        "message": f"Disk warning: Task requires ~{estimated_gb:.1f} GB. Free space is {free_gb:.1f} GB, which may drop below the 5.0 GB safety threshold."
                    })

                title, cmd = build_action_command(payload)
                metadata = {
                    key: payload.get(key)
                    for key in ["project_name", "project_path", "project_root"]
                    if payload.get(key)
                }
                ok, job_id_or_err = JobService.start_job(title, cmd, metadata=metadata)
                if ok:
                    active = JobService.get_job(job_id_or_err)
                    return self.send_json({"ok": True, "message": "Job started.", "job": active})
                else:
                    return self.send_json({"ok": False, "message": job_id_or_err, "job": None}, 409)
            if path == "/api/cancel":
                active = JobService.get_active_job()
                ok = False
                if active:
                    ok = JobService.cancel_job(active["id"])
                return self.send_json({"ok": ok})
            if path == "/api/job/retry":
                body = self.read_json()
                job_id = str(body.get("id") or "").strip()
                if not job_id:
                    return self.send_json({"ok": False, "message": "job id required"}, 400)
                job = JobService.get_job(job_id)
                if not job:
                    return self.send_json({"ok": False, "message": "Job not found in history"}, 404)
                title = job.get("title") or "Retry Job"
                cmd = job.get("command")
                metadata = job.get("metadata") or {}
                if not cmd:
                    return self.send_json({"ok": False, "message": "Job command not found"}, 400)
                ok, job_id_or_err = JobService.start_job(title, cmd, metadata=metadata)
                if ok:
                    active = JobService.get_job(job_id_or_err)
                    return self.send_json({"ok": True, "message": "Job retried.", "job": active})
                else:
                    return self.send_json({"ok": False, "message": job_id_or_err, "job": None}, 409)
            if path == "/api/cleanup/purge":
                body = self.read_json()
                file_ids = body.get("ids") or []
                if not isinstance(file_ids, list) or not file_ids:
                    return self.send_json({"ok": False, "message": "ids list required"}, 400)
                count = 0
                reclaimed_bytes = 0
                for fid in file_ids:
                    fid_str = str(fid).strip()
                    if not fid_str:
                        continue
                    path_target = (ROOT / fid_str).resolve()
                    if not _is_relative_to(path_target, ROOT):
                        continue
                    comfy_out = _comfy_output_root()
                    is_safe = (
                        _is_relative_to(path_target, OUTPUT) or
                        _is_relative_to(path_target, LOGS) or
                        _is_relative_to(path_target, UPLOADS) or
                        (comfy_out.exists() and _is_relative_to(path_target, comfy_out))
                    )
                    if not is_safe:
                        continue
                    if path_target.exists():
                        try:
                            if path_target.is_file():
                                sz = path_target.stat().st_size
                                path_target.unlink()
                                reclaimed_bytes += sz
                                count += 1
                            elif path_target.is_dir():
                                sz = sum(f.stat().st_size for f in path_target.rglob("*") if f.is_file())
                                shutil.rmtree(path_target)
                                reclaimed_bytes += sz
                                count += 1
                        except Exception:
                            pass
                reclaimed_mb = round(reclaimed_bytes / (1024 * 1024), 2)
                return self.send_json({"ok": True, "count": count, "reclaimed_mb": reclaimed_mb})
            if path == "/api/launch_comfy":
                ok = ComfyService.launch()
                return self.send_json({"ok": ok, "message": "ComfyUI launch requested." if ok else "Launch failed."})
            if path == "/api/experiments/note":
                body = self.read_json()
                run_id = str(body.get("id") or "")
                notes = str(body.get("notes") or "")
                found = ExperimentService.update_note(run_id, notes)
                return self.send_json({"ok": found})
            if path == "/api/experiments/star":
                body = self.read_json()
                run_id = str(body.get("id") or "")
                starred = bool(body.get("starred"))
                found = ExperimentService.set_starred(run_id, starred)
                return self.send_json({"ok": found})
            if path == "/api/experiments/clear":
                body = self.read_json()
                keep_starred = bool(body.get("keep_starred", True))
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                project_meta = (
                    ProjectService.metadata_for_path(str(body.get("active_project") or ""))
                    or _project_meta_from_query(qs)
                )
                predicate = (lambda rec: ProjectService.item_matches_project(rec, project_meta)) if project_meta else None
                removed = ExperimentService.clear_history(keep_starred=keep_starred, predicate=predicate)
                return self.send_json({"ok": True, "removed": removed})
            if path == "/api/projects/create":
                body = self.read_json()
                name = str(body.get("name") or "").strip()
                if not name:
                    return self.send_json({"ok": False, "message": "Project name required."}, 400)
                project = ProjectService.create_project(
                    name=name,
                    character=str(body.get("character") or "single full body original game character, consistent outfit, readable silhouette"),
                    style=str(body.get("style") or "2D game sprite animation, crisp edges, readable silhouette, production sprite sheet style"),
                )
                return self.send_json({"ok": True, "project": project})
            if path == "/api/projects/active":
                body = self.read_json()
                requested = str(body.get("path") or "")
                if not requested:
                    ProjectService.clear_active_project()
                    return self.send_json({"ok": True, "project": None})
                project = ProjectService.set_active_project(requested)
                if not project:
                    return self.send_json({"ok": False, "message": "Project not found."}, 404)
                return self.send_json({"ok": True, "project": project})
            if path == "/api/compare":
                body = self.read_json()
                a_str = str(body.get("a") or "").strip()
                b_str = str(body.get("b") or "").strip()
                if not a_str or not b_str:
                    return self.send_json({"ok": False, "message": "Both 'a' and 'b' paths required."}, 400)
                out_dir = OUTPUT / "sprite_compare"
                try:
                    a_path = _resolve_sprite_output_dir(a_str)
                    b_path = _resolve_sprite_output_dir(b_str)
                    from spriteforge_compare import compare_dirs
                    compare_dirs(a_path, b_path, out_dir)
                    report_rel = rel(out_dir / "compare_report.html")
                    return self.send_json({"ok": True, "report_url": "/file/" + report_rel})
                except FileNotFoundError as exc:
                    return self.send_json({"ok": False, "message": str(exc)}, 404)
                except ValueError as exc:
                    return self.send_json({"ok": False, "message": str(exc)}, 403)
                except Exception as exc:
                    return self.send_json({"ok": False, "message": str(exc)}, 500)
            if path == "/api/presets/save":
                body = self.read_json()
                name = str(body.get("name") or "").strip()
                if not name:
                    return self.send_json({"ok": False, "message": "Preset name required."}, 400)
                user_presets_path = ROOT / "config" / "user_presets.json"
                user_presets_path.parent.mkdir(parents=True, exist_ok=True)
                user_presets = load_json(user_presets_path, {})
                preset_fields = {}
                for field in [
                    "character", "style", "tier", "profile", "fps", "cell_size",
                    "default_actions", "default_directions", "negative",
                    "qa_threshold_loop_rmse", "qa_threshold_foot_drift", "qa_threshold_center_drift"
                ]:
                    preset_fields[field] = str(body.get(field) or "").strip()
                user_presets[name] = preset_fields
                save_json(user_presets_path, user_presets)
                return self.send_json({"ok": True, "presets": _get_presets()})
            if path == "/api/presets/delete":
                body = self.read_json()
                name = str(body.get("name") or "").strip()
                if not name:
                    return self.send_json({"ok": False, "message": "Preset name required."}, 400)
                user_presets_path = ROOT / "config" / "user_presets.json"
                user_presets = load_json(user_presets_path, {})
                if name in user_presets:
                    del user_presets[name]
                    save_json(user_presets_path, user_presets)
                    return self.send_json({"ok": True, "presets": _get_presets()})
                return self.send_json({"ok": False, "message": f"Preset '{name}' is a default preset or not found."}, 400)
            if path == "/api/sprite/save_metadata":
                body = self.read_json()
                sprite_dir_str = str(body.get("path") or "").strip()
                meta_data = body.get("metadata")
                if not sprite_dir_str or meta_data is None:
                    return self.send_json({"ok": False, "message": "path and metadata are required."}, 400)
                try:
                    sprite_dir = _resolve_sprite_output_dir(sprite_dir_str)
                except FileNotFoundError as exc:
                    return self.send_json({"ok": False, "message": str(exc)}, 404)
                except ValueError as exc:
                    return self.send_json({"ok": False, "message": str(exc)}, 403)
                
                sheet_json_path = sprite_dir / "sheet.json"
                save_json(sheet_json_path, meta_data)
                return self.send_json({"ok": True, "message": "Metadata saved successfully."})
            if path == "/api/release/precheck":
                body = self.read_json()
                sprites = body.get("sprites") or []
                if isinstance(sprites, str):
                    sprites = [s.strip() for s in sprites.splitlines() if s.strip()]
                if not sprites:
                    return self.send_json({"ok": True, "errors": [], "warnings": ["No sprites selected for precheck."]})
                resolved_paths = []
                for s in sprites:
                    try:
                        resolved_paths.append(_resolve_sprite_output_dir(s))
                    except Exception as exc:
                        return self.send_json({"ok": False, "errors": [f"Invalid sprite folder '{s}': {exc}"], "warnings": []})
                
                from spriteforge_final import check_release_quality_gates
                gate = check_release_quality_gates(resolved_paths)
                return self.send_json(gate)
            if path == "/api/queues/reorder":
                body = self.read_json()
                qpath_str = str(body.get("path") or "").strip()
                job_id = str(body.get("job_id") or "").strip()
                direction = str(body.get("direction") or "").strip()  # "up" or "down"
                if not qpath_str or not job_id or not direction:
                    return self.send_json({"ok": False, "message": "path, job_id, and direction are required."}, 400)
                qpath = _resolve_queue_path(qpath_str)
                data = json.loads(qpath.read_text(encoding="utf-8"))
                jobs = data.get("jobs", [])
                
                idx = -1
                for i, job in enumerate(jobs):
                    if job.get("id") == job_id:
                        idx = i
                        break
                if idx == -1:
                    return self.send_json({"ok": False, "message": f"Job {job_id} not found in queue."}, 404)
                
                if direction == "up" and idx > 0:
                    jobs[idx], jobs[idx-1] = jobs[idx-1], jobs[idx]
                elif direction == "down" and idx < len(jobs) - 1:
                    jobs[idx], jobs[idx+1] = jobs[idx+1], jobs[idx]
                else:
                    return self.send_json({"ok": False, "message": "Invalid movement direction or boundary reached."}, 400)
                
                save_json(qpath, data)
                return self.send_json({"ok": True, "queue": data})
            if path == "/api/queues/duplicate":
                body = self.read_json()
                qpath_str = str(body.get("path") or "").strip()
                job_id = str(body.get("job_id") or "").strip()
                if not qpath_str or not job_id:
                    return self.send_json({"ok": False, "message": "path and job_id are required."}, 400)
                qpath = _resolve_queue_path(qpath_str)
                data = json.loads(qpath.read_text(encoding="utf-8"))
                jobs = data.get("jobs", [])
                
                target_job = None
                for job in jobs:
                    if job.get("id") == job_id:
                        target_job = job
                        break
                if not target_job:
                    return self.send_json({"ok": False, "message": f"Job {job_id} not found in queue."}, 404)
                
                new_job = json.loads(json.dumps(target_job))
                import re
                base_id_clean = re.sub(r'_dup\d+$', '', job_id)
                dup_idx = 1
                new_id = f"{base_id_clean}_dup{dup_idx}"
                existing_ids = {j.get("id") for j in jobs}
                while new_id in existing_ids:
                    dup_idx += 1
                    new_id = f"{base_id_clean}_dup{dup_idx}"
                
                new_job["id"] = new_id
                new_job["status"] = "pending"
                new_job["started_at"] = None
                new_job["finished_at"] = None
                new_job["exit_code"] = None
                new_job["log"] = None
                
                idx = jobs.index(target_job)
                jobs.insert(idx + 1, new_job)
                save_json(qpath, data)
                return self.send_json({"ok": True, "queue": data})
            if path == "/api/queues/edit_job":
                body = self.read_json()
                qpath_str = str(body.get("path") or "").strip()
                job_id = str(body.get("job_id") or "").strip()
                if not qpath_str or not job_id:
                    return self.send_json({"ok": False, "message": "path and job_id are required."}, 400)
                qpath = _resolve_queue_path(qpath_str)
                data = json.loads(qpath.read_text(encoding="utf-8"))
                jobs = data.get("jobs", [])
                
                target_job = None
                for job in jobs:
                    if job.get("id") == job_id:
                        target_job = job
                        break
                if not target_job:
                    return self.send_json({"ok": False, "message": f"Job {job_id} not found in queue."}, 404)
                
                if "command" in body and isinstance(body["command"], list):
                    target_job["command"] = body["command"]
                if "action" in body:
                    target_job["action"] = str(body["action"])
                if "direction" in body:
                    target_job["direction"] = str(body["direction"])
                
                target_job["status"] = "pending"
                target_job["started_at"] = None
                target_job["finished_at"] = None
                target_job["exit_code"] = None
                target_job["log"] = None
                
                save_json(qpath, data)
                return self.send_json({"ok": True, "queue": data})
            if path in {"/api/queues/run", "/api/queues/retry-failed", "/api/queues/reset"}:
                body = self.read_json()
                qpath_str = str(body.get("path") or "").strip()
                if not qpath_str:
                    return self.send_json({"ok": False, "message": "path required"}, 400)
                try:
                    qpath = _resolve_queue_path(qpath_str)
                except FileNotFoundError as exc:
                    return self.send_json({"ok": False, "message": str(exc)}, 404)
                except ValueError as exc:
                    return self.send_json({"ok": False, "message": str(exc)}, 403)
                if path == "/api/queues/reset":
                    title = f"Reset queue: {qpath.name}"
                    cmd = [PYTHON, "spriteforge_queue.py", "reset", "--queue", str(qpath)]
                elif path == "/api/queues/retry-failed":
                    title = f"Retry failed jobs in queue: {qpath.name}"
                    cmd = [PYTHON, "spriteforge_queue.py", "run", "--queue", str(qpath), "--retry-failed", "--continue-on-error"]
                else:  # /api/queues/run
                    title = f"Run queue: {qpath.name}"
                    cmd = [PYTHON, "spriteforge_queue.py", "run", "--queue", str(qpath), "--continue-on-error"]
                
                only_jobs = body.get("only_jobs")
                if only_jobs:
                    if isinstance(only_jobs, list):
                        only_jobs_str = ",".join(only_jobs)
                    else:
                        only_jobs_str = str(only_jobs)
                    if only_jobs_str:
                        cmd += ["--only-jobs", only_jobs_str]
                ok, job_id_or_err = JobService.start_job(title, cmd)
                if ok:
                    active = JobService.get_job(job_id_or_err)
                    return self.send_json({"ok": True, "message": "Queue job started.", "job": active})
                return self.send_json({"ok": False, "message": job_id_or_err}, 409)
            if path == "/api/open":
                target = str(self.read_json().get("path") or "output")
                p = Path(target).resolve() if Path(target).is_absolute() else (ROOT / target).resolve()
                if not str(p).startswith(str(ROOT.resolve())):
                    return self.send_json({"ok": False, "message": "Access denied: Path is outside workspace root."}, 403)
                try:
                    rel_parts = p.relative_to(ROOT).parts
                    if not rel_parts or rel_parts[0] not in ALLOWED_SUBDIRS:
                        return self.send_json({"ok": False, "message": "Access denied: Opening system folders is restricted."}, 403)
                except ValueError:
                    return self.send_json({"ok": False, "message": "Access denied."}, 403)
                if p.exists():
                    open_local_path(p)
                    return self.send_json({"ok": True})
                return self.send_json({"ok": False, "message": "Path does not exist."}, 404)
            if path == "/api/project/config":
                active = ProjectService.get_active_project()
                if not active:
                    return self.send_json({"ok": False, "message": "No active project"}, 400)
                p_path = ROOT / active["path"]
                if not p_path.exists():
                    return self.send_json({"ok": False, "message": "Project file not found"}, 404)
                
                body = self.read_json()
                try:
                    data = json.loads(p_path.read_text(encoding="utf-8"))
                    for key in ["character", "style", "actions", "directions", "fps", "cell_size", "frames_by_action", "quality_gates"]:
                        if key in body:
                            data[key] = body[key]
                    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    save_json(p_path, data)
                    return self.send_json({"ok": True, "config": data})
                except Exception as exc:
                    return self.send_json({"ok": False, "message": str(exc)}, 500)
                    
            if path == "/api/library/save":
                body = self.read_json()
                project_name = body.get("project_name")
                if not project_name:
                    active = ProjectService.get_active_project()
                    project_name = active["name"] if active else ""
                if not project_name:
                    return self.send_json({"ok": False, "message": "No project context"}, 400)
                res = _library_save(project_name, body)
                return self.send_json(res)
                
            if path == "/api/library/delete":
                body = self.read_json()
                project_name = body.get("project_name")
                asset_id = body.get("id")
                if not project_name:
                    active = ProjectService.get_active_project()
                    project_name = active["name"] if active else ""
                if not project_name or not asset_id:
                    return self.send_json({"ok": False, "message": "project_name and id are required"}, 400)
                res = _library_delete(project_name, asset_id)
                return self.send_json(res)
                
            if path == "/api/sprite/version/save":
                body = self.read_json()
                sprite_path_str = body.get("path")
                label = body.get("label")
                if not sprite_path_str:
                    return self.send_json({"ok": False, "message": "path is required"}, 400)
                res = _sprite_version_save(sprite_path_str, label)
                return self.send_json(res)
                
            if path == "/api/sprite/version/rollback":
                body = self.read_json()
                sprite_path_str = body.get("path")
                version_id = body.get("version_id")
                if not sprite_path_str or not version_id:
                    return self.send_json({"ok": False, "message": "path and version_id are required"}, 400)
                res = _sprite_version_rollback(sprite_path_str, version_id)
                return self.send_json(res)
                
            if path == "/api/ab_run/create":
                body = self.read_json()
                force = bool(body.get("force", False))
                estimated_gb = 2.0
                total, used, free = shutil.disk_usage(ROOT)
                free_gb = free / (1024**3)
                if not force and (free_gb - estimated_gb < 5.0):
                    return self.send_json({
                        "ok": False,
                        "warning": "low_disk",
                        "free_gb": round(free_gb, 2),
                        "estimated_gb": round(estimated_gb, 2),
                        "message": f"Disk warning: A/B Run requires ~2.0 GB. Free space is {free_gb:.1f} GB, which may drop below the 5.0 GB safety threshold."
                    })
                res = _ab_run_create(body)
                return self.send_json(res)
                
            if path == "/api/sprite/edit_frames":
                body = self.read_json()
                sprite_path_str = body.get("path")
                actions = body.get("actions", [])
                new_fps = body.get("fps")
                if not sprite_path_str:
                    return self.send_json({"ok": False, "message": "path is required"}, 400)
                res = _sprite_edit_frames(sprite_path_str, actions, new_fps)
                return self.send_json(res)

            if path == "/api/upload":
                return self.handle_upload()
            return self.send_json({"ok": False, "message": "Not found"}, 404)
        except Exception as exc:
            return self.send_json({"ok": False, "message": str(exc)}, 500)

    def handle_upload(self) -> None:
        try:
            content_type = self.headers.get("Content-Type", "")
            content_length = int(self.headers.get("Content-Length", 0))
            if not content_type or content_length <= 0:
                return self.send_json({"ok": False, "message": "Invalid upload request."}, 400)
            
            # Limit upload size to 100MB
            if content_length > 100 * 1024 * 1024:
                return self.send_json({"ok": False, "message": "Upload size exceeds maximum allowed limit (100MB)."}, 413)
            
            body = self.rfile.read(content_length)
            msg = BytesParser().parsebytes(b"Content-Type: " + content_type.encode("utf-8") + b"\r\n\r\n" + body)
            
            uploaded_part = None
            active_project = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_filename():
                        uploaded_part = part
                        continue
                    field_name = part.get_param("name", header="content-disposition")
                    if field_name == "active_project":
                        active_project = str(part.get_payload(decode=True).decode("utf-8", errors="ignore")).strip()
            
            if uploaded_part is None:
                return self.send_json({"ok": False, "message": "No file payload found in multipart data."}, 400)
                
            filename = safe_name(Path(uploaded_part.get_filename()).name)
            suffix = Path(filename).suffix.lower()
            if suffix not in VIDEO_SUFFIXES and suffix not in IMAGE_SUFFIXES:
                return self.send_json({"ok": False, "message": "Unsupported file type."}, 400)

            project_meta = ProjectService.metadata_for_path(active_project) if active_project else None
            upload_dir = _project_artifact_path(project_meta, "references", "upload").parent if project_meta else UPLOADS
            upload_dir.mkdir(parents=True, exist_ok=True)
            dest = upload_dir / filename
            if dest.exists():
                dest = upload_dir / f"{dest.stem}_{int(time.time())}{dest.suffix}"
            
            file_data = uploaded_part.get_payload(decode=True)
            dest.write_bytes(file_data)
            
            return self.send_json({"ok": True, "path": str(dest), "relative": rel(dest), "name": dest.name})
        except Exception as exc:
            return self.send_json({"ok": False, "message": f"Upload failed: {exc}"}, 500)

    def serve_static(self, path: Path, base: Optional[Path] = None) -> None:
        try:
            path = path.resolve()
            if base is not None and not str(path).startswith(str(base.resolve())):
                self.send_error(403, "Forbidden")
                return
            if not path.exists() or not path.is_file():
                self.send_error(404, "Not found")
                return
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(str(path))[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
        except BrokenPipeError:
            return


def find_free_port(preferred: int) -> int:
    for port in [preferred, 8766, 8767, 8877, 8899, 0]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return int(sock.getsockname()[1])
            except OSError:
                continue
    return preferred


def run_server(port: int, no_browser: bool = False) -> int:
    for folder in [LOGS, OUTPUT, INPUT, WEB]:
        folder.mkdir(parents=True, exist_ok=True)
    port = find_free_port(port)
    url = f"http://127.0.0.1:{port}/"
    print("SpriteForge Studio v12 Final Polish Edition")
    print(f"Local UI: {url}")
    print("Close this window to stop the local UI server.")
    JobService.recover_interrupted_jobs()
    print("Startup: interrupted job recovery complete.")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    if not no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping SpriteForge web UI.")
    finally:
        server.server_close()
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="SpriteForge Studio v12 local web UI")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        expected_files = [
            "index.html",
            "styles.css",
            "js/globals.js",
            "js/project.js",
            "js/gallery.js",
            "js/editor.js",
            "js/experiments.js",
            "js/qa.js",
            "js/app_main.js",
        ]
        missing = [str(WEB / name) for name in expected_files if not (WEB / name).exists()]
        if missing:
            print("Missing web assets:", missing)
            return 1
        print("SpriteForge v12 web UI smoke test passed.")
        return 0
    return run_server(args.port, args.no_browser)


if __name__ == "__main__":
    raise SystemExit(main())
