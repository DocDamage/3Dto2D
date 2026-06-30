from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from spriteforge_utils import natural_key


def build_frame_manifest(
    sprite_dir: Path,
    meta: Dict[str, Any],
    rel_path: Callable[[Path], str],
    file_url: Callable[[Optional[Path]], Optional[str]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    frame_dirs = [sprite_dir / "frames_processed", sprite_dir / "frames"]
    frame_files: List[Path] = []
    frame_dir_name = ""
    for frame_dir in frame_dirs:
        if frame_dir.is_dir():
            frame_files = sorted(frame_dir.glob("*.png"), key=natural_key)
            if frame_files:
                frame_dir_name = frame_dir.name
                break

    sheet_frames = meta.get("frames") if isinstance(meta.get("frames"), list) else []
    records: List[Dict[str, Any]] = []
    for idx, frame_path in enumerate(frame_files):
        sheet_frame = sheet_frames[idx] if idx < len(sheet_frames) and isinstance(sheet_frames[idx], dict) else {}
        rect = {
            "x": int(sheet_frame.get("x", 0) or 0),
            "y": int(sheet_frame.get("y", 0) or 0),
            "w": int(sheet_frame.get("w", meta.get("frame_width", 0)) or 0),
            "h": int(sheet_frame.get("h", meta.get("frame_height", 0)) or 0),
        }
        raw_index = sheet_frame.get("index", idx)
        try:
            frame_index = int(raw_index)
        except (TypeError, ValueError):
            frame_index = idx
        records.append({
            "index": frame_index,
            "name": frame_path.name,
            "path": rel_path(frame_path),
            "url": file_url(frame_path),
            "sheet_rect": rect,
        })

    frame_count = int(meta.get("frame_count") or len(records) or len(sheet_frames) or 0)
    manifest = {
        "frame_count": frame_count,
        "available_frame_count": len(records),
        "fps": meta.get("fps", 12),
        "frame_width": meta.get("frame_width"),
        "frame_height": meta.get("frame_height"),
        "source": frame_dir_name or "sheet",
        "uses_extracted_frames": bool(records),
    }
    return records, manifest
