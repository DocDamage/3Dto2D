from __future__ import annotations

import json
import hashlib
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from services.sprite_sheet_service import (
    make_contact_sheet,
    make_preview_gif,
    pack_sheet,
    write_godot_notes,
    write_metadata,
    write_report,
)
from services.sprite_video_loader import FrameItem, ensure_dir, load_image, save_png_sequence
from spriteforge_utils import load_json, natural_key, save_json

MAX_FRAME_LABEL_LENGTH = 80


def sanitize_frame_label(value: Any) -> str:
    text = str(value or "").replace("\x00", "").strip().replace("\\", "/")
    while "../" in text:
        text = text.replace("../", "")
    return "".join(ch for ch in text if ch.isalnum() or ch in " ._-")[:MAX_FRAME_LABEL_LENGTH].strip()


def _frame_source_dir(sprite_dir: Path) -> Path:
    for name in ("frames_processed", "frames"):
        candidate = sprite_dir / name
        if candidate.is_dir() and list(candidate.glob("*.png")):
            return candidate
    raise FileNotFoundError("No frames_processed or frames PNG sequence found for this sprite.")


def _source_files(sprite_dir: Path) -> List[Path]:
    frame_dir = _frame_source_dir(sprite_dir)
    files = sorted(frame_dir.glob("*.png"), key=natural_key)
    if not files:
        raise FileNotFoundError("No PNG frames found for this sprite.")
    return files


