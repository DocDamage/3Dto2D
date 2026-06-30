from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image


def _load_sheet(sprite_dir: Path) -> Image.Image:
    meta_path = sprite_dir / "sheet.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing sheet.json in {sprite_dir}")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Could not parse {meta_path}: {exc}") from exc
    image_name = str(meta.get("image") or "sheet.png")
    image_path = sprite_dir / image_name
    if not image_path.exists():
        raise FileNotFoundError(f"Missing sheet image: {image_path}")
    return Image.open(image_path).convert("RGBA")


def compare_sprite_to_golden(
    sprite_dir: Path,
    golden_dir: Path,
    *,
    max_channel_delta: int = 2,
    mismatch_ratio: float = 0.001,
    report_path: Optional[Path] = None,
) -> Dict[str, Any]:
    current = _load_sheet(sprite_dir)
    golden = _load_sheet(golden_dir)
    report: Dict[str, Any] = {
        "schema": "spriteforge_visual_regression.v1",
        "sprite_dir": str(sprite_dir),
        "golden_dir": str(golden_dir),
        "max_allowed_channel_delta": max_channel_delta,
        "max_allowed_mismatch_ratio": mismatch_ratio,
        "image_size": list(current.size),
        "golden_size": list(golden.size),
    }
    if current.size != golden.size:
        report.update({
            "ok": False,
            "reason": "size_mismatch",
            "max_channel_delta": None,
            "pixel_mismatch_ratio": 1.0,
        })
        return _write_report(report, report_path)

    current_arr = np.asarray(current, dtype=np.int16)
    golden_arr = np.asarray(golden, dtype=np.int16)
    delta = np.abs(current_arr - golden_arr)
    per_pixel_delta = np.max(delta, axis=2)
    max_delta = int(np.max(per_pixel_delta)) if per_pixel_delta.size else 0
    mismatched = per_pixel_delta > int(max_channel_delta)
    ratio = float(np.sum(mismatched) / max(1, mismatched.size))
    report.update({
        "ok": max_delta <= int(max_channel_delta) or ratio <= float(mismatch_ratio),
        "reason": "pass" if max_delta <= int(max_channel_delta) or ratio <= float(mismatch_ratio) else "pixel_delta",
        "max_channel_delta": max_delta,
        "pixel_mismatch_ratio": round(ratio, 6),
        "mismatched_pixels": int(np.sum(mismatched)),
        "total_pixels": int(mismatched.size),
    })
    return _write_report(report, report_path)


def _write_report(report: Dict[str, Any], report_path: Optional[Path]) -> Dict[str, Any]:
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
