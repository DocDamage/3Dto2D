#!/usr/bin/env python3
"""Chroma-key, alpha bbox, rembg, outline, and solidify operations for sprite frames."""
from __future__ import annotations

import os
import logging
from collections import Counter, deque
from typing import Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image, ImageChops, ImageFilter

try:
    import cv2
except Exception as exc:
    cv2 = None
    logging.getLogger(__name__).debug("OpenCV is not available; depth matting morphology will use fallback behavior: %s", exc)

from services.sprite_service import SpriteService

logger = logging.getLogger(__name__)

BIREFNET_MATTING_MODEL_ID = os.environ.get("SPRITEFORGE_BIREFNET_MODEL", "ZhengPeng7/BiRefNet-matting")
DEPTH_ANYTHING_MODEL_ID = os.environ.get("SPRITEFORGE_DEPTH_ANYTHING_MODEL", "LiheYoung/depth-anything-small-hf")

__all__ = [
    "BIREFNET_MATTING_MODEL_ID",
    "DEPTH_ANYTHING_MODEL_ID",
    "guess_key_color_from_corners",
    "apply_chroma_key",
    "apply_pixel_art_background_removal",
    "try_rembg",
    "try_birefnet",
    "try_depth_anything",
    "apply_pixeloe_pixelization",
    "palette_to_native_array",
    "fit_native_pixel_palette",
    "apply_native_pixel_cleanup",
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


def _border_rgb_counts(img: Image.Image, alpha_threshold: int) -> Counter:
    arr = np.asarray(img.convert("RGBA"))
    h, w = arr.shape[:2]
    pixels = []
    if h == 0 or w == 0:
        return Counter()
    pixels.extend(arr[0, :, :].tolist())
    pixels.extend(arr[h - 1, :, :].tolist())
    if h > 2:
        pixels.extend(arr[1 : h - 1, 0, :].tolist())
        pixels.extend(arr[1 : h - 1, w - 1, :].tolist())
    return Counter(tuple(px[:3]) for px in pixels if px[3] > alpha_threshold)


def apply_pixel_art_background_removal(
    img: Image.Image,
    tolerance: float = 18.0,
    max_palette_colors: int = 6,
    alpha_threshold: int = 8,
) -> Image.Image:
    """Remove border-connected pixel-art backgrounds with hard, non-feathered alpha.

    This is tuned for generated pixel-art sheets where the background is a flat
    or lightly dithered color. It samples the image border, flood-fills only
    border-connected pixels near those background colors, and leaves interior
    same-color sprite details intact.
    """
    base = img.convert("RGBA")
    arr = np.asarray(base).copy()
    h, w = arr.shape[:2]
    if h == 0 or w == 0:
        return base

    counts = _border_rgb_counts(base, alpha_threshold)
    if not counts:
        return base

    palette = np.asarray([rgb for rgb, _count in counts.most_common(max(1, int(max_palette_colors)))], dtype=np.float32)
    rgb = arr[:, :, :3].astype(np.float32)
    alpha = arr[:, :, 3]
    dist = np.sum((rgb[:, :, None, :] - palette[None, None, :, :]) ** 2, axis=3)
    candidate = (np.min(dist, axis=2) <= float(tolerance) ** 2) & (alpha > alpha_threshold)

    remove = np.zeros((h, w), dtype=bool)
    q = deque()
    for x in range(w):
        if candidate[0, x]:
            q.append((x, 0))
        if h > 1 and candidate[h - 1, x]:
            q.append((x, h - 1))
    for y in range(1, max(1, h - 1)):
        if candidate[y, 0]:
            q.append((0, y))
        if w > 1 and candidate[y, w - 1]:
            q.append((w - 1, y))

    while q:
        x, y = q.popleft()
        if remove[y, x] or not candidate[y, x]:
            continue
        remove[y, x] = True
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not remove[ny, nx] and candidate[ny, nx]:
                q.append((nx, ny))

    arr[remove, 3] = 0
    keep = ~remove & (alpha > alpha_threshold)
    arr[keep, 3] = 255
    arr[~keep & ~remove, 3] = 0
    return Image.fromarray(arr, mode="RGBA")


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


def _border_depth_values(depth: np.ndarray) -> np.ndarray:
    if depth.size == 0:
        return np.asarray([], dtype=np.float32)
    h, w = depth.shape[:2]
    border = [depth[0, :], depth[h - 1, :], depth[:, 0], depth[:, w - 1]]
    return np.concatenate([b.reshape(-1) for b in border]).astype(np.float32)


def try_depth_anything(img: Image.Image) -> Image.Image:
    """Use optional Depth Anything depth estimation to build an alpha matte."""
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    except Exception as exc:
        raise RuntimeError(
            "The depth-anything matting option requires optional transformers and torch packages. "
            "Install them with: pip install transformers torch"
        ) from exc

    global _DEPTH_ANYTHING_MODEL, _DEPTH_ANYTHING_PROCESSOR
    if "_DEPTH_ANYTHING_MODEL" not in globals() or _DEPTH_ANYTHING_MODEL is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _DEPTH_ANYTHING_PROCESSOR = AutoImageProcessor.from_pretrained(DEPTH_ANYTHING_MODEL_ID)
        _DEPTH_ANYTHING_MODEL = AutoModelForDepthEstimation.from_pretrained(DEPTH_ANYTHING_MODEL_ID).to(device)
        _DEPTH_ANYTHING_MODEL.eval()

    input_rgb = img.convert("RGB")
    w, h = input_rgb.size
    device = next(_DEPTH_ANYTHING_MODEL.parameters()).device
    inputs = _DEPTH_ANYTHING_PROCESSOR(images=input_rgb, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = _DEPTH_ANYTHING_MODEL(**inputs)
        predicted_depth = outputs.predicted_depth
        prediction = torch.nn.functional.interpolate(
            predicted_depth.unsqueeze(1),
            size=(h, w),
            mode="bicubic",
            align_corners=False,
        ).squeeze().cpu().numpy()

    depth = prediction.astype(np.float32)
    depth = (depth - float(depth.min())) / max(1e-6, float(depth.max() - depth.min()))
    border = _border_depth_values(depth)
    if border.size == 0:
        return img.convert("RGBA")

    background_depth = float(np.median(border))
    delta = np.abs(depth - background_depth)
    threshold = max(0.08, float(np.percentile(np.abs(border - background_depth), 90)) * 1.5)
    alpha = np.where(delta > threshold, 255, 0).astype(np.uint8)
    if cv2 is not None:
        alpha = cv2.medianBlur(alpha, 5)
        kernel = np.ones((3, 3), np.uint8)
        alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel, iterations=1)
    mask = Image.fromarray(alpha, mode="L").filter(ImageFilter.GaussianBlur(1.0))
    rgba = img.convert("RGBA")
    out = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    out.paste(rgba, (0, 0), mask=mask)
    return out


def apply_pixeloe_pixelization(img: Image.Image, pixel_size: int = 4, thickness: int = 1) -> Image.Image:
    """Applies detail-oriented pixelization using contrast-aware downscaling and outline expansion."""
    try:
        from pixeloe import pixelize
        np_arr = np.array(img.convert("RGBA"))
        out_arr = pixelize(np_arr, pixel_size=pixel_size, thickness=thickness)
        return Image.fromarray(out_arr, mode="RGBA")
    except Exception as exc:
        logger.debug("Pixeloe pixelization unavailable; using native fallback: %s", exc)
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


def _srgb_to_linear(rgb: np.ndarray) -> np.ndarray:
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(rgb: np.ndarray) -> np.ndarray:
    rgb = np.clip(rgb, 0.0, 1.0)
    return np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.power(rgb, 1 / 2.4) - 0.055)


