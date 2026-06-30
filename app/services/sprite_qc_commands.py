from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from spriteforge_qc import (
    FrameRecord,
    ensure_dir,
    alpha_bbox,
    load_input,
    load_sheet_frames,
    analyze_frames,
    make_contact_sheet,
    write_html_report,
)

ROOT = Path(__file__).resolve().parent.parent

def rmse(a: Image.Image, b: Image.Image) -> float:
    if a.size != b.size:
        b = b.resize(a.size, Image.Resampling.BILINEAR)
    aa = np.asarray(a.convert("RGBA"), dtype=np.float32)
    bb = np.asarray(b.convert("RGBA"), dtype=np.float32)
    aa[:, :, :3] *= aa[:, :, 3:4] / 255.0
    bb[:, :, :3] *= bb[:, :, 3:4] / 255.0
    return float(np.sqrt(np.mean((aa - bb) ** 2)))


def solidify_transparent_rgb(img: Image.Image, radius: int = 2) -> Image.Image:
    if radius <= 0:
        return img.convert("RGBA")
    img = img.convert("RGBA")
    arr = np.asarray(img).copy()
    alpha = arr[:, :, 3]
    rgb_img = Image.fromarray(arr[:, :, :3], mode="RGB")
    blur = rgb_img.filter(ImageFilter.GaussianBlur(radius=radius))
    blur_arr = np.asarray(blur)
    transparent = alpha == 0
    arr[:, :, :3][transparent] = blur_arr[transparent]
    return Image.fromarray(arr, mode="RGBA")


def smooth_sequence(coords: List[float], window_size: int = 5) -> List[float]:
    if len(coords) < window_size:
        return coords
    smoothed = []
    half = window_size // 2
    for idx in range(len(coords)):
        start_idx = max(0, idx - half)
        end_idx = min(len(coords), idx + half + 1)
        smoothed.append(float(np.median(coords[start_idx:end_idx])))
    return smoothed


def blend_loop_seam(frames: List[FrameRecord], blend_frames: int) -> List[FrameRecord]:
    if blend_frames <= 0 or len(frames) <= blend_frames * 2:
        return frames
    out = list(frames)
    n = len(frames)
    for i in range(blend_frames):
        idx_start = i
        idx_end = n - blend_frames + i
        alpha = (i + 0.5) / blend_frames
        blended = Image.blend(frames[idx_end].image, frames[idx_start].image, alpha)
        out[idx_end] = FrameRecord(frames[idx_end].index, blended, frames[idx_end].name)
    return out


