from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from spriteforge_utils import load_json, save_json

ALLOWED_STATUSES = {"unreviewed", "approved", "rejected", "needs_edit"}
ALLOWED_FRAME_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_REVIEW_NOTE_LENGTH = 500


def sanitize_review_note(note: str) -> str:
    text = str(note or "").replace("\x00", "").strip()
    text = text.replace("\\", "/")
    while "../" in text:
        text = text.replace("../", "")
    return text[:MAX_REVIEW_NOTE_LENGTH]


def sanitize_frame_filename(frame_name: str) -> str:
    text = str(frame_name or "").replace("\x00", "").strip()
    if not text:
        raise ValueError("frame_name is required.")
    normalized = text.replace("\\", "/")
    name = Path(normalized).name
    if name != normalized or name in {".", ".."} or ".." in name:
        raise ValueError("frame_name must be a simple filename.")
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_FRAME_EXTENSIONS:
        raise ValueError("frame_name must use a supported image extension.")
    if any(ch in name for ch in '<>:"|?*'):
        raise ValueError("frame_name contains unsupported characters.")
    return name


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
    safe_note = sanitize_review_note(note)
    if safe_note:
        frame["review_note"] = safe_note
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
