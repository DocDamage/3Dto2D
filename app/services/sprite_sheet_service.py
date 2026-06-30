#!/usr/bin/env python3
"""Sheet packing, metadata writing, preview GIF/contact sheet, Godot/report output."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw

from services.sprite_video_loader import FrameItem, ensure_dir
from services.sprite_frame_norm import next_power_of_two, paste_fit_anchor


def pack_sheet(
    frames: Sequence[FrameItem],
    columns: Optional[int],
    spacing: int,
    margin: int,
    power_of_two: bool,
) -> Tuple[Image.Image, int, int, List[Dict[str, int]]]:
    if not frames:
        raise RuntimeError("No frames to pack.")
    cell_w, cell_h = frames[0].image.size
    n = len(frames)
    if columns is None:
        columns = int(math.ceil(math.sqrt(n)))
    columns = max(1, columns)
    rows = int(math.ceil(n / columns))
    sheet_w = margin * 2 + columns * cell_w + max(0, columns - 1) * spacing
    sheet_h = margin * 2 + rows * cell_h + max(0, rows - 1) * spacing
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
    rects: List[Dict[str, int]] = []
    for i, item in enumerate(frames):
        x = margin + (i % columns) * (cell_w + spacing)
        y = margin + (i // columns) * (cell_h + spacing)
        sheet.alpha_composite(item.image.convert("RGBA"), (x, y))
        rects.append({"x": x, "y": y, "w": cell_w, "h": cell_h})
    if power_of_two:
        new_w = next_power_of_two(sheet.width)
        new_h = next_power_of_two(sheet.height)
        if (new_w, new_h) != sheet.size:
            padded = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
            padded.alpha_composite(sheet, (0, 0))
            sheet = padded
    return sheet, columns, rows, rects


def write_metadata(
    path: Path,
    image_name: str,
    frames: Sequence[FrameItem],
    rects: Sequence[Dict[str, int]],
    cell_size: Tuple[int, int],
    columns: int,
    rows: int,
    fps: float,
    animation_name: str,
    spacing: int,
    margin: int,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    cell_w, cell_h = cell_size
    duration_ms = int(round(1000.0 / fps)) if fps > 0 else 0
    frame_data = []
    for i, (item, rect) in enumerate(zip(frames, rects)):
        frame_data.append({
            "index": i,
            "name": f"{animation_name}_{i:04d}",
            "source_name": item.name,
            "source_index": item.source_index,
            "x": rect["x"], "y": rect["y"],
            "w": rect["w"], "h": rect["h"],
            "duration_ms": duration_ms,
        })
    data: Dict[str, Any] = {
        "image": image_name,
        "animation": animation_name,
        "frame_width": cell_w,
        "frame_height": cell_h,
        "frame_count": len(frames),
        "fps": fps,
        "columns": columns,
        "rows": rows,
        "spacing": spacing,
        "margin": margin,
        "frames": frame_data,
    }
    if extra:
        data["extra"] = extra
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_aseprite_json(
    path: Path,
    image_name: str,
    frames: Sequence[FrameItem],
    rects: Sequence[Dict[str, int]],
    cell_size: Tuple[int, int],
    fps: float,
    animation_name: str,
) -> None:
    cell_w, cell_h = cell_size
    duration_ms = int(round(1000.0 / fps)) if fps > 0 else 0
    ase_frames: Dict[str, Any] = {}
    for i, rect in enumerate(rects):
        name = f"{animation_name}_{i:04d}.png"
        ase_frames[name] = {
            "frame": {"x": rect["x"], "y": rect["y"], "w": rect["w"], "h": rect["h"]},
            "rotated": False, "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": cell_w, "h": cell_h},
            "sourceSize": {"w": cell_w, "h": cell_h},
            "duration": duration_ms,
        }
    data = {
        "frames": ase_frames,
        "meta": {
            "app": "SpriteForge", "version": "2.0",
            "image": image_name, "format": "RGBA8888",
            "size": {"w": 0, "h": 0}, "scale": "1",
            "frameTags": [{"name": animation_name, "from": 0, "to": max(0, len(frames) - 1), "direction": "forward"}],
        },
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def make_preview_gif(frames: Sequence[FrameItem], path: Path, fps: float) -> None:
    if not frames:
        return
    duration = int(round(1000.0 / fps)) if fps > 0 else 83
    imgs = [f.image.convert("RGBA") for f in frames]
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=duration, loop=0, disposal=2)


def make_contact_sheet(frames: Sequence[FrameItem], path: Path, columns: Optional[int] = None, label: bool = True) -> None:
    if not frames:
        return
    thumb_w, thumb_h = 96, 96
    label_h = 18 if label else 0
    n = len(frames)
    columns = columns or int(math.ceil(math.sqrt(n)))
    rows = int(math.ceil(n / columns))
    sheet = Image.new("RGBA", (columns * thumb_w, rows * (thumb_h + label_h)), (32, 32, 32, 255))
    draw = ImageDraw.Draw(sheet)
    for i, item in enumerate(frames):
        img = paste_fit_anchor(item.image, (thumb_w, thumb_h), "bottom-center", 2)
        x = (i % columns) * thumb_w
        y = (i // columns) * (thumb_h + label_h)
        sheet.alpha_composite(img, (x, y))
        if label:
            draw.text((x + 3, y + thumb_h + 2), str(i), fill=(230, 230, 230, 255))
    sheet.convert("RGB").save(path)


def write_godot_notes(path: Path, frame_count: int, columns: int, rows: int, fps: float, cell_size: Tuple[int, int]) -> None:
    path.write_text(
        f"""SpriteForge Godot notes\n\n"""
        f"""Sprite2D setup:\n- Texture: sheet.png\n- hframes: {columns}\n- vframes: {rows}\n"""
        f"""- Frame range: 0 to {frame_count - 1}\n- FPS: {fps:g}\n- Cell size: {cell_size[0]}x{cell_size[1]}\n\n"""
        f"""For AnimatedSprite2D:\n- Create SpriteFrames resource.\n- Add animation.\n"""
        f"""- Add frames from sheet.png using the same {cell_size[0]}x{cell_size[1]} grid.\n"""
        f"""- Set animation speed to {fps:g} FPS.\n""",
        encoding="utf-8",
    )


def export_apng(frames: Sequence[FrameItem], path: Path, fps: float) -> None:
    """Export frames as animated PNG (lossless)."""
    if not frames:
        return
    # APNG is natively supported by Pillow since 9.1
    duration = int(round(1000.0 / fps)) if fps > 0 else 83
    imgs = [f.image.convert("RGBA") for f in frames]
    # Pillow saves APNG when saving PNG with save_all and append_images
    imgs[0].save(
        path,
        format="PNG",
        save_all=True,
        append_images=imgs[1:],
        duration=duration,
        loop=0,
        disposal=2,
    )


def export_webp_anim(frames: Sequence[FrameItem], path: Path, fps: float, quality: int = 85) -> None:
    """Export frames as animated WebP."""
    if not frames:
        return
    duration = int(round(1000.0 / fps)) if fps > 0 else 83
    imgs = [f.image.convert("RGBA") for f in frames]
    imgs[0].save(
        path,
        format="WEBP",
        save_all=True,
        append_images=imgs[1:],
        duration=duration,
        loop=0,
        lossless=False,
        quality=quality,
        method=4,
    )


def write_report(path: Path, sheet_name: str, output_dir: Path, frame_count: int, fps: float,
                 cell_size: Tuple[int, int], columns: int, rows: int, extra: Dict[str, Any]) -> None:
    preview_exists = (output_dir / "preview.gif").exists()
    contact_exists = (output_dir / "contact_sheet.jpg").exists()
    preview_html = '<p><img src="preview.gif" /></p>' if preview_exists else ""
    contact_html = '<p><img src="contact_sheet.jpg" /></p>' if contact_exists else ""
    extra_json = json.dumps(extra, indent=2)
    html = f"""<!doctype html>
<html><head><meta charset="utf-8" /><title>SpriteForge Report</title>
<style>body{{font-family:Arial,sans-serif;margin:24px;line-height:1.4;}}
code,pre{{background:#f3f3f3;padding:2px 4px;}}pre{{padding:12px;overflow:auto;}}
img{{max-width:100%;image-rendering:auto;}}table{{border-collapse:collapse;}}td,th{{border:1px solid #ccc;padding:6px 8px;}}</style>
</head><body><h1>SpriteForge Report</h1>
<table><tr><th>Frames</th><td>{frame_count}</td></tr>
<tr><th>FPS</th><td>{fps:g}</td></tr>
<tr><th>Cell</th><td>{cell_size[0]}x{cell_size[1]}</td></tr>
<tr><th>Grid</th><td>{columns} columns x {rows} rows</td></tr></table>
<h2>Preview</h2>{preview_html}
<h2>Contact sheet</h2>{contact_html}
<h2>Spritesheet</h2><p><img src="{sheet_name}" /></p>
<h2>Extra metadata</h2><pre>{extra_json}</pre></body></html>"""
    path.write_text(html, encoding="utf-8")