def _linear_srgb_to_oklab(rgb: np.ndarray) -> np.ndarray:
    l = 0.4122214708 * rgb[:, 0] + 0.5363325363 * rgb[:, 1] + 0.0514459929 * rgb[:, 2]
    m = 0.2119034982 * rgb[:, 0] + 0.6806995451 * rgb[:, 1] + 0.1073969566 * rgb[:, 2]
    s = 0.0883024619 * rgb[:, 0] + 0.2817188376 * rgb[:, 1] + 0.6299787005 * rgb[:, 2]
    l_, m_, s_ = np.cbrt(np.maximum(l, 0.0)), np.cbrt(np.maximum(m, 0.0)), np.cbrt(np.maximum(s, 0.0))
    return np.stack([
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    ], axis=1)


def _oklab_to_linear_srgb(lab: np.ndarray) -> np.ndarray:
    l_ = lab[:, 0] + 0.3963377774 * lab[:, 1] + 0.2158037573 * lab[:, 2]
    m_ = lab[:, 0] - 0.1055613458 * lab[:, 1] - 0.0638541728 * lab[:, 2]
    s_ = lab[:, 0] - 0.0894841775 * lab[:, 1] - 1.2914855480 * lab[:, 2]
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return np.stack([
        +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    ], axis=1)