def stabilize_frame(img: Image.Image, target_anchor: Tuple[float, float], bbox: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
    img = img.convert("RGBA")
    bbox = bbox or alpha_bbox(img)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    if not bbox:
        return img
    l, t, r, b = bbox
    src_anchor_x = (l + r) / 2.0
    src_anchor_y = float(b)
    dx = int(round(target_anchor[0] - src_anchor_x))
    dy = int(round(target_anchor[1] - src_anchor_y))
    out.alpha_composite(img, (dx, dy))
    return out


def deflicker_frames(frames: Sequence[FrameRecord]) -> List[FrameRecord]:
    from spriteforge_qc import masked_mean_rgb
    means = []
    for fr in frames:
        means.append(masked_mean_rgb(fr.image))
    arr = np.array(means, dtype=np.float32)
    lum = arr.mean(axis=1)
    target = float(np.median(lum[lum > 1])) if (lum > 1).any() else float(np.median(lum))
    out: List[FrameRecord] = []
    for fr, l in zip(frames, lum):
        img = fr.image.convert("RGBA")
        if l <= 1:
            out.append(fr)
            continue
        scale = np.clip(target / l, 0.75, 1.33)
        data = np.asarray(img).astype(np.float32)
        mask = data[:, :, 3] > 8
        data[:, :, :3][mask] = np.clip(data[:, :, :3][mask] * scale, 0, 255)
        out.append(FrameRecord(fr.index, Image.fromarray(data.astype(np.uint8), mode="RGBA"), fr.name))
    return out


def drop_loop_duplicate(frames: List[FrameRecord], threshold: float = 1.25) -> List[FrameRecord]:
    if len(frames) > 2 and rmse(frames[0].image, frames[-1].image) <= threshold:
        return frames[:-1]
    return frames


def pack_frames(frames: Sequence[FrameRecord], out_dir: Path, fps: float, animation: str) -> None:
    ensure_dir(out_dir)
    if not frames:
        raise ValueError("No frames to pack")
    w, h = frames[0].image.size
    cols = math.ceil(math.sqrt(len(frames)))
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new("RGBA", (cols * w, rows * h), (0, 0, 0, 0))
    frames_dir = out_dir / "frames_fixed"
    ensure_dir(frames_dir)
    for i, fr in enumerate(frames):
        img = fr.image.convert("RGBA")
        sheet.alpha_composite(img, ((i % cols) * w, (i // cols) * h))
        img.save(frames_dir / f"frame_{i:04d}.png")
    sheet.save(out_dir / "sheet.png")
    duration_ms = int(round(1000 / fps)) if fps else 83
    meta = {
        "image": "sheet.png",
        "animation": animation,
        "frame_width": w,
        "frame_height": h,
        "frame_count": len(frames),
        "fps": fps,
        "columns": cols,
        "rows": rows,
        "frames": [
            {"index": i, "name": f"{animation}_{i:04d}", "x": (i % cols) * w, "y": (i // cols) * h, "w": w, "h": h, "duration_ms": duration_ms}
            for i in range(len(frames))
        ],
    }
    (out_dir / "sheet.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    imgs = [fr.image.convert("RGBA") for fr in frames]
    if imgs:
        imgs[0].save(out_dir / "preview.gif", save_all=True, append_images=imgs[1:], duration=duration_ms, loop=0, disposal=2)


def cmd_autofix(args: argparse.Namespace) -> None:
    src = Path(args.input).resolve()
    frames, meta = load_input(src)
    fps = float(args.fps or meta.get("fps", 12))
    out_dir = Path(args.output).resolve() if args.output else (src.parent / f"{src.name}_fixed")
    fixed = list(frames)
    if args.drop_loop_duplicate:
        fixed = drop_loop_duplicate(fixed, threshold=args.duplicate_threshold)
    if args.stabilize_anchor:
        w, h = fixed[0].image.size
        target_anchor = (w * 0.5, h - args.baseline_margin)
        raw_anchors = []
        for fr in fixed:
            bbox = alpha_bbox(fr.image)
            if bbox:
                l, t, r, b = bbox
                raw_anchors.append(((l + r) / 2.0, float(b)))
            else:
                raw_anchors.append((w * 0.5, h - args.baseline_margin))
        xs = [x for x, y in raw_anchors]
        ys = [y for x, y in raw_anchors]
        smoothed_xs = smooth_sequence(xs, window_size=5)
        smoothed_ys = smooth_sequence(ys, window_size=5)
        
        new_fixed = []
        for i, fr in enumerate(fixed):
            src_anchor_x = smoothed_xs[i]
            src_anchor_y = smoothed_ys[i]
            dx = int(round(target_anchor[0] - src_anchor_x))
            dy = int(round(target_anchor[1] - src_anchor_y))
            
            out_img = Image.new("RGBA", fr.image.size, (0, 0, 0, 0))
            out_img.alpha_composite(fr.image.convert("RGBA"), (dx, dy))
            new_fixed.append(FrameRecord(fr.index, out_img, fr.name))
        fixed = new_fixed
    if args.deflicker:
        fixed = deflicker_frames(fixed)
    if getattr(args, "sharpen", False):
        from PIL import ImageFilter
        fixed = [FrameRecord(fr.index, fr.image.filter(ImageFilter.SHARPEN), fr.name) for fr in fixed]
    if args.solidify > 0:
        fixed = [FrameRecord(i, solidify_transparent_rgb(fr.image, args.solidify), fr.name) for i, fr in enumerate(fixed)]
    if getattr(args, "blend_loop_frames", 0) > 0:
        fixed = blend_loop_seam(fixed, args.blend_loop_frames)
    pack_frames(fixed, out_dir, fps=fps, animation=args.animation or str(meta.get("animation", src.name + "_fixed")))
    new_frames, new_meta = load_sheet_frames(out_dir)
    report = analyze_frames(new_frames, new_meta, duplicate_threshold=args.duplicate_threshold)
    ensure_dir(out_dir / "qa")
    (out_dir / "qa" / "qa_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    make_contact_sheet(new_frames, out_dir / "qa" / "qa_contact_sheet.jpg", thumb=args.thumb)
    write_html_report(report, out_dir / "qa" / "qa_report.html")
    print(f"Fixed sprite output: {out_dir}")
    print(f"QA report: {out_dir / 'qa' / 'qa_report.html'}")


def cmd_compare(args: argparse.Namespace) -> None:
    a_path = Path(args.a).resolve()
    b_path = Path(args.b).resolve()
    a_frames, a_meta = load_input(a_path)
    b_frames, b_meta = load_input(b_path)
    count = min(len(a_frames), len(b_frames))
    rows = []
    for i in range(count):
        rows.append({"index": i, "rmse": round(rmse(a_frames[i].image, b_frames[i].image), 4)})
    metrics = {
        "a": str(a_path),
        "b": str(b_path),
        "a_frame_count": len(a_frames),
        "b_frame_count": len(b_frames),
        "compared_frames": count,
        "mean_rmse": round(float(np.mean([r["rmse"] for r in rows])) if rows else 0.0, 4),
        "max_rmse": round(float(np.max([r["rmse"] for r in rows])) if rows else 0.0, 4),
        "frame_count_delta": len(b_frames) - len(a_frames),
    }
    out_dir = Path(args.output).resolve() if args.output else (ROOT / "output" / "sprite_compare" / f"compare_{int(time.time())}")
    ensure_dir(out_dir)
    report = {"metrics": metrics, "frames": rows}
    (out_dir / "compare_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    frame_rows = "".join(f"<tr><td>{r['index']}</td><td>{r['rmse']}</td></tr>" for r in rows)
    (out_dir / "compare_report.html").write_text(f"<!doctype html><html><body><h1>SpriteForge Compare</h1><pre>{json.dumps(metrics, indent=2)}</pre><table border='1'><tr><th>Frame</th><th>RMSE</th></tr>{frame_rows}</table></body></html>", encoding="utf-8")
    print(f"Compare report: {out_dir / 'compare_report.html'}")
    print(json.dumps(metrics, indent=2))
