#!/usr/bin/env python3
"""Animated export helpers for SpriteForge output folders."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from spriteforge_utils import natural_key
from services.sprite_sheet_service import export_apng, export_lottie_json, export_webp_anim
from services.sprite_video_loader import FrameItem, ensure_dir

ANIMATED_EXPORT_FORMATS = ("apng", "webp", "lottie")
ANIMATED_EXPORT_SCHEMA = "spriteforge.animated_export.v1"


def _load_meta(sprite_dir: Path) -> Dict[str, Any]:
    meta_path = sprite_dir / "sheet.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing {meta_path}")
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _load_frame_files(sprite_dir: Path) -> List[FrameItem]:
    for folder_name in ("frames_processed", "frames"):
        folder = sprite_dir / folder_name
        if folder.exists():
            files = sorted([p for p in folder.iterdir() if p.suffix.lower() in {".png", ".webp", ".jpg", ".jpeg"}], key=natural_key)
            if files:
                return [
                    FrameItem(image=Image.open(path).convert("RGBA"), name=path.stem, source_index=i)
                    for i, path in enumerate(files)
                ]
    return []


def load_sprite_animation_frames(sprite_dir: Path) -> tuple[List[FrameItem], Dict[str, Any]]:
    """Load animation frames from a SpriteForge output folder.

    Prefer processed frame PNGs because they preserve per-frame edits. If those
    are absent, slice the generated spritesheet using sheet.json rectangles.
    """
    sprite_dir = Path(sprite_dir)
    meta = _load_meta(sprite_dir)
    frames = _load_frame_files(sprite_dir)
    if frames:
        return frames, meta
    sheet_path = sprite_dir / str(meta.get("image", "sheet.png"))
    if not sheet_path.exists():
        raise FileNotFoundError(f"Missing {sheet_path}")
    sheet = Image.open(sheet_path).convert("RGBA")
    result: List[FrameItem] = []
    frame_meta = meta.get("frames") or []
    fw = int(meta.get("frame_width", 0))
    fh = int(meta.get("frame_height", 0))
    columns = max(1, int(meta.get("columns", 1)))
    count = int(meta.get("frame_count", len(frame_meta)))
    for i in range(count):
        fr = frame_meta[i] if i < len(frame_meta) else {
            "x": (i % columns) * fw,
            "y": (i // columns) * fh,
            "w": fw,
            "h": fh,
        }
        box = (
            int(fr["x"]),
            int(fr["y"]),
            int(fr["x"]) + int(fr.get("w", fw)),
            int(fr["y"]) + int(fr.get("h", fh)),
        )
        result.append(FrameItem(image=sheet.crop(box), name=str(fr.get("name") or f"frame_{i:04d}"), source_index=i))
    if not result:
        raise RuntimeError("No animation frames found.")
    return result, meta


def _frame_durations_ms(meta: Dict[str, Any], frame_count: int, fps: float) -> List[int]:
    default_duration = int(round(1000.0 / fps)) if fps > 0 else 83
    frames_meta = meta.get("frames") if isinstance(meta.get("frames"), list) else []
    durations: List[int] = []
    for index in range(frame_count):
        raw = frames_meta[index].get("duration_ms") if index < len(frames_meta) and isinstance(frames_meta[index], dict) else None
        try:
            duration = max(1, int(round(float(raw)))) if raw is not None else default_duration
        except (TypeError, ValueError):
            duration = default_duration
        durations.append(duration)
    return durations


def _engine_import_hints(fmt: str, frame_width: int, frame_height: int, fps: float, timing_source: str) -> Dict[str, Any]:
    """Return importer hints that game engines can consume without guessing."""
    raster = fmt in {"apng", "webp"}
    return {
        "texture_filter": "nearest",
        "loop": True,
        "frame_size": {"width": frame_width, "height": frame_height},
        "timing": {
            "fps": fps,
            "mode": "per_frame_duration_ms" if timing_source == "sheet.json duration_ms" else "uniform_fps",
        },
        "godot": {
            "supported": raster,
            "resource_type": "AnimatedTexture" if raster else "JSON metadata/reference",
            "import_hint": "Keep filter nearest and disable texture smoothing for crisp sprites.",
        },
        "web": {
            "supported": fmt in {"apng", "webp", "lottie"},
            "element_hint": "img/canvas" if raster else "lottie-web",
        },
    }


def export_animation(sprite_dir: Path, fmt: str, output: Optional[Path] = None, quality: int = 85) -> Dict[str, Any]:
    fmt = fmt.lower().strip()
    if fmt not in ANIMATED_EXPORT_FORMATS:
        raise ValueError(f"Unsupported animated export format: {fmt}")
    sprite_dir = Path(sprite_dir)
    frames, meta = load_sprite_animation_frames(sprite_dir)
    fps = float(meta.get("fps", 12.0) or 12.0)
    durations_ms = _frame_durations_ms(meta, len(frames), fps)
    out_dir = Path(output) if output else sprite_dir / "animated_exports"
    if out_dir.suffix:
        out_path = out_dir
        ensure_dir(out_path.parent)
    else:
        ensure_dir(out_dir)
        ext = {"apng": "png", "webp": "webp", "lottie": "json"}[fmt]
        out_path = out_dir / f"{meta.get('animation', 'animation')}.{ext}"
    if fmt == "apng":
        export_apng(frames, out_path, fps=fps)
    elif fmt == "webp":
        export_webp_anim(frames, out_path, fps=fps, quality=quality)
    else:
        export_lottie_json(frames, out_path, fps=fps, name=str(meta.get("animation", "sprite_animation")))
    frame_width = int(meta.get("frame_width") or (frames[0].image.width if frames else 0))
    frame_height = int(meta.get("frame_height") or (frames[0].image.height if frames else 0))
    manifest_path = out_path.with_suffix(f".{fmt}.manifest.json")
    timing_source = "sheet.json duration_ms" if any(duration != (int(round(1000.0 / fps)) if fps > 0 else 83) for duration in durations_ms) else "fps"
    manifest = {
        "schema": ANIMATED_EXPORT_SCHEMA,
        "format": fmt,
        "file": out_path.name,
        "source_sheet": str(meta.get("image", "sheet.png")),
        "animation": str(meta.get("animation", "animation")),
        "frame_count": len(frames),
        "fps": fps,
        "duration_seconds": round(sum(durations_ms) / 1000.0, 4),
        "timing_source": timing_source,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "quality": quality if fmt == "webp" else None,
        "engine_ready": {
            "godot": fmt in {"apng", "webp"},
            "web": fmt in {"apng", "webp", "lottie"},
            "notes": "APNG/WebP are raster animation assets; Lottie is JSON motion preview/export metadata.",
        },
        "engine_import": _engine_import_hints(fmt, frame_width, frame_height, fps, timing_source),
        "frames": [
            {
                "index": i,
                "name": frame.name,
                "source_index": frame.source_index,
                "duration_ms": durations_ms[i],
            }
            for i, frame in enumerate(frames)
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "format": fmt,
        "path": str(out_path),
        "manifest_path": str(manifest_path),
        "frame_count": len(frames),
        "fps": fps,
        "duration_seconds": manifest["duration_seconds"],
        "schema": ANIMATED_EXPORT_SCHEMA,
    }
