"""Project-level palette lock helpers."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List


DEFAULT_PALETTE_LOCK: Dict[str, Any] = {
    "enabled": False,
    "colors": [],
    "colors_limit": 32,
    "palette_file": "",
    "source": "",
}

_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")
logger = logging.getLogger(__name__)


def _normalize_hex(value: Any) -> str:
    text = str(value or "").strip()
    if not _HEX_RE.match(text):
        return ""
    return "#" + text.lstrip("#").upper()


def normalize_palette_lock(value: Any) -> Dict[str, Any]:
    """Normalize a project palette lock without enabling it by accident."""
    lock = dict(DEFAULT_PALETTE_LOCK)
    if not isinstance(value, dict):
        return lock
    colors: List[str] = []
    raw_colors = value.get("colors") or value.get("palette") or []
    if isinstance(raw_colors, str):
        raw_colors = [part.strip() for part in raw_colors.replace("\n", ",").split(",")]
    if isinstance(raw_colors, list):
        for item in raw_colors:
            color = _normalize_hex(item)
            if color and color not in colors:
                colors.append(color)
    lock["enabled"] = bool(value.get("enabled")) and bool(colors)
    lock["colors"] = colors
    try:
        lock["colors_limit"] = max(2, min(256, int(value.get("colors_limit") or value.get("colors") or len(colors) or 32)))
    except Exception as exc:
        logger.warning("Invalid palette colors_limit in project palette lock %r: %s", value.get("colors_limit"), exc)
        lock["colors_limit"] = len(colors) or 32
    lock["palette_file"] = str(value.get("palette_file") or "").strip()
    lock["source"] = str(value.get("source") or "").strip()
    return lock


def palette_arg_from_lock(value: Any) -> str:
    """Return a CLI-safe custom hex palette list for --pixel-cleanup-palette."""
    lock = normalize_palette_lock(value)
    if not lock["enabled"] or not lock["colors"]:
        return ""
    return ",".join(lock["colors"])
