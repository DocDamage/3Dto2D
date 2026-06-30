#!/usr/bin/env python3
"""Chroma-key, alpha bbox, rembg, outline, and solidify operations for sprite frames."""
from __future__ import annotations

from typing import Iterable, List, Optional, Tuple, Union

import numpy as np
from PIL import Image, ImageChops, ImageFilter

try:
    import cv2
except Exception:
    cv2 = None

from services.sprite_service import SpriteService

__all__ = [
    "guess_key_color_from_corners",
    "apply_chroma_key",
    "try_rembg",
    "alpha_bbox",
    "expand_bbox",
    "union_bboxes",
    "add_outline",
    "solidify_transparent_rgb",
]


def guess_key_color_from_corners(img: Image.Image, sample: int = 12) -> Tuple[int, int, int]:
    return SpriteService.guess_key_color_from_corners(img)


def apply_chroma_key(
    img: Image.Image,
    key_color: Union[Tuple[int, int, int], str],
    tolerance: float,
    feather: float,
) -> Image.Image:
    return SpriteService.apply_chroma_key(img, key_color, tolerance, feather)


def try_rembg(img: Image.Image) -> Image.Image:
    try:
        from rembg import remove
    except Exception as exc:
        raise RuntimeError(
            "The --rembg option requires the optional rembg package. "
            "Install it with: pip install rembg onnxruntime"
        ) from exc
    out = remove(img.convert("RGBA"))
    if isinstance(out, Image.Image):
        return out.convert("RGBA")
    return Image.open(out).convert("RGBA")


def alpha_bbox(img: Image.Image, threshold: int = 8) -> Optional[Tuple[int, int, int, int]]:
    return SpriteService.alpha_bbox(img, threshold)


def expand_bbox(
    bbox: Tuple[int, int, int, int],
    pad: int,
    max_w: int,
    max_h: int,
) -> Tuple[int, int, int, int]:
    l, t, r, b = bbox
    return max(0, l - pad), max(0, t - pad), min(max_w, r + pad), min(max_h, b + pad)


def union_bboxes(bboxes: Iterable[Tuple[int, int, int, int]]) -> Optional[Tuple[int, int, int, int]]:
    bboxes = list(bboxes)
    if not bboxes:
        return None
    return (
        min(b[0] for b in bboxes),
        min(b[1] for b in bboxes),
        max(b[2] for b in bboxes),
        max(b[3] for b in bboxes),
    )


def add_outline(img: Image.Image, width: int, color: Tuple[int, int, int, int]) -> Image.Image:
    if width <= 0:
        return img.convert("RGBA")
    base = img.convert("RGBA")
    alpha = base.getchannel("A")
    dilated = alpha
    for _ in range(width):
        dilated = dilated.filter(ImageFilter.MaxFilter(3))
    outline_alpha = ImageChops.subtract(dilated, alpha)
    outline = Image.new("RGBA", base.size, color)
    outline.putalpha(outline_alpha)
    outline.alpha_composite(base)
    return outline


def solidify_transparent_rgb(img: Image.Image, iterations: int, alpha_threshold: int = 8) -> Image.Image:
    if iterations <= 0:
        return img.convert("RGBA")
    if cv2 is None:
        return SpriteService.solidify_transparent_rgb(img, radius=max(1, iterations // 2))
    arr = np.asarray(img.convert("RGBA")).copy()
    rgb = arr[:, :, :3].astype(np.float32)
    alpha = arr[:, :, 3]
    filled = alpha > alpha_threshold
    original_alpha = alpha.copy()
    kernel = np.ones((3, 3), np.float32)
    for _ in range(iterations):
        dilated = cv2.dilate(filled.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=1).astype(bool)
        new = dilated & ~filled
        if not new.any():
            break
        counts = cv2.filter2D(filled.astype(np.float32), -1, kernel, borderType=cv2.BORDER_REPLICATE)
        counts = np.maximum(counts, 1.0)
        for c in range(3):
            sums = cv2.filter2D(rgb[:, :, c] * filled.astype(np.float32), -1, kernel, borderType=cv2.BORDER_REPLICATE)
            rgb[:, :, c][new] = (sums / counts)[new]
        filled = dilated
    arr[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    arr[:, :, 3] = original_alpha
    return Image.fromarray(arr, mode="RGBA")