#!/usr/bin/env python3
"""SpriteForge Quality Control tools.

Adds production QA for game-sprite outputs:
- foot/ground jitter
- horizontal center jitter
- frame-to-frame motion consistency
- loop seam score
- duplicate/near-empty frame detection
- color drift
- edge/halo risk
- contact sheet and HTML report
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def natural_key(path: Path) -> list:
    import re
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


@dataclass
class FrameMetric:
    index: int
    bbox: Optional[Tuple[int, int, int, int]]
    alpha_coverage: float
    center_x: Optional[float]
    center_y: Optional[float]
    bottom_y: Optional[float]
    width: Optional[int]
    height: Optional[int]
    opaque_rgb_mean: Tuple[float, float, float]
    edge_alpha_ratio: float
    next_diff: Optional[float] = None


def load_metadata(sprite_dir: Path) -> Dict[str, Any]:
    meta_path = sprite_dir / "sheet.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing {meta_path}. Expected a SpriteForge output folder.")
    return json.loads(meta_path.read_text(encoding="utf-8"))


def frames_from_processed(sprite_dir: Path) -> List[Image.Image]:
    for sub in ["frames_processed", "frames", "cleaned_frames"]:
        d = sprite_dir / sub
        if d.exists():
            files = sorted([p for p in d.iterdir() if p.suffix.lower() in IMAGE_EXTS], key=natural_key)
            if files:
                return [Image.open(p).convert("RGBA") for p in files]
    return []


def frames_from_sheet(sprite_dir: Path, meta: Dict[str, Any]) -> List[Image.Image]:
    sheet_path = sprite_dir / meta.get("image", "sheet.png")
    if not sheet_path.exists():
        raise FileNotFoundError(f"Missing spritesheet image: {sheet_path}")
    sheet = Image.open(sheet_path).convert("RGBA")
    fw = int(meta["frame_width"])
    fh = int(meta["frame_height"])
    count = int(meta["frame_count"])
    cols = int(meta.get("columns", max(1, sheet.width // fw)))
    frames: List[Image.Image] = []
    for i in range(count):
        x = (i % cols) * fw
        y = (i // cols) * fh
        frames.append(sheet.crop((x, y, x + fw, y + fh)))
    return frames


def load_frames(sprite_dir: Path, prefer_processed: bool = True) -> Tuple[Dict[str, Any], List[Image.Image]]:
    meta = load_metadata(sprite_dir)
    frames = frames_from_processed(sprite_dir) if prefer_processed else []
    if not frames:
        frames = frames_from_sheet(sprite_dir, meta)
    if not frames:
        raise RuntimeError("No frames found.")
    return meta, frames


def alpha_bbox(img: Image.Image, threshold: int = 8) -> Optional[Tuple[int, int, int, int]]:
    arr = np.asarray(img.convert("RGBA"))
    alpha = arr[:, :, 3]
    ys, xs = np.where(alpha > threshold)
    if len(xs) == 0 or len(ys) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def frame_diff(a: Image.Image, b: Image.Image) -> float:
    a_arr = np.asarray(a.convert("RGBA"), dtype=np.float32)
    b_arr = np.asarray(b.convert("RGBA"), dtype=np.float32)
    if a_arr.shape != b_arr.shape:
        b = b.resize(a.size, Image.Resampling.BILINEAR)
        b_arr = np.asarray(b.convert("RGBA"), dtype=np.float32)
    # Weight alpha heavily because silhouette flicker matters for sprites.
    rgb = np.mean(np.abs(a_arr[:, :, :3] - b_arr[:, :, :3])) / 255.0
    alpha = np.mean(np.abs(a_arr[:, :, 3] - b_arr[:, :, 3])) / 255.0
    return float(rgb * 0.4 + alpha * 0.6)


def edge_alpha_ratio(img: Image.Image) -> float:
    arr = np.asarray(img.convert("RGBA"), dtype=np.uint8)
    alpha = arr[:, :, 3]
    nonzero = alpha > 0
    if not np.any(nonzero):
        return 0.0
    semi = (alpha > 0) & (alpha < 245)
    return float(np.sum(semi) / max(1, np.sum(nonzero)))


def opaque_mean_rgb(img: Image.Image, threshold: int = 64) -> Tuple[float, float, float]:
    arr = np.asarray(img.convert("RGBA"), dtype=np.float32)
    mask = arr[:, :, 3] > threshold
    if not np.any(mask):
        return (0.0, 0.0, 0.0)
    vals = arr[:, :, :3][mask]
    return tuple(float(x) for x in vals.mean(axis=0))  # type: ignore[return-value]


def measure_frames(frames: Sequence[Image.Image], alpha_threshold: int = 8) -> List[FrameMetric]:
    metrics: List[FrameMetric] = []
    for i, img in enumerate(frames):
        rgba = img.convert("RGBA")
        arr = np.asarray(rgba)
        alpha = arr[:, :, 3]
        coverage = float(np.sum(alpha > alpha_threshold) / alpha.size)
        bbox = alpha_bbox(rgba, alpha_threshold)
        if bbox:
            l, t, r, b = bbox
            cx = (l + r) * 0.5
            cy = (t + b) * 0.5
            w = r - l
            h = b - t
            bottom = float(b)
        else:
            cx = cy = bottom = None
            w = h = None
        metrics.append(FrameMetric(
            index=i,
            bbox=bbox,
            alpha_coverage=coverage,
            center_x=cx,
            center_y=cy,
            bottom_y=bottom,
            width=w,
            height=h,
            opaque_rgb_mean=opaque_mean_rgb(rgba),
            edge_alpha_ratio=edge_alpha_ratio(rgba),
        ))
    for i in range(len(metrics) - 1):
        metrics[i].next_diff = frame_diff(frames[i], frames[i + 1])
    return metrics


def stdev(values: Sequence[float]) -> float:
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return float(statistics.pstdev(vals)) if len(vals) > 1 else 0.0


def max_jump(values: Sequence[Optional[float]]) -> float:
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return 0.0
    return float(max(abs(vals[i + 1] - vals[i]) for i in range(len(vals) - 1)))


def summarize(metrics: Sequence[FrameMetric], frames: Sequence[Image.Image], meta: Dict[str, Any]) -> Dict[str, Any]:
    bottoms = [m.bottom_y for m in metrics]
    centers = [m.center_x for m in metrics]
    heights = [float(m.height) for m in metrics if m.height]
    widths = [float(m.width) for m in metrics if m.width]
    coverage = [m.alpha_coverage for m in metrics]
    diffs = [m.next_diff for m in metrics if m.next_diff is not None]
    edge_ratios = [m.edge_alpha_ratio for m in metrics]
    rgb = np.array([m.opaque_rgb_mean for m in metrics], dtype=np.float32)

    loop_seam = frame_diff(frames[-1], frames[0]) if len(frames) > 1 else 0.0
    median_step = float(np.median(diffs)) if diffs else 0.0
    duplicate_frames = int(sum(1 for d in diffs if d < 0.004))
    empty_frames = int(sum(1 for c in coverage if c < 0.001))
    color_drift = float(np.mean(np.std(rgb, axis=0)) / 255.0) if len(rgb) else 0.0

    cell_w = int(meta.get("frame_width", frames[0].width))
    cell_h = int(meta.get("frame_height", frames[0].height))

    bottom_jitter = stdev([b for b in bottoms if b is not None])
    center_jitter = stdev([c for c in centers if c is not None])
    height_jitter = stdev(heights)
    width_jitter = stdev(widths)
    max_bottom_jump = max_jump(bottoms)
    max_center_jump = max_jump(centers)

    score = 100.0
    score -= min(25.0, bottom_jitter / max(1.0, cell_h) * 350.0)
    score -= min(20.0, center_jitter / max(1.0, cell_w) * 250.0)
    score -= min(20.0, loop_seam * 90.0)
    score -= min(10.0, duplicate_frames * 2.0)
    score -= min(15.0, color_drift * 100.0)
    score -= min(10.0, float(np.mean(edge_ratios)) * 30.0 if edge_ratios else 0.0)
    score -= empty_frames * 20.0
    score = max(0.0, min(100.0, score))

    suggestions: List[str] = []
    if empty_frames:
        suggestions.append(f"{empty_frames} empty/near-empty frame(s) detected. Check chroma key or frame extraction.")
    if bottom_jitter > cell_h * 0.025:
        suggestions.append("Foot/ground jitter is high. Use bottom-center anchoring, stronger pose guidance, or render from Blender with a locked ground plane.")
    if center_jitter > cell_w * 0.035:
        suggestions.append("Horizontal center drift is visible. Use locked camera wording and global crop; avoid WAN camera movement.")
    if loop_seam > max(0.04, median_step * 1.75):
        suggestions.append("Loop seam is rough. Try --drop-loop-duplicate, generate one extra cycle, or pick a cleaner start/end window.")
    if duplicate_frames > max(1, len(frames) // 8):
        suggestions.append("Many adjacent frames are nearly identical. Lower FPS or trim duplicated output.")
    if color_drift > 0.055:
        suggestions.append("Color drift is high. Use a reference image workflow, stricter prompt, lower motion complexity, or same seed/template across actions.")
    if edge_ratios and float(np.mean(edge_ratios)) > 0.35:
        suggestions.append("High semi-transparent edge ratio. Keep --solidify enabled and test against dark/light backgrounds.")
    if not suggestions:
        suggestions.append("QC looks usable. Next step: build an atlas/export to engine and test in-game at actual scale.")

    return {
        "score": round(score, 2),
        "grade": "A" if score >= 88 else "B" if score >= 74 else "C" if score >= 60 else "D",
        "frame_count": len(frames),
        "cell_width": cell_w,
        "cell_height": cell_h,
        "fps": meta.get("fps"),
        "bottom_jitter_px": round(bottom_jitter, 3),
        "center_jitter_px": round(center_jitter, 3),
        "height_jitter_px": round(height_jitter, 3),
        "width_jitter_px": round(width_jitter, 3),
        "max_bottom_jump_px": round(max_bottom_jump, 3),
        "max_center_jump_px": round(max_center_jump, 3),
        "median_frame_diff": round(median_step, 6),
        "loop_seam_diff": round(loop_seam, 6),
        "loop_seam_ratio_to_median": round(loop_seam / median_step, 3) if median_step > 0 else None,
        "duplicate_adjacent_frames": duplicate_frames,
        "empty_frames": empty_frames,
        "color_drift": round(color_drift, 6),
        "mean_edge_alpha_ratio": round(float(np.mean(edge_ratios)) if edge_ratios else 0.0, 6),
        "suggestions": suggestions,
    }


def write_metrics_csv(path: Path, metrics: Sequence[FrameMetric]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["index", "bbox_l", "bbox_t", "bbox_r", "bbox_b", "alpha_coverage", "center_x", "center_y", "bottom_y", "width", "height", "mean_r", "mean_g", "mean_b", "edge_alpha_ratio", "next_diff"])
        for m in metrics:
            bbox = m.bbox or (None, None, None, None)
            w.writerow([m.index, *bbox, m.alpha_coverage, m.center_x, m.center_y, m.bottom_y, m.width, m.height, *m.opaque_rgb_mean, m.edge_alpha_ratio, m.next_diff])


def make_contact_sheet(path: Path, frames: Sequence[Image.Image], metrics: Sequence[FrameMetric], cols: int = 8, thumb: int = 128) -> None:
    if not frames:
        return
    cols = max(1, cols)
    rows = math.ceil(len(frames) / cols)
    label_h = 22
    sheet = Image.new("RGBA", (cols * thumb, rows * (thumb + label_h)), (30, 30, 30, 255))
    d = ImageDraw.Draw(sheet)
    for i, img in enumerate(frames):
        x = (i % cols) * thumb
        y = (i // cols) * (thumb + label_h)
        im = img.convert("RGBA")
        scale = min(thumb / im.width, thumb / im.height)
        rw = max(1, int(im.width * scale))
        rh = max(1, int(im.height * scale))
        im = im.resize((rw, rh), Image.Resampling.LANCZOS)
        px = x + (thumb - rw) // 2
        py = y + (thumb - rh) // 2
        checker = Image.new("RGBA", (thumb, thumb), (60, 60, 60, 255))
        cd = ImageDraw.Draw(checker)
        step = max(8, thumb // 8)
        for yy in range(0, thumb, step):
            for xx in range(0, thumb, step):
                if (xx // step + yy // step) % 2:
                    cd.rectangle((xx, yy, xx + step - 1, yy + step - 1), fill=(80, 80, 80, 255))
        checker.alpha_composite(im, (px - x, py - y))
        sheet.alpha_composite(checker, (x, y))
        m = metrics[i]
        label = f"{i:02d} b={m.bottom_y:.0f}" if m.bottom_y is not None else f"{i:02d} empty"
        d.text((x + 4, y + thumb + 3), label, fill=(235, 235, 235, 255))
    sheet.convert("RGB").save(path)


def make_html(path: Path, sprite_dir: Path, summary: Dict[str, Any], metric_csv: str, contact_sheet: str) -> None:
    suggestions = "".join(f"<li>{html.escape(s)}</li>" for s in summary.get("suggestions", []))
    rows = "".join(
        f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>"
        for k, v in summary.items()
        if k != "suggestions"
    )
    doc = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>SpriteForge QC Report</title>
<style>
body {{ font-family: system-ui, Segoe UI, Arial, sans-serif; margin: 24px; background: #151515; color: #eee; }}
table {{ border-collapse: collapse; margin: 1rem 0; }}
th, td {{ border: 1px solid #444; padding: 6px 10px; text-align: left; }}
th {{ background: #242424; }}
.bad {{ color: #ff9b9b; }} .good {{ color: #9bffb4; }}
img {{ max-width: 100%; background: #222; }}
a {{ color: #9bd0ff; }}
</style></head><body>
<h1>SpriteForge QC Report</h1>
<p><strong>Sprite folder:</strong> {html.escape(str(sprite_dir))}</p>
<h2>Score: {summary.get('score')} / 100 — Grade {html.escape(str(summary.get('grade')))}</h2>
<table>{rows}</table>
<h2>Suggestions</h2><ul>{suggestions}</ul>
<h2>Contact Sheet</h2>
<p><img src="{html.escape(contact_sheet)}" alt="quality contact sheet"></p>
<p><a href="{html.escape(metric_csv)}">metrics.csv</a></p>
</body></html>"""
    path.write_text(doc, encoding="utf-8")


