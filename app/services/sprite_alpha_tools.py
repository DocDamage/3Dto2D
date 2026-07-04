#!/usr/bin/env python3
"""Alpha extraction and refinement helpers for sprite frames."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image, ImageFilter


def extract_dual_background_alpha(
    black_bg: Image.Image,
    white_bg: Image.Image,
    alpha_floor: int = 0,
) -> Image.Image:
    """Recover RGBA from matching renders on black and white backgrounds.

    This implements the standard dual-background alpha equation:
    alpha = 1 - (white - black). Averaging RGB channels makes the result stable
    for neutral render backgrounds while keeping the implementation dependency
    free and suitable for Blender black/white passes.
    """
    black = np.asarray(black_bg.convert("RGB")).astype(np.float32) / 255.0
    white = np.asarray(white_bg.convert("RGB")).astype(np.float32) / 255.0
    if black.shape != white.shape:
        raise ValueError("Dual-background alpha inputs must have the same dimensions")

    diff = np.clip(white - black, 0.0, 1.0)
    alpha = np.clip(1.0 - diff.mean(axis=2), 0.0, 1.0)
    if alpha_floor > 0:
        alpha = np.where(alpha * 255.0 >= alpha_floor, alpha, 0.0)

    rgb = np.zeros_like(black)
    visible = alpha > 1e-6
    rgb[visible] = black[visible] / alpha[visible, None]
    rgb = np.clip(rgb, 0.0, 1.0)

    out = np.dstack([rgb, alpha])
    return Image.fromarray((out * 255.0 + 0.5).astype(np.uint8), mode="RGBA")


def refine_alpha_edges(
    img: Image.Image,
    radius: int = 1,
    strength: float = 0.65,
) -> Image.Image:
    """Refine matte edges with a native, deterministic edge-aware alpha pass."""
    base = img.convert("RGBA")
    radius = max(0, int(radius))
    strength = max(0.0, min(1.0, float(strength)))
    if radius <= 0 or strength <= 0:
        return base

    alpha = base.getchannel("A")
    alpha_arr = np.asarray(alpha).astype(np.float32) / 255.0
    foreground = alpha_arr >= 0.98
    background = alpha_arr <= 0.02

    edge = np.asarray(alpha.filter(ImageFilter.FIND_EDGES)) > 0
    if radius > 1:
        edge_img = Image.fromarray(edge.astype(np.uint8) * 255, mode="L").filter(ImageFilter.MaxFilter(radius * 2 + 1))
        edge = np.asarray(edge_img) > 0

    soft_band = (alpha_arr > 0.02) & (alpha_arr < 0.98)
    visible_band = np.asarray(alpha.filter(ImageFilter.MaxFilter(radius * 2 + 1))) > 0
    edit_mask = edge | soft_band | (visible_band & ~foreground)
    gaussian_smooth = np.asarray(alpha.filter(ImageFilter.GaussianBlur(radius))).astype(np.float32) / 255.0

    try:
        import cv2  # type: ignore

        bilateral = cv2.bilateralFilter(
            alpha_arr.astype(np.float32),
            d=max(3, radius * 2 + 1),
            sigmaColor=0.14,
            sigmaSpace=max(1.0, float(radius * 2)),
        )
        smooth = bilateral * 0.65 + gaussian_smooth * 0.35
    except Exception as exc:
        logging.getLogger(__name__).debug("OpenCV unavailable for bilateral alpha refinement; Gaussian fallback will be used: %s", exc)
        smooth = gaussian_smooth

    refined = alpha_arr.copy()
    refined[edit_mask] = alpha_arr[edit_mask] * (1.0 - strength) + smooth[edit_mask] * strength
    refined[foreground & ~edge] = np.maximum(refined[foreground & ~edge], alpha_arr[foreground & ~edge])
    far_background = background & ~edge & ~visible_band
    refined[far_background] = np.minimum(refined[far_background], alpha_arr[far_background])

    out = base.copy()
    out.putalpha(Image.fromarray((np.clip(refined, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8), mode="L"))
    return out


def rgba_to_rgb_alpha(img: Image.Image) -> Tuple[np.ndarray, np.ndarray]:
    arr = np.asarray(img.convert("RGBA"))
    return arr[:, :, :3], arr[:, :, 3]


def save_dual_background_alpha(black_path: Path, white_path: Path, output_path: Path) -> Image.Image:
    out = extract_dual_background_alpha(Image.open(black_path), Image.open(white_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(output_path)
    return out
