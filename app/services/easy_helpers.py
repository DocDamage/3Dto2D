#!/usr/bin/env python3
"""Utility functions for Easy Mode GUI."""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from spriteforge_utils import ROOT

CONFIG_PATH = ROOT / "config" / "spriteforge_config.json"
VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}

from services.open_path_service import open_path as open_system_path
from spriteforge_utils import load_json, save_json, get_app_version
from spriteforge_utils import PYTHON  # noqa: F401

logger = logging.getLogger(__name__)

try:
    get_app_version = get_app_version
except NameError:
    get_app_version = lambda: "12"


def python_preference() -> str:
    try:
        return (ROOT / ".python_version").read_text(encoding="utf-8").strip() or "3.12"
    except Exception as exc:
        logger.debug("Could not read .python_version; using Python 3.12 preference: %s", exc)
        return "3.12"


def resolve_root_path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def open_path(path: Path) -> None:
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True) if not path.suffix else None
    open_system_path(path)


def web_studio_url(host: str = "127.0.0.1", port: int = 7860) -> str:
    return f"http://{host}:{port}"


def is_comfy_running(host: str = "127.0.0.1", port: int = 8188, timeout: float = 0.75) -> bool:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/system_stats", timeout=timeout) as r:
            return 200 <= getattr(r, "status", 200) < 500
    except Exception as exc:
        logger.debug("ComfyUI health check failed for %s:%s: %s", host, port, exc)
        return False


def short_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception as exc:
        logger.debug("Could not shorten path %s relative to %s: %s", path, ROOT, exc)
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


_nvidia_summary_cache = {"time": 0.0, "value": ""}


def nvidia_summary() -> str:
    now = time.time()
    if now - _nvidia_summary_cache["time"] < 15.0:
        return _nvidia_summary_cache["value"]

    exe = shutil.which("nvidia-smi")
    if not exe:
        val = "nvidia-smi not found"
    else:
        try:
            out = subprocess.check_output([exe, "--query-gpu=name,memory.total", "--format=csv,noheader"],
                                           text=True, timeout=3, errors="replace")
            val = out.strip().replace("\n", "; ") or "not detected"
        except Exception as exc:
            val = f"could not read ({exc})"

    _nvidia_summary_cache["time"] = now
    _nvidia_summary_cache["value"] = val
    return val


def pycmd(*args: str) -> List[str]:
    return [str(PYTHON), *map(str, args)]


def parse_progress_percent(text: str) -> Optional[float]:
    """Extract a 0-100 progress percentage from common CLI progress lines."""
    line = str(text or "")
    percent = re.search(r"(\d+(?:\.\d+)?)%\s*(?:\||$|\s)", line)
    if percent:
        value = float(percent.group(1))
        return max(0.0, min(100.0, value))

    for pattern in (
        r"(?:[Ss]tep|[Ss]teps|[Ff]rame|[Ff]rames)?\s*(\d+)\s*/\s*(\d+)",
        r"(\d+)\s+of\s+(\d+)",
    ):
        match = re.search(pattern, line)
        if match:
            current = int(match.group(1))
            total = int(match.group(2))
            if total > 0 and current <= total:
                return max(0.0, min(100.0, (current / total) * 100.0))
    return None


def load_thumbnail(folder: Path, cache: Dict[str, Any]) -> Optional[Any]:
    try:
        if str(folder) in cache:
            return cache[str(folder)]

        from PIL import Image, ImageTk
        json_path = folder / "sheet.json"
        img_name = "sheet.png"
        w, h = 512, 512
        if json_path.exists():
            try:
                meta = json.loads(json_path.read_text(encoding="utf-8"))
                img_name = meta.get("image", "sheet.png")
                cell = meta.get("cell_size")
                if cell and len(cell) == 2:
                    w, h = int(cell[0]), int(cell[1])
            except Exception as exc:
                logger.debug("Could not read thumbnail metadata from %s: %s", json_path, exc)

        img_path = folder / img_name
        if not img_path.exists():
            img_path = folder / "sheet.png"
        if not img_path.exists():
            pngs = list(folder.glob("*.png"))
            if pngs:
                img_path = pngs[0]

        if img_path.exists():
            with Image.open(img_path) as img:
                if img.width >= w and img.height >= h:
                    frame = img.crop((0, 0, w, h))
                else:
                    frame = img
                frame.thumbnail((48, 48), Image.Resampling.LANCZOS)
                bg = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
                offset = ((48 - frame.width) // 2, (48 - frame.height) // 2)
                bg.paste(frame, offset)
                photo = ImageTk.PhotoImage(bg)
                cache[str(folder)] = photo
                return photo
    except Exception as exc:
        logger.warning("Error loading Easy Mode thumbnail from %s: %s", folder, exc)
    return None


def load_sprite_preview(folder: Path, cache: Dict[str, Any], size: int = 160) -> Optional[Any]:
    """Load a larger Easy Mode preview, preferring preview.gif when available."""
    try:
        key = f"{folder}:{size}"
        if key in cache:
            return cache[key]

        from PIL import Image, ImageTk

        candidates = [folder / "preview.gif", folder / "sheet.png", folder / "contact_sheet.jpg"]
        img_path = next((path for path in candidates if path.exists()), None)
        if img_path is None:
            frames = folder / "frames_processed"
            if frames.exists():
                img_path = next(iter(sorted(frames.glob("*.png"))), None)
        if img_path is None:
            return None

        with Image.open(img_path) as img:
            frame = img.convert("RGBA")
            frame.thumbnail((size, size), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (size, size), (24, 24, 24, 255))
            offset = ((size - frame.width) // 2, (size - frame.height) // 2)
            canvas.alpha_composite(frame, offset)
            photo = ImageTk.PhotoImage(canvas)
            cache[key] = photo
            return photo
    except Exception as exc:
        logger.warning("Error loading Easy Mode sprite preview from %s: %s", folder, exc)
    return None