def quality_report(sprite_dir: Path, output: Optional[Path], fail_under: Optional[float], prefer_processed: bool = True) -> Dict[str, Any]:
    sprite_dir = sprite_dir.resolve()
    meta, frames = load_frames(sprite_dir, prefer_processed=prefer_processed)
    out = (output.resolve() if output else sprite_dir / "quality")
    out.mkdir(parents=True, exist_ok=True)
    metrics = measure_frames(frames)
    summary = summarize(metrics, frames, meta)
    (out / "quality_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_metrics_csv(out / "metrics.csv", metrics)
    make_contact_sheet(out / "quality_contact_sheet.png", frames, metrics)
    make_html(out / "quality_report.html", sprite_dir, summary, "metrics.csv", "quality_contact_sheet.png")
    print(f"QC score: {summary['score']} / 100 grade {summary['grade']}")
    print(f"Report: {out / 'quality_report.html'}")
    print("Suggestions:")
    for s in summary.get("suggestions", []):
        print(f" - {s}")
    if fail_under is not None and float(summary["score"]) < fail_under:
        raise SystemExit(2)
    return summary


def batch_quality(root: Path, glob_pattern: str, output: Optional[Path], fail_under: Optional[float]) -> None:
    root = root.resolve()
    targets = []
    for meta in root.rglob("sheet.json"):
        if glob_pattern and not meta.parent.match(glob_pattern):
            # pathlib match checks from the right side; keep broad default behavior.
            pass
        targets.append(meta.parent)
    if not targets:
        raise RuntimeError(f"No SpriteForge sheet.json files found under {root}")
    out = output.resolve() if output else root / "quality_batch"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for target in targets:
        print(f"\nChecking {target}")
        qout = out / target.name
        try:
            summary = quality_report(target, qout, None)
            rows.append({"sprite_dir": str(target), **summary})
        except Exception as exc:
            rows.append({"sprite_dir": str(target), "error": str(exc), "score": 0})
    (out / "batch_quality.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    with (out / "batch_quality.csv").open("w", newline="", encoding="utf-8") as f:
        keys = sorted({k for row in rows for k in row.keys() if k != "suggestions"})
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in keys})
    failures = [r for r in rows if fail_under is not None and float(r.get("score", 0)) < fail_under]
    print(f"\nBatch report: {out / 'batch_quality.json'}")
    if failures:
        print(f"{len(failures)} sprite output(s) under threshold {fail_under}.")
        raise SystemExit(2)




