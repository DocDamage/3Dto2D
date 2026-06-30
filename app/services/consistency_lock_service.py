from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from spriteforge_utils import save_json

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
DEFAULT_PROMPT_SUFFIX = (
    "appearance consistency lock, preserve the same character identity, "
    "outfit, palette, face, silhouette, and proportions across every action"
)


def _resolve_under_root(root: Path, value: str) -> Path:
    root = root.resolve()
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Reference image must live inside the SpriteForge workspace.") from exc
    return candidate


def _valid_reference_image(root: Path, value: Any) -> Path:
    path_value = str(value or "").strip()
    if not path_value:
        raise ValueError("Reference image is required for a consistency lock.")
    path = _resolve_under_root(root, path_value)
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError("Reference image must be a PNG, JPG, JPEG, WEBP, or BMP file.")
    if not path.exists() or not path.is_file():
        raise ValueError("Reference image file was not found.")
    return path


def _strength(value: Any) -> float:
    if value in (None, ""):
        return 0.75
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Consistency lock strength must be a number.") from exc
    if parsed < 0.0 or parsed > 1.0:
        raise ValueError("Consistency lock strength must be between 0 and 1.")
    return round(parsed, 3)


def _safe_mode(value: Any) -> str:
    mode = str(value or "ip_adapter").strip().lower().replace("-", "_")
    allowed = {"ip_adapter", "controlnet", "reference_only"}
    if mode not in allowed:
        raise ValueError("Consistency lock mode must be ip_adapter, controlnet, or reference_only.")
    return mode


def build_consistency_lock(root: Path, payload: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
    reference_image = _valid_reference_image(root, payload.get("reference_image"))
    name = str(payload.get("name") or reference_image.stem or "character").strip()
    prompt_suffix = str(payload.get("prompt_suffix") or DEFAULT_PROMPT_SUFFIX).strip()
    output_dir.mkdir(parents=True, exist_ok=True)

    lock = {
        "name": name,
        "mode": _safe_mode(payload.get("mode")),
        "strength": _strength(payload.get("strength")),
        "reference_image": str(reference_image),
        "prompt_suffix": prompt_suffix,
        "generation_hints": {
            "reference_image_flag": "--reference-image",
            "style_image_flag": "--style-image" if _safe_mode(payload.get("mode")) == "ip_adapter" else None,
            "note": "Existing WAN generation forwards this image to ComfyUI reference/IP-Adapter nodes.",
        },
    }

    manifest_path = output_dir / "consistency_lock.json"
    save_json(manifest_path, lock)
    return {
        "ok": True,
        "lock": lock,
        "manifest": str(manifest_path),
        "reference_image": str(reference_image),
    }


def apply_consistency_lock_to_command(command: List[str], lock: Dict[str, Any]) -> List[str]:
    reference_image = str(lock.get("reference_image") or "").strip()
    if not reference_image:
        return list(command)
    updated = list(command)
    if "--reference-image" in updated:
        idx = updated.index("--reference-image")
        if idx + 1 < len(updated):
            updated[idx + 1] = reference_image
        else:
            updated.append(reference_image)
    else:
        updated += ["--reference-image", reference_image]
    return updated


def load_consistency_lock(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