def _timeline_from_actions(source_count: int, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    timeline = [{"source_index": idx} for idx in range(source_count)]
    for action in actions or []:
        action_type = str(action.get("type") or "").strip()
        if action_type == "delete":
            delete_indices = {int(idx) for idx in action.get("indices") or []}
            timeline = [frame for idx, frame in enumerate(timeline) if idx not in delete_indices]
        elif action_type == "hold":
            idx = int(action.get("index", -1))
            count = max(1, int(action.get("count", 1)))
            if 0 <= idx < len(timeline):
                timeline = timeline[: idx + 1] + [dict(timeline[idx]) for _ in range(count)] + timeline[idx + 1 :]
        elif action_type == "reorder":
            mapping = [int(idx) for idx in action.get("mapping") or []]
            timeline = [timeline[idx] for idx in mapping if 0 <= idx < len(timeline)]
        elif action_type == "trim":
            start = int(action.get("start", 0) or 0)
            end = int(action.get("end", len(timeline)) or len(timeline))
            timeline = timeline[max(0, start) : max(0, end)]
    return timeline


def _timeline_from_payload(payload: Dict[str, Any], source_count: int) -> List[Dict[str, Any]]:
    frames = payload.get("frames")
    if isinstance(frames, list) and frames:
        timeline = []
        for item in frames:
            if not isinstance(item, dict):
                continue
            source_index = int(item.get("source_index", item.get("index", -1)))
            if 0 <= source_index < source_count:
                timeline.append({
                    "source_index": source_index,
                    "duration_ms": item.get("duration_ms"),
                    "label": sanitize_frame_label(item.get("label") or ""),
                })
        if timeline:
            return timeline
    return _timeline_from_actions(source_count, payload.get("actions") or [])


def _build_repack_history(
    *,
    sprite_dir: Path,
    source_files: List[Path],
    timeline: List[Dict[str, Any]],
    fps: float,
    default_duration_ms: int,
) -> Dict[str, Any]:
    mappings: List[Dict[str, Any]] = []
    used_source_indices: List[int] = []
    duration_overrides = 0
    for output_index, item in enumerate(timeline):
        source_index = int(item["source_index"])
        used_source_indices.append(source_index)
        duration = item.get("duration_ms")
        mapping = {
            "output_index": output_index,
            "source_index": source_index,
            "source_name": source_files[source_index].name,
            "duration_ms": default_duration_ms,
        }
        if duration not in (None, ""):
            mapping["duration_ms"] = max(1, int(float(duration)))
            duration_overrides += 1
        label = sanitize_frame_label(item.get("label") or "")
        if label:
            mapping["label"] = label
        mappings.append(mapping)

    deleted_source_indices = [
        index for index in range(len(source_files)) if index not in set(used_source_indices)
    ]
    operation_basis = {
        "sprite": sprite_dir.name,
        "fps": fps,
        "source_count": len(source_files),
        "mapping": [
            [item["output_index"], item["source_index"], item["duration_ms"]]
            for item in mappings
        ],
    }
    operation_id = hashlib.sha256(
        json.dumps(operation_basis, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "schema": "spriteforge.frame_repack_history.v1",
        "operation_id": operation_id,
        "source_frame_count": len(source_files),
        "output_frame_count": len(timeline),
        "source_dir": _frame_source_dir(sprite_dir).name,
        "fps": fps,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_overrides": duration_overrides,
        "duplicate_outputs": max(0, len(used_source_indices) - len(set(used_source_indices))),
        "deleted_source_indices": deleted_source_indices,
        "mappings": mappings,
    }


def repack_sprite_sheet(sprite_dir: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    sprite_dir = Path(sprite_dir)
    meta_path = sprite_dir / "sheet.json"
    meta = load_json(meta_path, {})
    source_files = _source_files(sprite_dir)
    timeline = _timeline_from_payload(payload, len(source_files))
    if not timeline:
        raise ValueError("Timeline cannot be empty.")

    fps = float(payload.get("fps") or meta.get("fps") or 12.0)
    animation = str(payload.get("animation") or meta.get("animation") or sprite_dir.name)
    frame_width = int(payload.get("frame_width") or meta.get("frame_width") or Image.open(source_files[0]).width)
    frame_height = int(payload.get("frame_height") or meta.get("frame_height") or Image.open(source_files[0]).height)
    columns = payload.get("columns")
    columns = int(columns) if columns not in (None, "", 0) else int(meta.get("columns") or 0) or None
    backup = bool(payload.get("backup", True))
    default_duration = int(round(1000.0 / fps)) if fps > 0 else 83
    repack_history = _build_repack_history(
        sprite_dir=sprite_dir,
        source_files=source_files,
        timeline=timeline,
        fps=fps,
        default_duration_ms=default_duration,
    )

    if backup:
        version_dir = sprite_dir / ".timeline_backups" / time.strftime("%Y%m%d_%H%M%S")
        ensure_dir(version_dir)
        for name in ("sheet.png", "sheet.json", "preview.gif", "contact_sheet.jpg", "report.html"):
            src = sprite_dir / name
            if src.exists():
                shutil.copy2(src, version_dir / name)

    frames: List[FrameItem] = []
    for out_index, item in enumerate(timeline):
        source_index = int(item["source_index"])
        img = load_image(source_files[source_index])
        if img.size != (frame_width, frame_height):
            img = img.resize((frame_width, frame_height), Image.Resampling.NEAREST)
        frames.append(FrameItem(img, f"frame_{out_index:04d}", source_index=source_index))

    processed_dir = sprite_dir / "frames_processed"
    if processed_dir.exists():
        shutil.rmtree(processed_dir)
    save_png_sequence(frames, processed_dir, prefix="frame")

    sheet, used_columns, rows, rects = pack_sheet(frames, columns=columns, spacing=0, margin=0, power_of_two=False)
    sheet.save(sprite_dir / "sheet.png")
    extra = dict(meta.get("extra") or {}) if isinstance(meta.get("extra"), dict) else {}
    extra["timeline_edit"] = {
        "schema": "spriteforge.timeline_edit.v1",
        "source_frame_count": len(source_files),
        "source_dir": _frame_source_dir(sprite_dir).name,
        "edited_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "history_schema": repack_history["schema"],
        "operation_id": repack_history["operation_id"],
    }
    extra["frame_repack_history"] = repack_history
    write_metadata(
        meta_path,
        "sheet.png",
        frames,
        rects,
        (frame_width, frame_height),
        used_columns,
        rows,
        fps,
        animation,
        spacing=0,
        margin=0,
        extra=extra,
    )

    updated = load_json(meta_path, {})
    preview_durations = []
    for idx, item in enumerate(timeline):
        duration = item.get("duration_ms")
        if duration not in (None, "") and idx < len(updated.get("frames", [])):
            updated["frames"][idx]["duration_ms"] = max(1, int(float(duration)))
        if idx < len(updated.get("frames", [])):
            preview_durations.append(int(updated["frames"][idx].get("duration_ms") or default_duration))
        else:
            preview_durations.append(default_duration)
    updated_extra = updated.setdefault("extra", {})
    if isinstance(updated_extra, dict):
        updated_extra["frame_repack_history"] = repack_history
        updated_extra["timeline_edit"] = extra["timeline_edit"]
    save_json(meta_path, updated)

    make_preview_gif(frames, sprite_dir / "preview.gif", fps=fps, durations_ms=preview_durations)
    make_contact_sheet(frames, sprite_dir / "contact_sheet.jpg", columns=used_columns)
    write_godot_notes(sprite_dir / "godot_notes.txt", len(frames), used_columns, rows, fps, (frame_width, frame_height))
    write_report(sprite_dir / "report.html", "sheet.png", sprite_dir, len(frames), fps, (frame_width, frame_height), used_columns, rows, extra)

    return {
        "ok": True,
        "schema": "spriteforge.repack_sheet.v1",
        "path": str(sprite_dir),
        "frame_count": len(frames),
        "columns": used_columns,
        "rows": rows,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "fps": fps,
        "timeline": timeline,
        "frame_repack_history": repack_history,
    }