def cmd_quality(args: argparse.Namespace) -> int:
    # README-facing command: default reports go into sprite_dir/quality.
    if not getattr(args, "output", None):
        args.output = str(Path(args.sprite_dir).resolve() / "quality")
    # Fill optional args used by cmd_check when called through the compatibility alias.
    for name, default in [
        ("alpha_threshold", 8), ("bottom_jitter_warn", 4.0), ("center_jitter_warn", 24.0),
        ("loop_diff_warn", 32.0), ("jump_diff_warn", 55.0), ("min_frames", 4),
        ("thumb", 144), ("columns", 6), ("strict", False), ("fail_on_warn", False),
    ]:
        if not hasattr(args, name):
            setattr(args, name, default)
    return cmd_check(args)


def cmd_batch(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    output = Path(args.output).resolve() if args.output else root / "quality_batch"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    status_code = 0
    candidates = [p for p in root.rglob("sheet.json") if p.is_file()]
    for meta_path in candidates:
        sprite_dir = meta_path.parent
        out = output / sprite_dir.name
        ns = argparse.Namespace(sprite_dir=str(sprite_dir), output=str(out), fail_under=args.fail_under)
        code = cmd_quality(ns)
        try:
            report = json.loads((out / "quality_report.json").read_text(encoding="utf-8"))
            rows.append({"sprite_dir": str(sprite_dir), "status": report.get("status"), "score": report.get("score"), **report.get("summary", {})})
        except Exception as exc:
            rows.append({"sprite_dir": str(sprite_dir), "status": "error", "score": 0, "error": str(exc)})
            code = 2
        status_code = max(status_code, code)
    summary = {"root": str(root), "count": len(rows), "items": rows}
    (output / "quality_batch_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    html_rows = "".join(f"<tr><td>{r.get('sprite_dir')}</td><td>{r.get('status')}</td><td>{r.get('score')}</td><td>{r.get('loop_diff','')}</td><td>{r.get('bottom_jitter_px','')}</td></tr>" for r in rows)
    (output / "quality_batch_report.html").write_text(f"<!doctype html><html><body><h1>SpriteForge QC Batch</h1><table border='1'><tr><th>Sprite</th><th>Status</th><th>Score</th><th>Loop diff</th><th>Bottom jitter</th></tr>{html_rows}</table></body></html>", encoding="utf-8")
    print(f"Batch QC: {len(rows)} sprite outputs checked")
    print(f"Report: {output / 'quality_batch_report.html'}")
    return status_code

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SpriteForge quality-control tools")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("quality", help="Create a QC report for one SpriteForge output folder")
    s.add_argument("--sprite-dir", required=True)
    s.add_argument("--output", default=None)
    s.add_argument("--fail-under", type=float, default=None)
    s.add_argument("--sheet-only", action="store_true", help="Ignore frames_processed and reconstruct from sheet.png")
    s.set_defaults(func=lambda a: quality_report(Path(a.sprite_dir), Path(a.output) if a.output else None, a.fail_under, prefer_processed=not a.sheet_only))

    s = sub.add_parser("batch", help="QC every SpriteForge output found under a root folder")
    s.add_argument("--root", default="output")
    s.add_argument("--glob", default="*")
    s.add_argument("--output", default=None)
    s.add_argument("--fail-under", type=float, default=None)
    s.set_defaults(func=lambda a: batch_quality(Path(a.root), a.glob, Path(a.output) if a.output else None, a.fail_under))

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
