#!/usr/bin/env python3
"""Compare two SpriteForge sprite outputs frame-by-frame.

v2 adds:
- Side-by-side PNG grid (column A | column B, one row per frame)
- Per-pixel diff heatmap (red = large diff, green = small diff)
- QA delta table from sheet.json metadata
- Frame-alignment warnings
- Rich self-contained HTML report with embedded SVG bar chart
"""
from __future__ import annotations
import argparse, base64, io, json, math, re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from spriteforge_utils import natural_key, load_meta

IMAGE_EXTS = {'.png','.jpg','.jpeg','.webp','.bmp'}

# ---------------------------------------------------------------------------
# Helpers shared with other modules
# ---------------------------------------------------------------------------


def load_frames(sprite_dir: Path) -> List[Image.Image]:
    for folder in ['frames_processed', 'frames', 'cleaned_frames']:
        d = sprite_dir / folder
        if d.exists():
            files = sorted(
                [p for p in d.iterdir() if p.suffix.lower() in IMAGE_EXTS],
                key=natural_key,
            )
            if files:
                return [Image.open(p).convert('RGBA') for p in files]
    meta = load_meta(sprite_dir)
    sheet_path = sprite_dir / meta.get('image', 'sheet.png')
    if not sheet_path.exists():
        sheet_path = sprite_dir / 'sheet.png'
    sheet = Image.open(sheet_path).convert('RGBA')
    frames = []
    if meta.get('frames'):
        for fr in meta['frames']:
            x, y = int(fr['x']), int(fr['y'])
            w = int(fr.get('w', meta['frame_width']))
            h = int(fr.get('h', meta['frame_height']))
            frames.append(sheet.crop((x, y, x + w, y + h)))
    else:
        fw = int(meta['frame_width'])
        fh = int(meta['frame_height'])
        count = int(meta['frame_count'])
        cols = int(meta.get('columns', 1))
        for i in range(count):
            x = (i % cols) * fw
            y = (i // cols) * fh
            frames.append(sheet.crop((x, y, x + fw, y + fh)))
    return frames


# ---------------------------------------------------------------------------
# Core diff
# ---------------------------------------------------------------------------

def frame_diff(a: Image.Image, b: Image.Image) -> float:
    if a.size != b.size:
        b = b.resize(a.size, Image.Resampling.LANCZOS)
    aa = np.asarray(a.convert('RGBA'), dtype=np.int16)
    bb = np.asarray(b.convert('RGBA'), dtype=np.int16)
    return float(np.mean(np.abs(aa - bb)))


# ---------------------------------------------------------------------------
# Visual helpers
# ---------------------------------------------------------------------------

def _label_frame(img: Image.Image, label: str, font_size: int = 14) -> Image.Image:
    """Return a copy of *img* with a small label bar on top."""
    bar_h = font_size + 6
    w, h = img.size
    out = Image.new('RGBA', (w, h + bar_h), (30, 30, 30, 255))
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
    draw.text((4, 3), label, fill=(220, 220, 220, 255), font=font)
    out.paste(img, (0, bar_h))
    return out


def make_sidebyside_grid(
    af: List[Image.Image],
    bf: List[Image.Image],
    a_label: str = "A",
    b_label: str = "B",
    max_frames: int = 16,
    thumb_w: int = 128,
) -> Image.Image:
    """Return a two-column PNG grid: column A | column B, one row per frame."""
    n = min(len(af), len(bf), max_frames)
    if n == 0:
        return Image.new('RGBA', (thumb_w * 2, 64), (40, 40, 40, 255))

    # Compute uniform cell size
    cell_w = thumb_w
    # Preserve aspect ratio of first frame
    ref = af[0]
    cell_h = int(cell_w * ref.height / max(ref.width, 1))
    label_bar = 20
    pad = 2
    col_w = cell_w + pad * 2
    row_h = cell_h + label_bar + pad * 2

    grid_w = col_w * 2 + 4  # 4px divider
    grid_h = row_h * n + label_bar  # header row

    grid = Image.new('RGBA', (grid_w, grid_h), (25, 25, 25, 255))
    draw = ImageDraw.Draw(grid)
    try:
        font = ImageFont.truetype("arial.ttf", 12)
        font_hdr = ImageFont.truetype("arial.ttf", 13)
    except Exception:
        font = ImageFont.load_default()
        font_hdr = font

    # Header labels
    draw.rectangle([0, 0, col_w - 1, label_bar - 1], fill=(45, 45, 60, 255))
    draw.rectangle([col_w + 4, 0, grid_w - 1, label_bar - 1], fill=(45, 60, 45, 255))
    draw.text((col_w // 4, 3), a_label, fill=(180, 200, 255), font=font_hdr)
    draw.text((col_w + 4 + col_w // 4, 3), b_label, fill=(180, 255, 180), font=font_hdr)

    for i in range(n):
        y_off = label_bar + i * row_h
        # Column A
        fa = af[i].resize((cell_w, cell_h), Image.Resampling.LANCZOS).convert('RGBA')
        grid.paste(fa, (pad, y_off + label_bar + pad))
        draw.text((pad + 2, y_off + pad + 2), f"#{i}", fill=(200, 200, 200), font=font)
        # Divider
        draw.line([(col_w + 1, y_off), (col_w + 2, y_off + row_h)], fill=(80, 80, 80), width=2)
        # Column B
        fb = bf[i].resize((cell_w, cell_h), Image.Resampling.LANCZOS).convert('RGBA')
        grid.paste(fb, (col_w + 4 + pad, y_off + label_bar + pad))
        draw.text((col_w + 4 + pad + 2, y_off + pad + 2), f"#{i}", fill=(200, 200, 200), font=font)

    return grid


def make_diff_heatmap(
    a: Image.Image,
    b: Image.Image,
    w: int = 256,
    h: int = 256,
) -> Image.Image:
    """Return a red-green heatmap of per-pixel RGBA diff between a and b."""
    a2 = a.resize((w, h), Image.Resampling.LANCZOS).convert('RGBA')
    b2 = b.resize((w, h), Image.Resampling.LANCZOS).convert('RGBA')
    aa = np.asarray(a2, dtype=np.int16)
    bb = np.asarray(b2, dtype=np.int16)
    diff = np.mean(np.abs(aa - bb), axis=2).astype(np.float32)  # (H, W) 0-255
    norm = (diff / max(diff.max(), 1.0) * 255).astype(np.uint8)
    # Red = large diff, green = small diff
    r = norm
    g = (255 - norm)
    b_ch = np.zeros_like(norm)
    heatmap = np.stack([r, g, b_ch, np.full_like(norm, 255)], axis=2)
    return Image.fromarray(heatmap, mode='RGBA')


def _png_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('ascii')


# ---------------------------------------------------------------------------
# QA delta
# ---------------------------------------------------------------------------

def qa_delta(meta_a: Dict[str, Any], meta_b: Dict[str, Any]) -> List[Dict[str, Any]]:
    keys = ['frame_count', 'fps', 'frame_width', 'frame_height', 'columns', 'rows']
    rows = []
    for k in keys:
        va = meta_a.get(k, 'N/A')
        vb = meta_b.get(k, 'N/A')
        rows.append({'field': k, 'a': va, 'b': vb, 'match': va == vb})
    return rows


# ---------------------------------------------------------------------------
# Alignment warnings
# ---------------------------------------------------------------------------

def frame_alignment_warnings(
    af: List[Image.Image],
    bf: List[Image.Image],
    diffs: List[float],
) -> List[str]:
    warnings = []
    if len(af) != len(bf):
        warnings.append(
            f"Frame count mismatch: A has {len(af)} frames, B has {len(bf)} frames. "
            "Extra frames were ignored in comparison."
        )
    if diffs:
        worst_idx = int(np.argmax(diffs))
        worst_val = diffs[worst_idx]
        if worst_val > 40:
            warnings.append(
                f"Frame #{worst_idx} has a very high diff ({worst_val:.1f}/255). "
                "Check for missing/duplicate frames."
            )
        mean_diff = float(np.mean(diffs))
        if mean_diff > 20:
            warnings.append(
                f"Overall mean diff is {mean_diff:.1f} — outputs look substantially different."
            )
    return warnings


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def _svg_bar_chart(diffs: List[float], max_w: int = 600) -> str:
    if not diffs:
        return ""
    bar_h = 14
    gap = 3
    pad_l = 40
    pad_r = 20
    svg_h = (bar_h + gap) * len(diffs) + 30
    svg_w = max_w
    max_val = max(max(diffs), 1.0)
    bars = []
    for i, d in enumerate(diffs):
        bw = int((d / max_val) * (max_w - pad_l - pad_r))
        y = 20 + i * (bar_h + gap)
        color = "#e05050" if d > 40 else "#f0a040" if d > 20 else "#50b050"
        bars.append(
            f'<rect x="{pad_l}" y="{y}" width="{bw}" height="{bar_h}" fill="{color}" rx="2"/>'
            f'<text x="{pad_l - 4}" y="{y + bar_h - 2}" text-anchor="end" font-size="10" fill="#aaa">#{i}</text>'
            f'<text x="{pad_l + bw + 4}" y="{y + bar_h - 2}" font-size="10" fill="#ccc">{d:.1f}</text>'
        )
    return (
        f'<svg width="{svg_w}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1a1a1a;border-radius:6px">'
        f'<text x="{pad_l}" y="14" font-size="12" fill="#aaa">Per-frame mean abs RGBA diff</text>'
        + "".join(bars) + "</svg>"
    )


def make_html_report(
    data: Dict[str, Any],
    grid_img: Optional[Image.Image],
    heatmap_img: Optional[Image.Image],
) -> str:
    a = data['a']
    b = data['b']
    diffs = [r['mean_abs_rgba_diff'] for r in data.get('frames', [])]
    delta = data.get('qa_delta', [])
    warnings_list = data.get('warnings', [])

    grid_tag = ""
    if grid_img:
        grid_tag = f'<img src="data:image/png;base64,{_png_b64(grid_img)}" style="max-width:100%;border-radius:6px" alt="Side-by-side grid">'

    heat_tag = ""
    if heatmap_img:
        heat_tag = f'<img src="data:image/png;base64,{_png_b64(heatmap_img)}" style="max-width:300px;border-radius:6px" alt="Diff heatmap">'

    delta_rows = "".join(
        f"<tr><td>{r['field']}</td><td>{r['a']}</td><td>{r['b']}</td>"
        f"<td style='color:{'#6f6' if r['match'] else '#f66'}'>{'✔' if r['match'] else '✘'}</td></tr>"
        for r in delta
    )

    warn_items = "".join(f"<li style='color:#f0a040'>{w}</li>" for w in warnings_list)

    bar_chart = _svg_bar_chart(diffs)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>SpriteForge Compare Report</title>
<style>
  body{{font-family:system-ui,sans-serif;background:#111;color:#ddd;margin:0;padding:24px}}
  h1{{color:#a0c4ff;margin-bottom:4px}}
  h2{{color:#7ab;font-size:1rem;margin:24px 0 8px}}
  .path{{font-size:.8rem;color:#777;font-family:monospace;margin-bottom:16px}}
  .stats{{display:flex;gap:24px;flex-wrap:wrap;margin:16px 0}}
  .stat-box{{background:#1e1e2e;border-radius:8px;padding:12px 20px;min-width:120px}}
  .stat-box .val{{font-size:1.6rem;font-weight:700;color:#a0c4ff}}
  .stat-box .lbl{{font-size:.75rem;color:#888;text-transform:uppercase}}
  table{{border-collapse:collapse;width:100%;max-width:500px}}
  td,th{{padding:6px 10px;border:1px solid #333;font-size:.85rem}}
  th{{background:#1e1e2e;color:#aaa}}
  .warn{{background:#1e1200;border:1px solid #664400;border-radius:6px;padding:12px;margin:16px 0}}
  ul{{margin:4px 0;padding-left:20px}}
  .images{{display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start;margin:16px 0}}
  .img-block label{{display:block;color:#888;font-size:.8rem;margin-bottom:6px}}
</style>
</head>
<body>
<h1>SpriteForge Compare Report</h1>
<div class="path">A: {a}<br>B: {b}</div>
<div class="stats">
  <div class="stat-box"><div class="val">{data.get('compared_frames','?')}</div><div class="lbl">Frames compared</div></div>
  <div class="stat-box"><div class="val">{data.get('mean_diff',0):.2f}</div><div class="lbl">Mean diff</div></div>
  <div class="stat-box"><div class="val">{data.get('max_diff',0):.2f}</div><div class="lbl">Max diff</div></div>
  <div class="stat-box"><div class="val">{data.get('a_frame_count','?')}</div><div class="lbl">A frames</div></div>
  <div class="stat-box"><div class="val">{data.get('b_frame_count','?')}</div><div class="lbl">B frames</div></div>
</div>

{'<div class="warn"><b>⚠ Alignment warnings</b><ul>' + warn_items + '</ul></div>' if warn_items else ''}

<h2>Side-by-side grid</h2>
<div class="images">
  <div class="img-block">{grid_tag}</div>
  <div class="img-block">
    <label>Diff heatmap (red = large diff)</label>
    {heat_tag}
  </div>
</div>

<h2>Per-frame diff chart</h2>
{bar_chart}

<h2>QA delta (sheet.json)</h2>
<table>
<tr><th>Field</th><th>A</th><th>B</th><th>Match</th></tr>
{delta_rows}
</table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Public entry point (also callable in-process)
# ---------------------------------------------------------------------------

def compare_dirs(
    a_dir: Path,
    b_dir: Path,
    out_dir: Optional[Path] = None,
    max_frames: int = 16,
) -> Dict[str, Any]:
    """Compare two sprite output directories and write a visual report.

    Returns the data dict (same as compare_report.json).
    """
    af, bf = load_frames(a_dir), load_frames(b_dir)
    n = min(len(af), len(bf))
    frame_rows = [{'index': i, 'mean_abs_rgba_diff': frame_diff(af[i], bf[i])} for i in range(n)]

    diffs = [r['mean_abs_rgba_diff'] for r in frame_rows]

    try:
        meta_a = load_meta(a_dir)
    except Exception:
        meta_a = {}
    try:
        meta_b = load_meta(b_dir)
    except Exception:
        meta_b = {}

    qa_d = qa_delta(meta_a, meta_b)
    align_warnings = frame_alignment_warnings(af, bf, diffs)

    data = {
        'a': str(a_dir),
        'b': str(b_dir),
        'a_frame_count': len(af),
        'b_frame_count': len(bf),
        'compared_frames': n,
        'mean_diff': float(np.mean(diffs)) if diffs else 0.0,
        'max_diff': float(np.max(diffs)) if diffs else 0.0,
        'frames': frame_rows,
        'qa_delta': qa_d,
        'warnings': align_warnings,
    }

    if out_dir is None:
        out_dir = Path('output') / 'sprite_compare'
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON report
    (out_dir / 'compare_report.json').write_text(json.dumps(data, indent=2), encoding='utf-8')

    # Visual assets
    try:
        grid_img = make_sidebyside_grid(af, bf, a_dir.name, b_dir.name, max_frames=max_frames)
        grid_img.save(out_dir / 'sidebyside_grid.png')
    except Exception:
        grid_img = None

    try:
        if af and bf:
            # Build aggregate heatmap across all compared frames
            base = af[0].convert('RGBA')
            w, h = base.size
            acc = np.zeros((min(h, 256), min(w, 256)), dtype=np.float32)
            for i in range(n):
                hm = make_diff_heatmap(af[i], bf[i], min(w, 256), min(h, 256))
                acc += np.asarray(hm)[:, :, 0].astype(np.float32)
            acc /= max(n, 1)
            norm = (acc / max(acc.max(), 1.0) * 255).astype(np.uint8)
            g_ch = (255 - norm)
            b_ch = np.zeros_like(norm)
            rgba = np.stack([norm, g_ch, b_ch, np.full_like(norm, 255)], axis=2)
            heatmap_img = Image.fromarray(rgba, mode='RGBA')
            heatmap_img.save(out_dir / 'diff_heatmap.png')
        else:
            heatmap_img = None
    except Exception:
        heatmap_img = None

    # Rich HTML report
    html = make_html_report(data, grid_img, heatmap_img)
    (out_dir / 'compare_report.html').write_text(html, encoding='utf-8')

    print(
        f"Compared {n} frames. Mean diff={data['mean_diff']:.3f}. "
        f"Report: {out_dir / 'compare_report.html'}"
    )
    return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_compare(args: argparse.Namespace) -> None:
    out = Path(args.output) if args.output else Path('output') / 'sprite_compare'
    compare_dirs(Path(args.a), Path(args.b), out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Compare two SpriteForge sprite outputs')
    s = p.add_subparsers(dest='command', required=True).add_parser('compare')
    s.add_argument('--a', required=True)
    s.add_argument('--b', required=True)
    s.add_argument('--output', default=None)
    s.set_defaults(func=cmd_compare)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = build_parser()
    a = p.parse_args(argv)
    a.func(a)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
