#!/usr/bin/env python3
"""Chroma-key, alpha bbox, rembg, outline, and solidify operations for sprite frames."""
from __future__ import annotations

import os
from typing import Iterable, List, Optional, Tuple, Union

import numpy as np
from PIL import Image, ImageChops, ImageFilter

try:
    import cv2
except Exception:
    cv2 = None

from services.sprite_service import SpriteService

BIREFNET_MATTING_MODEL_ID = os.environ.get("SPRITEFORGE_BIREFNET_MODEL", "ZhengPeng7/BiRefNet-matting")

__all__ = [
    "BIREFNET_MATTING_MODEL_ID",
    "guess_key_color_from_corners",
    "apply_chroma_key",
    "try_rembg",
    "try_birefnet",
    "apply_pixeloe_pixelization",
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


def try_birefnet(img: Image.Image) -> Image.Image:
    try:
        import torch
        from torchvision import transforms
        from transformers import AutoModelForImageSegmentation
    except Exception as exc:
        raise RuntimeError(
            "The BiRefNet option requires the optional transformers, torch, and torchvision packages. "
            "Install them with: pip install transformers torch torchvision"
        ) from exc

    global _BIREFNET_MODEL, _BIREFNET_TRANSFORM
    if '_BIREFNET_MODEL' not in globals() or _BIREFNET_MODEL is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _BIREFNET_MODEL = AutoModelForImageSegmentation.from_pretrained(
            BIREFNET_MATTING_MODEL_ID, trust_remote_code=True
        ).to(device)
        _BIREFNET_MODEL.eval()
        _BIREFNET_TRANSFORM = transforms.Compose([
            transforms.Resize((1024, 1024)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

    device = next(_BIREFNET_MODEL.parameters()).device
    input_rgb = img.convert("RGB")
    w, h = input_rgb.size
    input_tensor = _BIREFNET_TRANSFORM(input_rgb).unsqueeze(0).to(device)

    with torch.no_grad():
        preds = _BIREFNET_MODEL(input_tensor)[-1].sigmoid().cpu()

    pred = preds[0].squeeze()
    pred_pil = transforms.ToPILImage()(pred).resize((w, h), Image.Resampling.BILINEAR)

    # Composite onto transparent background
    img = img.convert("RGBA")
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask=pred_pil)
    return out


def apply_pixeloe_pixelization(img: Image.Image, pixel_size: int = 4, thickness: int = 1) -> Image.Image:
    """Applies detail-oriented pixelization using contrast-aware downscaling and outline expansion."""
    try:
        from pixeloe import pixelize
        np_arr = np.array(img.convert("RGBA"))
        out_arr = pixelize(np_arr, pixel_size=pixel_size, thickness=thickness)
        return Image.fromarray(out_arr, mode="RGBA")
    except Exception:
        # High quality fallback implementation
        img = img.convert("RGBA")
        w, h = img.size
        if w <= pixel_size or h <= pixel_size:
            return img

        # Dilation of alpha mask to keep outlines readable
        alpha = img.getchannel("A")
        if thickness > 0:
            alpha = alpha.filter(ImageFilter.MaxFilter(3 if thickness == 1 else 5))

        # Re-assemble expanded image
        expanded = Image.new("RGBA", img.size, (0, 0, 0, 0))
        expanded.paste(img, (0, 0), mask=alpha)

        # Contrast-aware block pixel sampling
        dw = w // pixel_size
        dh = h // pixel_size
        if dw <= 0 or dh <= 0:
            return img

        arr = np.asarray(expanded)
        downscaled = np.zeros((dh, dw, 4), dtype=np.uint8)

        for y in range(dh):
            for x in range(dw):
                block = arr[y*pixel_size : (y+1)*pixel_size, x*pixel_size : (x+1)*pixel_size]
                if np.max(block[:, :, 3]) < 8:
                    downscaled[y, x] = [0, 0, 0, 0]
                    continue
                alphas = block[:, :, 3]
                max_a = int(np.max(alphas))
                mask = alphas >= max(8, max_a - 15)
                rgb = block[:, :, :3][mask]
                if len(rgb) > 0:
                    mean_rgb = rgb.mean(axis=0).astype(np.uint8)
                else:
                    mean_rgb = np.zeros(3, dtype=np.uint8)
                downscaled[y, x] = [mean_rgb[0], mean_rgb[1], mean_rgb[2], max_a]

        down_img = Image.fromarray(downscaled, mode="RGBA")
        return down_img.resize((w, h), Image.Resampling.NEAREST)



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
