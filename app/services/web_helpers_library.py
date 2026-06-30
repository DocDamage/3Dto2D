#!/usr/bin/env python3
"""Library/pose asset CRUD, references, planning assets, asset counts."""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from spriteforge_utils import (
    load_json, save_json, ALLOWED_SUBDIRS,
    VIDEO_SUFFIXES, IMAGE_SUFFIXES, AUDIO_SUFFIXES,
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




# ── Library CRUD ────────────────────────────────────────

def _library_json_path(project_name: str) -> Path:
    PROJECTS = ROOT / "projects"
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


# ── References ──────────────────────────────────────────

def _list_references(project_meta: Optional[Dict[str, str]] = None, limit: int = 80) -> List[Dict[str, Any]]:
    allowed = VIDEO_SUFFIXES | IMAGE_SUFFIXES | AUDIO_SUFFIXES
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
            suffix = path.suffix.lower()
            kind = "video" if suffix in VIDEO_SUFFIXES else "audio" if suffix in AUDIO_SUFFIXES else "image"
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


# ── Planning Assets ─────────────────────────────────────

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


# ── Asset Counts ────────────────────────────────────────

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
    allowed_refs = VIDEO_SUFFIXES | IMAGE_SUFFIXES | AUDIO_SUFFIXES
    counts["references"] = sum(1 for path in (root / "references").glob("*") if path.is_file() and path.suffix.lower() in allowed_refs) if (root / "references").exists() else 0
    counts["packs"] = sum(1 for path in root.rglob("pack_manifest.json") if path.is_file())
    counts["prompts"] = sum(1 for path in (root / "prompts").glob("*.json") if path.is_file()) if (root / "prompts").exists() else 0
    counts["posepacks"] = sum(1 for path in (root / "posepacks").glob("*/posepack.json") if path.is_file()) if (root / "posepacks").exists() else 0
    return counts