#!/usr/bin/env python3
"""SpriteForge QA and auto-fix tools."""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter
from spriteforge_utils import natural_key
ROOT = Path(__file__).resolve().parent
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def parse_size(value: Optional[str]) -> Optional[Tuple[int, int]]:
    if not value:
        return None
    value = value.lower().strip()
    if "x" not in value:
        raise argparse.ArgumentTypeError("Size must look like 512x512")
    a, b = value.split("x", 1)
    return int(a), int(b)

@dataclass
class FrameRecord:
    index: int
    image: Image.Image
    name: str

def load_sheet_frames(sprite_dir: Path) -> Tuple[List[FrameRecord], Dict[str, Any]]:
    meta_path = sprite_dir / "sheet.json"
    sheet_path = sprite_dir / "sheet.png"
    if not meta_path.exists() or not sheet_path.exists():
        raise FileNotFoundError(f"Expected sheet.png and sheet.json in {sprite_dir}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    sheet = Image.open(sheet_path).convert("RGBA")
    fw = int(meta["frame_width"])
    fh = int(meta["frame_height"])
    count = int(meta["frame_count"])
    cols = int(meta.get("columns", max(1, sheet.width // fw)))
    frames: List[FrameRecord] = []
    for i in range(count):
        x = (i % cols) * fw
        y = (i // cols) * fh
        frames.append(FrameRecord(i, sheet.crop((x, y, x + fw, y + fh)), f"frame_{i:04d}"))
    return frames, meta


def load_folder_frames(folder: Path) -> Tuple[List[FrameRecord], Dict[str, Any]]:
    files = sorted([p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTS], key=natural_key)
    if not files:
        raise FileNotFoundError(f"No image frames found in {folder}")
    frames = [FrameRecord(i, Image.open(p).convert("RGBA"), p.stem) for i, p in enumerate(files)]
    w, h = frames[0].image.size
    meta = {"frame_width": w, "frame_height": h, "frame_count": len(frames), "fps": 12, "columns": len(frames), "rows": 1, "animation": folder.name}
    return frames, meta


def load_input(path: Path) -> Tuple[List[FrameRecord], Dict[str, Any]]:
    if path.is_dir() and (path / "sheet.json").exists() and (path / "sheet.png").exists():
        return load_sheet_frames(path)
    if path.is_dir():
        return load_folder_frames(path)
    raise FileNotFoundError("QA input must be a SpriteForge output folder or a folder of image frames.")


def alpha_bbox(img: Image.Image, threshold: int = 8) -> Optional[Tuple[int, int, int, int]]:
    arr = np.asarray(img.convert("RGBA"))
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > threshold)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def masked_mean_rgb(img: Image.Image, threshold: int = 8) -> Tuple[float, float, float]:
    arr = np.asarray(img.convert("RGBA"), dtype=np.float32)
    mask = arr[:, :, 3] > threshold
    if not mask.any():
        return (0.0, 0.0, 0.0)
    rgb = arr[:, :, :3][mask]
    return tuple(float(x) for x in rgb.mean(axis=0))


def rmse(a: Image.Image, b: Image.Image) -> float:
    if a.size != b.size:
        b = b.resize(a.size, Image.Resampling.BILINEAR)
    aa = np.asarray(a.convert("RGBA"), dtype=np.float32)
    bb = np.asarray(b.convert("RGBA"), dtype=np.float32)
    # Premultiply RGB by alpha so transparent garbage does not dominate.
    aa[:, :, :3] *= aa[:, :, 3:4] / 255.0
    bb[:, :, :3] *= bb[:, :, 3:4] / 255.0
    return float(np.sqrt(np.mean((aa - bb) ** 2)))


def alpha_coverage(img: Image.Image, threshold: int = 8) -> float:
    arr = np.asarray(img.convert("RGBA"))
    return float((arr[:, :, 3] > threshold).sum() / (arr.shape[0] * arr.shape[1]))


def analyze_frames(frames: Sequence[FrameRecord], meta: Dict[str, Any], duplicate_threshold: float = 1.25,
                   loop_rmse_threshold: float = 20.0, foot_drift_threshold: float = 3.0, center_drift_threshold: float = 8.0) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    prev: Optional[FrameRecord] = None
    diffs: List[float] = []
    duplicates: List[int] = []

    for fr in frames:
        bbox = alpha_bbox(fr.image)
        coverage = alpha_coverage(fr.image)
        mean = masked_mean_rgb(fr.image)
        rec: Dict[str, Any] = {
            "index": fr.index,
            "name": fr.name,
            "width": fr.image.width,
            "height": fr.image.height,
            "alpha_coverage": coverage,
            "blank": bbox is None,
            "mean_rgb": [round(x, 2) for x in mean],
        }
        if bbox:
            l, t, r, b = bbox
            rec.update({
                "bbox": [l, t, r, b],
                "bbox_width": r - l,
                "bbox_height": b - t,
                "center_x": (l + r) / 2.0,
                "center_y": (t + b) / 2.0,
                "foot_y": b,
                "area_px": int((r - l) * (b - t)),
            })
        if prev is not None:
            d = rmse(prev.image, fr.image)
            rec["prev_rmse"] = round(d, 3)
            diffs.append(d)
            if d <= duplicate_threshold:
                duplicates.append(fr.index)
        rows.append(rec)
        prev = fr

    nonblank = [r for r in rows if not r["blank"]]
    def values(key: str) -> List[float]:
        return [float(r[key]) for r in nonblank if key in r]

    center_x = values("center_x")
    foot_y = values("foot_y")
    area = values("area_px")
    coverage = [float(r["alpha_coverage"]) for r in rows]
    means = np.array([r["mean_rgb"] for r in rows], dtype=np.float32) if rows else np.zeros((0, 3), dtype=np.float32)

    loop_rmse = rmse(frames[0].image, frames[-1].image) if len(frames) > 1 else 0.0
    noise_count = 0
    total_pixels = 0
    for fr in frames:
        arr = np.asarray(fr.image)
        if arr.shape[2] == 4:
            alpha = arr[:, :, 3]
            noise_count += ((alpha > 0) & (alpha < 16)).sum()
            total_pixels += alpha.size
    alpha_cleanliness_val = float(noise_count / max(1, total_pixels))
    brightness = means.mean(axis=1) if len(means) else np.array([])

    metrics = {
        "frame_count": len(frames),
        "cell_width": int(meta.get("frame_width", frames[0].image.width if frames else 0)),
        "cell_height": int(meta.get("frame_height", frames[0].image.height if frames else 0)),
        "fps": float(meta.get("fps", 12)),
        "blank_frames": [r["index"] for r in rows if r["blank"]],
        "duplicate_frames_after_previous": duplicates,
        "consecutive_rmse_median": float(np.median(diffs)) if diffs else 0.0,
        "loop_seam_rmse": loop_rmse,
        "center_x_stdev_px": float(np.std(center_x)) if center_x else 0.0,
        "foot_y_stdev_px": float(np.std(foot_y)) if foot_y else 0.0,
        "alpha_coverage_cv": float(np.std(coverage) / max(1e-6, np.mean(coverage))) if coverage else 0.0,
        "area_cv": float(np.std(area) / max(1e-6, np.mean(area))) if area else 0.0,
        "brightness_stdev": float(np.std(brightness)) if len(brightness) else 0.0,
        "mean_alpha_coverage": float(np.mean(coverage)) if coverage else 0.0,
        "alpha_cleanliness": alpha_cleanliness_val,
    }

    issues: List[Dict[str, str]] = []
    def issue(level: str, code: str, message: str) -> None:
        issues.append({"level": level, "code": code, "message": message})

    if metrics["blank_frames"]:
        issue("error", "blank_frames", f"Blank/fully transparent frames: {metrics['blank_frames']}")
    if metrics["duplicate_frames_after_previous"]:
        issue("warn", "duplicates", f"Frames nearly identical to previous: {metrics['duplicate_frames_after_previous']}")
    if metrics["foot_y_stdev_px"] > foot_drift_threshold:
        issue("warn", "foot_drift", f"Foot/ground anchor drifts by {metrics['foot_y_stdev_px']:.1f}px stdev; use bottom-center anchoring or autofix.")
    if metrics["center_x_stdev_px"] > center_drift_threshold:
        issue("warn", "center_jitter", f"Horizontal center jitters by {metrics['center_x_stdev_px']:.1f}px stdev.")
    if metrics["area_cv"] > 0.20:
        issue("warn", "silhouette_popping", f"Silhouette area varies {metrics['area_cv']*100:.1f}%; likely WAN identity/scale popping.")
    if metrics["brightness_stdev"] > 18.0:
        issue("warn", "flicker", f"Brightness varies by {metrics['brightness_stdev']:.1f}; use --deflicker or stronger prompt lighting lock.")
    if metrics["loop_seam_rmse"] > max(loop_rmse_threshold, metrics["consecutive_rmse_median"] * 2.25):
        issue("warn", "loop_seam", f"First/last frame seam is high ({metrics['loop_seam_rmse']:.1f}); loop may pop.")
    if metrics["mean_alpha_coverage"] < 0.03:
        issue("warn", "tiny_subject", "Subject occupies very little of the cell; reduce padding/cell size or tighten crop.")
    if metrics["mean_alpha_coverage"] > 0.70:
        issue("warn", "overfilled_cell", "Subject fills most of the cell; clipping risk in large motion frames.")

    suggestions = []
    for it in issues:
        code = it["code"]
        if code == "foot_drift":
            suggestions.append("Run autofix with --stabilize-anchor, or reconvert with --anchor bottom-center --crop-mode global.")
        elif code == "duplicates":
            suggestions.append("Run autofix with --drop-loop-duplicate, or reconvert with --drop-loop-duplicate.")
        elif code == "flicker":
            suggestions.append("Run autofix with --deflicker and use prompts like 'fixed flat lighting, no exposure changes'.")
        elif code == "silhouette_popping":
            suggestions.append("Use a stronger reference image/I2V/VACE workflow, shorter clips, and simpler action prompts.")
        elif code == "loop_seam":
            suggestions.append("Try pingpong loop mode, drop duplicate endpoints, or regenerate as an explicit seamless loop.")
    suggestions = sorted(set(suggestions))

    return {"metrics": metrics, "issues": issues, "suggestions": suggestions, "frames": rows, "metadata": meta}


def make_contact_sheet(frames: Sequence[FrameRecord], out: Path, thumb: int = 96) -> Path:
    if not frames:
        raise ValueError("No frames")
    cols = min(8, len(frames))
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new("RGBA", (cols * thumb, rows * (thumb + 18)), (30, 30, 30, 255))
    draw = ImageDraw.Draw(sheet)
    for i, fr in enumerate(frames):
        img = fr.image.copy()
        img.thumbnail((thumb, thumb), Image.Resampling.LANCZOS)
        x = (i % cols) * thumb + (thumb - img.width) // 2
        y = (i // cols) * (thumb + 18) + (thumb - img.height) // 2
        sheet.alpha_composite(img, (x, y))
        draw.text(((i % cols) * thumb + 4, (i // cols) * (thumb + 18) + thumb), str(fr.index), fill=(255, 255, 255, 255))
    ensure_dir(out.parent)
    sheet.convert("RGB").save(out)
    return out


def write_html_report(report: Dict[str, Any], out: Path, contact_name: str = "qa_contact_sheet.jpg") -> None:
    ensure_dir(out.parent)
    metrics = report["metrics"]
    issues = report["issues"]
    rows = report["frames"]
    issue_html = "".join(f"<li><b>{i['level'].upper()}</b> {i['code']}: {i['message']}</li>" for i in issues) or "<li>No major issues detected.</li>"
    sugg_html = "".join(f"<li>{s}</li>" for s in report.get("suggestions", [])) or "<li>No automatic suggestions.</li>"
    frame_rows = "\n".join(
        f"<tr><td>{r['index']}</td><td>{r.get('alpha_coverage',0):.3f}</td><td>{r.get('center_x','')}</td><td>{r.get('foot_y','')}</td><td>{r.get('prev_rmse','')}</td><td>{'yes' if r.get('blank') else ''}</td></tr>"
        for r in rows
    )
    out.write_text(f"""<!doctype html>
<html><head><meta charset='utf-8'><title>SpriteForge QA Report</title>
<style>body{{font-family:Arial,sans-serif;margin:24px;line-height:1.35}} table{{border-collapse:collapse}} td,th{{border:1px solid #bbb;padding:4px 8px}} code{{background:#eee;padding:2px 4px}} .warn{{color:#9a6200}} .error{{color:#b00020}}</style>
</head><body>
<h1>SpriteForge QA Report</h1>
<p>Generated {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
<h2>Summary</h2>
<pre>{json.dumps(metrics, indent=2)}</pre>
<h2>Issues</h2><ul>{issue_html}</ul>
<h2>Suggested fixes</h2><ul>{sugg_html}</ul>
<h2>Contact sheet</h2><img src="{contact_name}" style="max-width:100%;image-rendering:pixelated">
<h2>Per-frame table</h2>
<table><tr><th>frame</th><th>alpha coverage</th><th>center x</th><th>foot y</th><th>prev RMSE</th><th>blank</th></tr>{frame_rows}</table>
</body></html>""", encoding="utf-8")


from services.sprite_qc_commands import (
    rmse,
    solidify_transparent_rgb,
    smooth_sequence,
    blend_loop_seam,
    stabilize_frame,
    deflicker_frames,
    drop_loop_duplicate,
    pack_frames,
    cmd_autofix,
    cmd_compare,
)

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SpriteForge sprite QA and auto-fix")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("report", help="Analyze a SpriteForge output folder or image-frame folder")
    for name, kwargs in [
        ("--input", {"required": True}), ("--output", {"default": None}),
        ("--duplicate-threshold", {"type": float, "default": 1.25}), ("--thumb", {"type": int, "default": 96}),
        ("--loop-rmse-threshold", {"type": float, "default": 20.0}),
        ("--foot-drift-threshold", {"type": float, "default": 3.0}),
        ("--center-drift-threshold", {"type": float, "default": 8.0}),
    ]:
        s.add_argument(name, **kwargs)
    s.set_defaults(func=cmd_report)

    s = sub.add_parser("autofix", help="Make a stabilized fixed copy of a sprite folder")
    for name, kwargs in [
        ("--input", {"required": True}), ("--output", {"default": None}), ("--fps", {"type": float, "default": None}),
        ("--animation", {"default": None}), ("--drop-loop-duplicate", {"action": "store_true"}),
        ("--duplicate-threshold", {"type": float, "default": 1.25}), ("--stabilize-anchor", {"action": "store_true"}),
        ("--baseline-margin", {"type": int, "default": 4}), ("--deflicker", {"action": "store_true"}),
        ("--solidify", {"type": int, "default": 2}), ("--blend-loop-frames", {"type": int, "default": 0}),
        ("--thumb", {"type": int, "default": 96}), ("--sharpen", {"action": "store_true", "help": "Sharpen sprite edges"}),
    ]:
        s.add_argument(name, **kwargs)
    s.set_defaults(func=cmd_autofix)


    s = sub.add_parser("compare", help="Compare two sprite outputs frame-by-frame")
    s.add_argument("--a", required=True)
    s.add_argument("--b", required=True)
    s.add_argument("--output", default=None)
    s.set_defaults(func=cmd_compare)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
