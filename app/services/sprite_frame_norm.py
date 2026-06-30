#!/usr/bin/env python3
"""Frame normalization, anchor positioning, sequence ops, frame diff."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageChops

from services.sprite_service import SpriteService
from services.sprite_video_loader import FrameItem, ensure_dir
from services.sprite_chroma_alpha import alpha_bbox, expand_bbox, union_bboxes


def next_power_of_two(n: int) -> int:
    if n <= 1:
        return 1
    return 1 << (n - 1).bit_length()


def anchor_position(
    canvas_size: Tuple[int, int],
    image_size: Tuple[int, int],
    anchor: str,
    ground_margin: int,
) -> Tuple[int, int]:
    cell_w, cell_h = canvas_size
    w, h = image_size
    anchor = anchor.lower()
    if anchor in {"center", "middle"}:
        return (cell_w - w) // 2, (cell_h - h) // 2
    if anchor in {"bottom-center", "feet", "ground"}:
        return (cell_w - w) // 2, cell_h - h - ground_margin
    if anchor == "top-center":
        return (cell_w - w) // 2, ground_margin
    if anchor == "bottom-left":
        return ground_margin, cell_h - h - ground_margin
    if anchor == "bottom-right":
        return cell_w - w - ground_margin, cell_h - h - ground_margin
    if anchor == "left-center":
        return ground_margin, (cell_h - h) // 2
    if anchor == "right-center":
        return cell_w - w - ground_margin, (cell_h - h) // 2
    raise RuntimeError(f"Unknown anchor: {anchor}")


def paste_fit_anchor(src: Image.Image, cell_size: Tuple[int, int], anchor: str, ground_margin: int) -> Image.Image:
    src = src.convert("RGBA")
    cell_w, cell_h = cell_size
    canvas = Image.new("RGBA", cell_size, (0, 0, 0, 0))
    w, h = src.size
    if w <= 0 or h <= 0:
        return canvas
    scale = min(cell_w / w, cell_h / h)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = src.resize((new_w, new_h), Image.Resampling.LANCZOS)
    x, y = anchor_position(cell_size, (new_w, new_h), anchor, ground_margin)
    x = max(0, min(cell_w - new_w, x))
    y = max(0, min(cell_h - new_h, y))
    canvas.alpha_composite(resized, (x, y))
    return canvas


def normalize_frames(
    frames: Sequence[FrameItem],
    cell_size: Optional[Tuple[int, int]],
    crop_mode: str,
    pad: int,
    alpha_threshold: int,
    anchor: str,
    ground_margin: int,
) -> Tuple[List[FrameItem], Tuple[int, int], Dict[str, Any]]:
    if not frames:
        raise RuntimeError("No frames to normalize.")
    bboxes = []
    per_frame_bboxes: List[Optional[Tuple[int, int, int, int]]] = []
    for item in frames:
        bbox = alpha_bbox(item.image, alpha_threshold)
        per_frame_bboxes.append(bbox)
        if bbox is not None:
            bboxes.append(bbox)
    global_bbox = None
    if crop_mode == "none" or not bboxes:
        cropped = [FrameItem(item.image.convert("RGBA"), item.name, item.source_index) for item in frames]
    elif crop_mode == "global":
        u = union_bboxes(bboxes)
        assert u is not None
        max_w = frames[0].image.width
        max_h = frames[0].image.height
        global_bbox = expand_bbox(u, pad, max_w, max_h)
        cropped = [FrameItem(item.image.crop(global_bbox), item.name, item.source_index) for item in frames]
    elif crop_mode == "per-frame":
        cropped = []
        for item, bbox in zip(frames, per_frame_bboxes):
            if bbox is None:
                cropped.append(FrameItem(item.image.convert("RGBA"), item.name, item.source_index))
            else:
                bbox = expand_bbox(bbox, pad, item.image.width, item.image.height)
                cropped.append(FrameItem(item.image.crop(bbox), item.name, item.source_index))
    else:
        raise RuntimeError(f"Unknown crop mode: {crop_mode}")
    if cell_size is None:
        max_w = max(img.image.width for img in cropped)
        max_h = max(img.image.height for img in cropped)
        cell_size = (max_w, max_h)
    normalized = [
        FrameItem(paste_fit_anchor(item.image, cell_size, anchor, ground_margin), item.name, item.source_index)
        for item in cropped
    ]
    info = {
        "crop_mode": crop_mode,
        "global_bbox": list(global_bbox) if global_bbox else None,
        "anchor": anchor,
        "ground_margin": ground_margin,
    }
    return normalized, cell_size, info


def frame_difference(a: Image.Image, b: Image.Image) -> float:
    a_small = a.convert("RGBA").resize((64, 64), Image.Resampling.BILINEAR)
    b_small = b.convert("RGBA").resize((64, 64), Image.Resampling.BILINEAR)
    aa = np.asarray(a_small).astype(np.float32)
    bb = np.asarray(b_small).astype(np.float32)
    return float(np.mean(np.abs(aa - bb)))


def apply_frame_sequence_ops(
    frames: List[FrameItem],
    drop_last: bool,
    drop_loop_duplicate: bool,
    loop_mode: str,
    reverse: bool,
    flip_x: bool,
    flip_y: bool,
    palette: Optional[List[Tuple[int, int, int]]] = None,
) -> List[FrameItem]:
    out = list(frames)
    if palette:
        for item in out:
            item.image = SpriteService.apply_palette_lock(item.image, palette)
    if drop_last and len(out) > 1:
        out = out[:-1]
    if drop_loop_duplicate and len(out) > 2:
        if frame_difference(out[0].image, out[-1].image) < 2.5:
            out = out[:-1]
    if loop_mode == "pingpong" and len(out) > 2:
        out = out + [FrameItem(f.image.copy(), f"{f.name}_rev", f.source_index) for f in reversed(out[1:-1])]
    if reverse:
        out = list(reversed(out))
    if flip_x or flip_y:
        flipped = []
        for item in out:
            img = item.image
            if flip_x:
                img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if flip_y:
                img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            flipped.append(FrameItem(img, item.name, item.source_index))
        out = flipped
    return out