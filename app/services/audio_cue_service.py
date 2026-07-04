"""Frame-synced audio cue manifests for sprite previews."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_AUDIO_CUE_FPS = 12
MANIFEST_SCHEMA = "spriteforge_audio_cues.v1"


def cue_manifest_path(sprite_dir: Path) -> Path:
    return sprite_dir / "audio_cues.json"


def _cue_time_seconds(frame_index: int, fps: int = DEFAULT_AUDIO_CUE_FPS) -> float:
    safe_fps = max(1.0, float(fps))
    return round(max(0, int(frame_index)) / safe_fps, 4)


def _sprite_fps(sprite_dir: Path) -> float:
    sheet_path = sprite_dir / "sheet.json"
    if not sheet_path.exists():
        return float(DEFAULT_AUDIO_CUE_FPS)
    try:
        data = json.loads(sheet_path.read_text(encoding="utf-8"))
        return max(1.0, float(data.get("fps") or DEFAULT_AUDIO_CUE_FPS))
    except Exception:
        return float(DEFAULT_AUDIO_CUE_FPS)


def _engine_import_metadata(fps: float = DEFAULT_AUDIO_CUE_FPS) -> Dict[str, Any]:
    safe_fps = max(1.0, float(fps))
    return {
        "sync": "frame_index",
        "fps": safe_fps,
        "timebase": "seconds = frame_index / fps",
        "loop_behavior": "re-trigger cue when animation loops past its frame",
        "godot": {
            "animation_track": "Call method or audio track at cue.time_seconds",
            "node": "AudioStreamPlayer2D",
        },
        "unity": {
            "animation_event": "Invoke cue playback at cue.time_seconds",
            "component": "AudioSource",
        },
    }


def _manifest(cues: List[Dict[str, Any]], fps: float = DEFAULT_AUDIO_CUE_FPS) -> Dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "engine_import": _engine_import_metadata(fps),
        "cues": cues,
    }


def load_audio_cues(sprite_dir: Path) -> Dict[str, Any]:
    path = cue_manifest_path(sprite_dir)
    if not path.exists():
        return _manifest([])
    data = json.loads(path.read_text(encoding="utf-8"))
    cues = data.get("cues") if isinstance(data, dict) else []
    return save_audio_cues(sprite_dir, cues if isinstance(cues, list) else [])


def save_audio_cues(sprite_dir: Path, cues: List[Dict[str, Any]]) -> Dict[str, Any]:
    cleaned: List[Dict[str, Any]] = []
    fps = _sprite_fps(sprite_dir)
    for cue in cues:
        if not isinstance(cue, dict):
            continue
        frame = int(cue.get("frame_index", 0))
        audio = str(cue.get("audio_path") or "").strip()
        label = str(cue.get("label") or Path(audio).stem or "Cue").strip()
        if frame < 0 or not audio:
            continue
        cleaned.append({
            "frame_index": frame,
            "time_seconds": _cue_time_seconds(frame, fps),
            "audio_path": audio.replace("\\", "/"),
            "label": label[:80],
        })
    manifest = _manifest(cleaned, fps)
    path = cue_manifest_path(sprite_dir)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def upsert_audio_cue(sprite_dir: Path, frame_index: int, audio_path: str, label: str = "") -> Dict[str, Any]:
    manifest = load_audio_cues(sprite_dir)
    cues = [
        cue for cue in manifest["cues"]
        if int(cue.get("frame_index", -1)) != int(frame_index)
    ]
    cues.append({
        "frame_index": int(frame_index),
        "audio_path": audio_path,
        "label": label or Path(audio_path).stem or "Cue",
    })
    cues.sort(key=lambda cue: int(cue.get("frame_index", 0)))
    return save_audio_cues(sprite_dir, cues)


def remove_audio_cue(sprite_dir: Path, frame_index: int) -> Dict[str, Any]:
    manifest = load_audio_cues(sprite_dir)
    cues = [
        cue for cue in manifest["cues"]
        if int(cue.get("frame_index", -1)) != int(frame_index)
    ]
    return save_audio_cues(sprite_dir, cues)
