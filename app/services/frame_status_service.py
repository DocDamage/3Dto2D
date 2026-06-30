from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from spriteforge_utils import load_json, save_json

ALLOWED_STATUSES = {"unreviewed", "approved", "rejected", "needs_edit"}


def update_frame_status(sprite_dir: Path, frame_index: int, status: str, note: str = "") -> Dict[str, Any]:
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Unknown frame status '{status}'.")
    meta_path = Path(sprite_dir) / "sheet.json"
    meta = load_json(meta_path, {})
    frames = meta.get("frames")
    if not isinstance(frames, list):
        raise ValueError("sheet.json does not contain a frames list.")
    if frame_index < 0 or frame_index >= len(frames):
        raise IndexError("frame_index is out of range.")
    frame = frames[frame_index]
    if not isinstance(frame, dict):
        raise ValueError("frame entry is not editable.")
    frame["review_status"] = status
    if note:
        frame["review_note"] = note
    elif "review_note" in frame and status == "approved":
        frame.pop("review_note", None)
    save_json(meta_path, meta)
    return frame_status_summary(meta)


def frame_status_summary(meta: Dict[str, Any]) -> Dict[str, Any]:
    counts = {status: 0 for status in ALLOWED_STATUSES}
    frames = meta.get("frames") if isinstance(meta.get("frames"), list) else []
    for frame in frames:
        status = frame.get("review_status", "unreviewed") if isinstance(frame, dict) else "unreviewed"
        counts[status if status in counts else "unreviewed"] += 1
    return {
        "frame_count": len(frames),
        "counts": counts,
        "complete": len(frames) > 0 and counts["unreviewed"] == 0,
    }
