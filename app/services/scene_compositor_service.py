from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List


def _safe_name(value: str, fallback: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_. -]+", "_", str(value or "").strip())
    return text[:80] or fallback


def _safe_sprite_dir(root: Path, value: str) -> Path:
    rel = str(value or "").replace("\\", "/").strip("/")
    candidate = (root / rel).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("Sprite path must stay inside the SpriteForge workspace.") from exc
    if not candidate.is_dir() or not (candidate / "sheet.json").is_file():
        raise ValueError(f"Sprite output not found: {value}")
    return candidate


def _rel_url(root: Path, path: Path) -> str:
    return "/file/" + path.resolve().relative_to(root.resolve()).as_posix()


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_scene_manifest(root: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    width = max(64, min(4096, _int(payload.get("width"), 640)))
    height = max(64, min(4096, _int(payload.get("height"), 360)))
    fps = max(1, min(60, _int(payload.get("fps"), 12)))
    layers_in = payload.get("layers") if isinstance(payload.get("layers"), list) else []
    if not layers_in:
        raise ValueError("At least one scene layer is required.")

    layers: List[Dict[str, Any]] = []
    for idx, raw in enumerate(layers_in):
        if not isinstance(raw, dict):
            continue
        sprite_dir = _safe_sprite_dir(root, str(raw.get("sprite_path") or ""))
        meta = json.loads((sprite_dir / "sheet.json").read_text(encoding="utf-8"))
        image = str(meta.get("image") or "sheet.png")
        sheet_path = sprite_dir / image
        if not sheet_path.is_file():
            raise ValueError(f"Missing sprite sheet image for {raw.get('sprite_path')}")
        layers.append({
            "name": _safe_name(raw.get("name"), f"Layer {idx + 1}"),
            "sprite_path": sprite_dir.relative_to(root.resolve()).as_posix(),
            "sheet_url": _rel_url(root, sheet_path),
            "x": _float(raw.get("x"), width / 2),
            "y": _float(raw.get("y"), height / 2),
            "scale": max(0.1, min(8.0, _float(raw.get("scale"), 1.0))),
            "opacity": max(0.0, min(1.0, _float(raw.get("opacity"), 1.0))),
            "frame_width": _int(meta.get("frame_width"), 1),
            "frame_height": _int(meta.get("frame_height"), 1),
            "frame_count": _int(meta.get("frame_count"), 1),
            "columns": _int(meta.get("columns"), 1),
            "rows": _int(meta.get("rows"), 1),
            "fps": _int(meta.get("fps"), fps),
            "animation": str(meta.get("animation") or sprite_dir.name),
        })
    if not layers:
        raise ValueError("No valid scene layers were provided.")
    return {
        "ok": True,
        "scene": {"name": _safe_name(payload.get("name"), "scene"), "width": width, "height": height, "fps": fps},
        "layers": layers,
    }
