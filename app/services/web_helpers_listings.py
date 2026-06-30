#!/usr/bin/env python3
"""Queue, release, pack, and quality listing helpers (depend on web_helpers_library)."""
from __future__ import annotations

import datetime as dt
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.project_service import ProjectService
from spriteforge_utils import load_json, save_json

# Import shared utilities from the library module
from services.web_helpers_library import (
    ROOT, OUTPUT, INPUT, UPLOADS,
    _is_relative_to, rel, safe_name,
    VIDEO_SUFFIXES, IMAGE_SUFFIXES, AUDIO_SUFFIXES,
)


# ── Queue listing ──────────────────────────────────────

def _resolve_queue_path(value: str) -> Path:
    import web_helpers
    qpath = (web_helpers.ROOT / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    jobs_dir = (web_helpers.OUTPUT / "jobs").resolve()
    if not _is_relative_to(qpath, jobs_dir):
        raise ValueError("Queue path must be inside output/jobs.")
    if qpath.suffix.lower() != ".json" or not qpath.name.endswith("_queue.json"):
        raise ValueError("Queue path must be a *_queue.json file.")
    if not qpath.exists() or not qpath.is_file():
        raise FileNotFoundError("Queue file not found.")
    return qpath

def _get_failed_reason(log_path_str: Optional[str]) -> Optional[str]:
    if not log_path_str:
        return None
    try:
        import web_helpers
        log_path = Path(log_path_str)
        if not log_path.is_absolute():
            log_path = web_helpers.ROOT / log_path
        if log_path.exists() and log_path.is_file():
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in reversed(lines):
                line = line.strip()
                if line:
                    return line
    except Exception:
        pass
    return None

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


# ── Release listing ────────────────────────────────────

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


# ── Pack listing ───────────────────────────────────────

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


# ── Quality listing ────────────────────────────────────

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