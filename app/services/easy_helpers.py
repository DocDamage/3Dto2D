#!/usr/bin/env python3
"""Utility functions for Easy Mode GUI."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "spriteforge_config.json"
VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}

from services.open_path_service import open_path as open_system_path
from spriteforge_utils import load_json, save_json, get_app_version
from spriteforge_utils import PYTHON  # noqa: F401

try:
    get_app_version = get_app_version
except NameError:
    get_app_version = lambda: "12"


def python_preference() -> str:
    try:
        return (ROOT / ".python_version").read_text(encoding="utf-8").strip() or "3.12"
    except Exception:
        return "3.12"


def resolve_root_path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def open_path(path: Path) -> None:
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True) if not path.suffix else None
    open_system_path(path)


def is_comfy_running(host: str = "127.0.0.1", port: int = 8188, timeout: float = 0.75) -> bool:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/system_stats", timeout=timeout) as r:
            return 200 <= getattr(r, "status", 200) < 500
    except Exception:
        return False


def short_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def find_recent_sprite_outputs(limit: int = 25) -> List[Path]:
    out = ROOT / "output"
    if not out.exists():
        return []
    candidates: List[Path] = []
    for p in out.rglob("sheet.json"):
        if p.is_file():
            candidates.append(p.parent)
    candidates.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return candidates[:limit]


def nvidia_summary() -> str:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return "nvidia-smi not found"
    try:
        out = subprocess.check_output([exe, "--query-gpu=name,memory.total", "--format=csv,noheader"],
                                       text=True, timeout=3, errors="replace")
        return out.strip().replace("\n", "; ") or "not detected"
    except Exception as exc:
        return f"could not read ({exc})"


def pycmd(*args: str) -> List[str]:
    return [str(PYTHON), *map(str, args)]