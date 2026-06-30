#!/usr/bin/env python3
"""Sprite preview bundle, sprite outputs, QA batch summary."""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.project_service import ProjectService
from services.experiment_service import ExperimentService
from services.config_service import ConfigService
from services.preview_manifest_service import build_frame_manifest
from services.audio_cue_service import load_audio_cues
from services.generation_intelligence import summarize_qa_gates
from spriteforge_utils import load_json, save_json

from services.web_helpers_library import (
    ROOT, OUTPUT, INPUT, UPLOADS, ALLOWED_SUBDIRS,
    _is_relative_to, rel, safe_name,
    VIDEO_SUFFIXES, IMAGE_SUFFIXES, AUDIO_SUFFIXES,
)
from services.web_helpers_listings import (
    _list_queues, _list_releases, _list_packs, _list_quality_reports,
)


# ── Helpers ─────────────────────────────────────────────

def _resolve_sprite_output_dir(value: str) -> Path:
    import web_helpers
    sprite_dir = (web_helpers.ROOT / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    projects_dir = (web_helpers.ROOT / "projects").resolve()
    if not (_is_relative_to(sprite_dir, web_helpers.OUTPUT) or _is_relative_to(sprite_dir, projects_dir)):
        raise ValueError("Sprite path must be inside output or projects.")
    if not sprite_dir.is_dir() or not (sprite_dir / "sheet.json").is_file():
        raise FileNotFoundError("Sprite output folder not found.")
    return sprite_dir

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


# ── Sprite outputs ─────────────────────────────────────

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


# ── Sprite preview bundle ──────────────────────────────

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
    frames, frame_manifest = build_frame_manifest(sprite_dir, meta, rel, _file_url)
    audio_cues = load_audio_cues(sprite_dir)
    for cue in audio_cues.get("cues", []):
        audio_path = _resolve_existing_file(str(cue.get("audio_path") or ""))
        cue["audio_url"] = _file_url(audio_path)

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
        "frames": frames,
        "frame_manifest": frame_manifest,
        "audio_cues": audio_cues,
    }


# ── QA batch summary ──────────────────────────────────

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
            "history": version_history,
        })

    return {"summary": summary_list}