"""Frame-synced audio cue manifests for sprite previews."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def cue_manifest_path(sprite_dir: Path) -> Path:
    return sprite_dir / "audio_cues.json"


def load_audio_cues(sprite_dir: Path) -> Dict[str, Any]:
    path = cue_manifest_path(sprite_dir)
    if not path.exists():
        return {"schema": "spriteforge_audio_cues.v1", "cues": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    cues = data.get("cues") if isinstance(data, dict) else []
    return {"schema": "spriteforge_audio_cues.v1", "cues": cues if isinstance(cues, list) else []}


def save_audio_cues(sprite_dir: Path, cues: List[Dict[str, Any]]) -> Dict[str, Any]:
    cleaned: List[Dict[str, Any]] = []
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
            "audio_path": audio.replace("\\", "/"),
            "label": label[:80],
        })
    manifest = {"schema": "spriteforge_audio_cues.v1", "cues": cleaned}
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