def _fit_oklab_palette(rgb255: np.ndarray, colors: int, iterations: int = 10) -> np.ndarray:
    rgb = rgb255.astype(np.float32) / 255.0
    lab = _linear_srgb_to_oklab(_srgb_to_linear(rgb))
    unique = np.unique(lab, axis=0)
    k = min(max(1, int(colors)), len(unique))
    if k == len(unique):
        centers = unique
    else:
        order = np.argsort(unique[:, 0])
        centers = unique[order[np.linspace(0, len(unique) - 1, k).astype(int)]].copy()
        for _ in range(iterations):
            dist = np.sum((lab[:, None, :] - centers[None, :, :]) ** 2, axis=2)
            labels = np.argmin(dist, axis=1)
            for i in range(k):
                pts = lab[labels == i]
                if len(pts):
                    centers[i] = pts.mean(axis=0)
    srgb = _linear_to_srgb(_oklab_to_linear_srgb(centers))
    return np.clip(np.round(srgb * 255.0), 0, 255).astype(np.uint8)


def palette_to_native_array(palette: Sequence[Tuple[int, int, int]]) -> np.ndarray:
    out = np.asarray(palette, dtype=np.uint8)
    if out.ndim != 2 or out.shape[1] != 3 or len(out) == 0:
        raise ValueError("Palette must contain at least one RGB color")
    return out


def _nearest_palette_indices_oklab(pixels: np.ndarray, palette: np.ndarray) -> np.ndarray:
    pixel_lab = _linear_srgb_to_oklab(_srgb_to_linear(np.clip(pixels, 0, 255).astype(np.float32) / 255.0))
    palette_lab = _linear_srgb_to_oklab(_srgb_to_linear(palette.astype(np.float32) / 255.0))
    dist = np.sum((pixel_lab[:, None, :] - palette_lab[None, :, :]) ** 2, axis=2)
    return np.argmin(dist, axis=1)


def _bayer_offset(shape: Tuple[int, int], strength: float = 28.0) -> np.ndarray:
    matrix = np.array(
        [
            [0, 8, 2, 10],
            [12, 4, 14, 6],
            [3, 11, 1, 9],
            [15, 7, 13, 5],
        ],
        dtype=np.float32,
    )
    tiled = np.tile(matrix, (shape[0] // 4 + 1, shape[1] // 4 + 1))[: shape[0], : shape[1]]
    return ((tiled + 0.5) / 16.0 - 0.5) * float(strength)


def apply_native_pixel_cleanup(
    img: Image.Image,
    colors: int = 24,
    alpha_threshold: int = 8,
    dither: bool = False,
    dither_mode: str = "none",
    palette: Optional[np.ndarray] = None,
) -> Image.Image:
    """Native Oklab palette cleanup for AI pixel art."""
    arr = np.asarray(img.convert("RGBA")).copy()
    alpha = arr[:, :, 3]
    visible = alpha > alpha_threshold
    if not visible.any():
        return Image.fromarray(arr, mode="RGBA")

    if palette is None:
        palette = _fit_oklab_palette(arr[:, :, :3][visible], colors)
    else:
        palette = palette_to_native_array(palette)
    work = arr[:, :, :3].astype(np.float32)
    if dither and dither_mode == "none":
        dither_mode = "floyd-steinberg"
    dither_mode = str(dither_mode or "none").lower().replace("_", "-")

    if dither_mode in {"floyd-steinberg", "fs"}:
        h, w = alpha.shape
        for y in range(h):
            for x in range(w):
                if not visible[y, x]:
                    continue
                old = work[y, x].copy()
                idx = int(_nearest_palette_indices_oklab(old.reshape(1, 3), palette)[0])
                new = palette[idx].astype(np.float32)
                work[y, x] = new
                err = old - new
                for dx, dy, weight in ((1, 0, 7 / 16), (-1, 1, 3 / 16), (0, 1, 5 / 16), (1, 1, 1 / 16)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and visible[ny, nx]:
                        work[ny, nx] += err * weight
    elif dither_mode == "bayer":
        offset = _bayer_offset(alpha.shape)[:, :, None]
        shifted = np.clip(work + offset, 0, 255)
        pixels = shifted[visible]
        work[visible] = palette[_nearest_palette_indices_oklab(pixels, palette)]
    else:
        pixels = work[visible]
        work[visible] = palette[_nearest_palette_indices_oklab(pixels, palette)]

    arr[:, :, :3] = np.clip(work, 0, 255).astype(np.uint8)
    arr[:, :, 3] = np.where(visible, np.where(alpha > 240, 255, alpha), 0).astype(np.uint8)
    return Image.fromarray(arr, mode="RGBA")


def fit_native_pixel_palette(
    images: Sequence[Image.Image],
    colors: int = 24,
    alpha_threshold: int = 8,
) -> np.ndarray:
    samples = []
    for img in images:
        arr = np.asarray(img.convert("RGBA"))
        visible = arr[:, :, 3] > alpha_threshold
        if visible.any():
            samples.append(arr[:, :, :3][visible])
    if not samples:
        return np.array([[0, 0, 0]], dtype=np.uint8)
    return _fit_oklab_palette(np.concatenate(samples, axis=0), colors)



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
