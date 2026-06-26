#!/usr/bin/env python3
"""
SpriteForge v2: video/frame-folder to game-ready spritesheet converter.

Typical WAN/ComfyUI video conversion:

python spriteforge.py video --input input/wan_walk.mp4 --output output/wan_walk_sprite --fps 12 --cell-size 512x512 --key-color auto --key-tolerance 45 --anchor bottom-center --pad 24 --solidify 2 --preview-gif --report

Typical Blender transparent frame packing:

python spriteforge.py pack --input output/ortho_frames --output output/ortho_sprite --fps 12 --cell-size 512x512 --anchor bottom-center --solidify 2 --preview-gif --report
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageSequence, ImageFilter

try:
    import cv2
except Exception:
    cv2 = None

from services.sprite_service import SpriteService


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


@dataclass
class FrameItem:
    image: Image.Image
    name: str
    source_index: int = 0


@dataclass
class ProcessResult:
    output: Path
    frame_count: int
    cell_size: Tuple[int, int]
    columns: int
    rows: int
    fps: float
    sheet_path: Path
    metadata_path: Path


def natural_key(path: Path) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def parse_size(value: Optional[str]) -> Optional[Tuple[int, int]]:
    if value is None:
        return None
    value = value.lower().strip()
    if "x" not in value:
        raise argparse.ArgumentTypeError("Size must look like 512x512")
    a, b = value.split("x", 1)
    w, h = int(a), int(b)
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("Size values must be positive")
    return w, h


def parse_rgb(value: Optional[str]) -> Optional[Union[Tuple[int, int, int], str]]:
    if value is None:
        return None
    value = value.strip().lower()
    if value == "auto":
        return "auto"
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("Color must be auto or R,G,B, for example 0,255,0")
    rgb = tuple(int(p) for p in parts)
    if any(v < 0 or v > 255 for v in rgb):
        raise argparse.ArgumentTypeError("RGB values must be between 0 and 255")
    return rgb  # type: ignore[return-value]


def parse_rgba(value: str) -> Tuple[int, int, int, int]:
    parts = [p.strip() for p in value.split(",")]
    if len(parts) == 3:
        parts.append("255")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("Color must be R,G,B or R,G,B,A")
    rgba = tuple(int(p) for p in parts)
    if any(v < 0 or v > 255 for v in rgba):
        raise argparse.ArgumentTypeError("RGBA values must be between 0 and 255")
    return rgba  # type: ignore[return-value]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_image(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def save_png_sequence(frames: Sequence[FrameItem], out_dir: Path, prefix: str = "frame") -> List[Path]:
    ensure_dir(out_dir)
    paths: List[Path] = []
    pad = max(4, len(str(len(frames))))
    for i, item in enumerate(frames):
        p = out_dir / f"{prefix}_{i:0{pad}d}.png"
        item.image.save(p)
        paths.append(p)
    return paths


def extract_video_frames(
    input_path: Path,
    target_fps: Optional[float],
    start_seconds: float,
    end_seconds: Optional[float],
    max_frames: Optional[int],
    stride: int,
) -> Tuple[List[FrameItem], float, Dict[str, Any]]:
    """Extract video frames with OpenCV first, then imageio/ffmpeg fallback.

    OpenCV is fast, but some Windows builds struggle with certain WEBM/MOV files.
    The fallback makes the end-user path less brittle for ComfyUI outputs.
    """
    errors: List[str] = []

    def sample_accept(t: float, read_index: int, next_sample_t: float) -> Tuple[bool, float]:
        if end_seconds is not None and t > end_seconds:
            return False, next_sample_t
        if stride > 1 and (read_index - 1) % stride != 0:
            return False, next_sample_t
        if target_fps is not None:
            if t + 1e-6 < next_sample_t:
                return False, next_sample_t
            next_sample_t += 1.0 / float(target_fps)
        return True, next_sample_t

    if cv2 is not None:
        try:
            cap = cv2.VideoCapture(str(input_path))
            if not cap.isOpened():
                raise RuntimeError("OpenCV could not open the video")

            src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            duration = frame_count / src_fps if src_fps > 0 else 0.0

            if start_seconds > 0:
                cap.set(cv2.CAP_PROP_POS_MSEC, start_seconds * 1000.0)

            out_fps = float(target_fps or src_fps or 30.0)
            next_sample_t = start_seconds
            frames: List[FrameItem] = []
            read_index = 0

            while True:
                ok, bgr = cap.read()
                if not ok:
                    break

                current_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                t = current_msec / 1000.0 if current_msec else (read_index / src_fps)
                read_index += 1

                if end_seconds is not None and t > end_seconds:
                    break

                accepted, next_sample_t = sample_accept(t, read_index, next_sample_t)
                if not accepted:
                    continue

                rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)
                img = Image.fromarray(rgba, mode="RGBA")
                frames.append(FrameItem(img, f"{input_path.stem}_{len(frames):04d}", source_index=read_index - 1))

                if max_frames is not None and len(frames) >= max_frames:
                    break

            cap.release()

            if frames:
                meta = {
                    "source_path": str(input_path),
                    "source_name": input_path.name,
                    "source_fps": src_fps,
                    "source_frame_count": frame_count,
                    "source_width": width,
                    "source_height": height,
                    "source_duration_seconds": duration,
                    "extracted_fps": out_fps,
                    "extracted_frame_count": len(frames),
                    "decoder": "opencv",
                }
                return frames, out_fps, meta
            errors.append("OpenCV opened the file but extracted 0 frames")
        except Exception as exc:
            try:
                cap.release()  # type: ignore[name-defined]
            except Exception:
                pass
            errors.append(f"OpenCV failed: {exc}")
    else:
        errors.append("OpenCV is not installed")

    # Fallback: imageio with ffmpeg. This often handles WEBM/MOV files that OpenCV rejects.
    try:
        import imageio.v2 as imageio  # type: ignore

        reader = imageio.get_reader(str(input_path), "ffmpeg")
        meta_in = reader.get_meta_data() or {}
        src_fps = float(meta_in.get("fps") or 30.0)
        size = meta_in.get("size") or (0, 0)
        width = int(size[0]) if len(size) >= 1 else 0
        height = int(size[1]) if len(size) >= 2 else 0
        duration = float(meta_in.get("duration") or 0.0)
        frame_count = int(meta_in.get("nframes") or 0) if str(meta_in.get("nframes", "")).isdigit() else 0
        out_fps = float(target_fps or src_fps or 30.0)
        next_sample_t = start_seconds
        frames = []

        for idx, frame in enumerate(reader):
            t = idx / src_fps if src_fps > 0 else 0.0
            if t < start_seconds:
                continue
            if end_seconds is not None and t > end_seconds:
                break
            read_index = idx + 1
            accepted, next_sample_t = sample_accept(t, read_index, next_sample_t)
            if not accepted:
                continue

            arr = np.asarray(frame)
            if arr.ndim == 2:
                arr = np.stack([arr, arr, arr], axis=-1)
            if arr.shape[-1] == 3:
                alpha = np.full(arr.shape[:2] + (1,), 255, dtype=arr.dtype)
                arr = np.concatenate([arr, alpha], axis=-1)
            elif arr.shape[-1] > 4:
                arr = arr[:, :, :4]
            img = Image.fromarray(arr.astype(np.uint8), mode="RGBA")
            frames.append(FrameItem(img, f"{input_path.stem}_{len(frames):04d}", source_index=idx))
            if max_frames is not None and len(frames) >= max_frames:
                break
        reader.close()

        if not frames:
            raise RuntimeError("imageio/ffmpeg extracted 0 frames")

        meta = {
            "source_path": str(input_path),
            "source_name": input_path.name,
            "source_fps": src_fps,
            "source_frame_count": frame_count,
            "source_width": width,
            "source_height": height,
            "source_duration_seconds": duration,
            "extracted_fps": out_fps,
            "extracted_frame_count": len(frames),
            "decoder": "imageio-ffmpeg",
            "opencv_errors": errors,
        }
        return frames, out_fps, meta
    except Exception as exc:
        errors.append(f"imageio/ffmpeg failed: {exc}")

    raise RuntimeError("No frames were extracted. " + " | ".join(errors))


def load_frame_folder(input_dir: Path, max_frames: Optional[int] = None) -> List[FrameItem]:
    files = sorted([p for p in input_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS], key=natural_key)
    if max_frames is not None:
        files = files[:max_frames]
    if not files:
        raise RuntimeError(f"No image frames found in: {input_dir}")

    return [FrameItem(load_image(p), p.stem, source_index=i) for i, p in enumerate(files)]


def guess_key_color_from_corners(img: Image.Image, sample: int = 12) -> Tuple[int, int, int]:
    arr = np.asarray(img.convert("RGBA"), dtype=np.float32)
    h, w = arr.shape[:2]
    sample = max(1, min(sample, max(1, h // 2), max(1, w // 2)))

    patches = [
        arr[:sample, :sample, :3],
        arr[:sample, w - sample :, :3],
        arr[h - sample :, :sample, :3],
        arr[h - sample :, w - sample :, :3],
    ]
    pixels = np.concatenate([p.reshape(-1, 3) for p in patches], axis=0)
    rgb = np.median(pixels, axis=0)
    return tuple(int(round(x)) for x in rgb)


def apply_chroma_key(
    img: Image.Image,
    key_color: Union[Tuple[int, int, int], str],
    tolerance: float,
    feather: float,
) -> Image.Image:
    return SpriteService.apply_chroma_key(img, key_color, tolerance, feather)


def try_rembg(img: Image.Image) -> Image.Image:
    try:
        from rembg import remove  # type: ignore
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
    """Fill RGB values under transparent pixels from nearby opaque pixels to reduce texture-filter fringes."""
    if iterations <= 0:
        return img.convert("RGBA")
    if cv2 is None:
        return img.convert("RGBA")

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


def apply_frame_sequence_ops(
    frames: List[FrameItem],
    drop_last: bool,
    drop_loop_duplicate: bool,
    loop_mode: str,
    reverse: bool,
    flip_x: bool,
    flip_y: bool,
) -> List[FrameItem]:
    out = list(frames)

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


def frame_difference(a: Image.Image, b: Image.Image) -> float:
    a_small = a.convert("RGBA").resize((64, 64), Image.Resampling.BILINEAR)
    b_small = b.convert("RGBA").resize((64, 64), Image.Resampling.BILINEAR)
    aa = np.asarray(a_small).astype(np.float32)
    bb = np.asarray(b_small).astype(np.float32)
    return float(np.mean(np.abs(aa - bb)))


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
        frame_data.append(
            {
                "index": i,
                "name": f"{animation_name}_{i:04d}",
                "source_name": item.name,
                "source_index": item.source_index,
                "x": rect["x"],
                "y": rect["y"],
                "w": rect["w"],
                "h": rect["h"],
                "duration_ms": duration_ms,
            }
        )

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
            "rotated": False,
            "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": cell_w, "h": cell_h},
            "sourceSize": {"w": cell_w, "h": cell_h},
            "duration": duration_ms,
        }

    data = {
        "frames": ase_frames,
        "meta": {
            "app": "SpriteForge",
            "version": "2.0",
            "image": image_name,
            "format": "RGBA8888",
            "size": {"w": 0, "h": 0},
            "scale": "1",
            "frameTags": [
                {"name": animation_name, "from": 0, "to": max(0, len(frames) - 1), "direction": "forward"}
            ],
        },
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def make_preview_gif(frames: Sequence[FrameItem], path: Path, fps: float) -> None:
    if not frames:
        return
    duration = int(round(1000.0 / fps)) if fps > 0 else 83
    imgs = [f.image.convert("RGBA") for f in frames]
    imgs[0].save(
        path,
        save_all=True,
        append_images=imgs[1:],
        duration=duration,
        loop=0,
        disposal=2,
    )


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


def write_godot_notes(path: Path, result: ProcessResult) -> None:
    text = f"""SpriteForge Godot notes

Sprite2D setup:
- Texture: sheet.png
- hframes: {result.columns}
- vframes: {result.rows}
- Frame range: 0 to {result.frame_count - 1}
- FPS: {result.fps:g}
- Cell size: {result.cell_size[0]}x{result.cell_size[1]}

For AnimatedSprite2D:
- Create SpriteFrames resource.
- Add animation.
- Add frames from sheet.png using the same {result.cell_size[0]}x{result.cell_size[1]} grid.
- Set animation speed to {result.fps:g} FPS.

If you used --spacing or --margin, use the rectangle data in sheet.json instead of plain hframes/vframes slicing.
"""
    path.write_text(text, encoding="utf-8")


def write_report(path: Path, result: ProcessResult, extra: Dict[str, Any]) -> None:
    sheet_rel = result.sheet_path.name
    preview_exists = (result.output / "preview.gif").exists()
    contact_exists = (result.output / "contact_sheet.jpg").exists()
    preview_html = '<p><img src="preview.gif" /></p>' if preview_exists else ""
    contact_html = '<p><img src="contact_sheet.jpg" /></p>' if contact_exists else ""
    extra_json = json.dumps(extra, indent=2)

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>SpriteForge Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; line-height: 1.4; }}
    code, pre {{ background: #f3f3f3; padding: 2px 4px; }}
    pre {{ padding: 12px; overflow: auto; }}
    img {{ max-width: 100%; image-rendering: auto; }}
    table {{ border-collapse: collapse; }}
    td, th {{ border: 1px solid #ccc; padding: 6px 8px; }}
  </style>
</head>
<body>
  <h1>SpriteForge Report</h1>
  <table>
    <tr><th>Frames</th><td>{result.frame_count}</td></tr>
    <tr><th>FPS</th><td>{result.fps:g}</td></tr>
    <tr><th>Cell</th><td>{result.cell_size[0]}x{result.cell_size[1]}</td></tr>
    <tr><th>Grid</th><td>{result.columns} columns x {result.rows} rows</td></tr>
  </table>
  <h2>Preview</h2>
  {preview_html}
  <h2>Contact sheet</h2>
  {contact_html}
  <h2>Spritesheet</h2>
  <p><img src="{sheet_rel}" /></p>
  <h2>Extra metadata</h2>
  <pre>{extra_json}</pre>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def process_common(
    frames: Sequence[FrameItem],
    output: Path,
    fps: float,
    cell_size: Optional[Tuple[int, int]],
    key_color: Optional[Union[Tuple[int, int, int], str]],
    key_tolerance: float,
    key_feather: float,
    rembg: bool,
    crop_mode: str,
    pad: int,
    alpha_threshold: int,
    columns: Optional[int],
    animation_name: str,
    preview_gif: bool,
    save_processed_frames: bool,
    anchor: str,
    ground_margin: int,
    spacing: int,
    margin: int,
    solidify: int,
    outline_width: int,
    outline_color: Tuple[int, int, int, int],
    power_of_two: bool,
    loop_mode: str,
    drop_last: bool,
    drop_loop_duplicate: bool,
    reverse: bool,
    flip_x: bool,
    flip_y: bool,
    report: bool,
    source_meta: Optional[Dict[str, Any]] = None,
) -> ProcessResult:
    ensure_dir(output)

    working = apply_frame_sequence_ops(
        list(frames),
        drop_last=drop_last,
        drop_loop_duplicate=drop_loop_duplicate,
        loop_mode=loop_mode,
        reverse=reverse,
        flip_x=flip_x,
        flip_y=flip_y,
    )

    processed: List[FrameItem] = []
    for item in working:
        img = item.image.convert("RGBA")
        if key_color is not None:
            img = apply_chroma_key(img, key_color, key_tolerance, key_feather)
        if rembg:
            img = try_rembg(img)
        if outline_width > 0:
            img = add_outline(img, outline_width, outline_color)
        processed.append(FrameItem(img, item.name, item.source_index))

    normalized, final_cell, normalize_info = normalize_frames(
        processed,
        cell_size=cell_size,
        crop_mode=crop_mode,
        pad=pad,
        alpha_threshold=alpha_threshold,
        anchor=anchor,
        ground_margin=ground_margin,
    )

    if solidify > 0:
        normalized = [
            FrameItem(solidify_transparent_rgb(item.image, solidify, alpha_threshold), item.name, item.source_index)
            for item in normalized
        ]

    if save_processed_frames:
        save_png_sequence(normalized, output / "frames_processed")

    sheet, cols, rows, rects = pack_sheet(normalized, columns, spacing, margin, power_of_two)
    sheet_path = output / "sheet.png"
    sheet.save(sheet_path)

    extra = {
        "source": source_meta or {},
        "normalize": normalize_info,
        "loop_mode": loop_mode,
        "solidify": solidify,
        "outline_width": outline_width,
        "power_of_two": power_of_two,
    }

    metadata_path = output / "sheet.json"
    write_metadata(
        metadata_path,
        image_name="sheet.png",
        frames=normalized,
        rects=rects,
        cell_size=final_cell,
        columns=cols,
        rows=rows,
        fps=fps,
        animation_name=animation_name,
        spacing=spacing,
        margin=margin,
        extra=extra,
    )

    write_aseprite_json(
        output / "sheet.aseprite.json",
        image_name="sheet.png",
        frames=normalized,
        rects=rects,
        cell_size=final_cell,
        fps=fps,
        animation_name=animation_name,
    )

    if preview_gif:
        make_preview_gif(normalized, output / "preview.gif", fps)

    make_contact_sheet(normalized, output / "contact_sheet.jpg")

    result = ProcessResult(
        output=output,
        frame_count=len(normalized),
        cell_size=final_cell,
        columns=cols,
        rows=rows,
        fps=fps,
        sheet_path=sheet_path,
        metadata_path=metadata_path,
    )
    write_godot_notes(output / "godot_notes.txt", result)

    if report:
        write_report(output / "report.html", result, extra)

    print("Done.")
    print(f"Frames: {len(normalized)}")
    print(f"Cell: {final_cell[0]}x{final_cell[1]}")
    print(f"Grid: {cols}x{rows}")
    print(f"Sheet: {sheet_path}")
    print(f"Metadata: {metadata_path}")
    print(f"Aseprite JSON: {output / 'sheet.aseprite.json'}")
    print(f"Godot notes: {output / 'godot_notes.txt'}")
    if preview_gif:
        print(f"Preview: {output / 'preview.gif'}")
    if report:
        print(f"Report: {output / 'report.html'}")

    return result


def cmd_video(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    output = Path(args.output)
    ensure_dir(output)

    frames, fps, source_meta = extract_video_frames(
        input_path=input_path,
        target_fps=args.fps,
        start_seconds=args.start,
        end_seconds=args.end,
        max_frames=args.max_frames,
        stride=args.stride,
    )

    if args.save_raw_frames:
        save_png_sequence(frames, output / "frames_raw", prefix="raw")

    process_common_from_args(frames, output, float(args.fps or fps), args, source_meta=source_meta)


def cmd_pack(args: argparse.Namespace) -> None:
    input_dir = Path(args.input)
    frames = load_frame_folder(input_dir, max_frames=args.max_frames)
    source_meta = {"source_type": "frame_folder", "source_folder": str(input_dir), "loaded_frame_count": len(frames)}
    process_common_from_args(frames, Path(args.output), float(args.fps), args, source_meta=source_meta)


def process_common_from_args(
    frames: Sequence[FrameItem],
    output: Path,
    fps: float,
    args: argparse.Namespace,
    source_meta: Optional[Dict[str, Any]] = None,
) -> ProcessResult:
    return process_common(
        frames=frames,
        output=output,
        fps=fps,
        cell_size=parse_size(args.cell_size),
        key_color=parse_rgb(args.key_color),
        key_tolerance=args.key_tolerance,
        key_feather=args.key_feather,
        rembg=args.rembg,
        crop_mode=args.crop_mode,
        pad=args.pad,
        alpha_threshold=args.alpha_threshold,
        columns=args.columns,
        animation_name=args.animation,
        preview_gif=args.preview_gif,
        save_processed_frames=True,
        anchor=args.anchor,
        ground_margin=args.ground_margin,
        spacing=args.spacing,
        margin=args.margin,
        solidify=args.solidify,
        outline_width=args.outline_width,
        outline_color=parse_rgba(args.outline_color),
        power_of_two=args.power_of_two,
        loop_mode=args.loop_mode,
        drop_last=args.drop_last,
        drop_loop_duplicate=args.drop_loop_duplicate,
        reverse=args.reverse,
        flip_x=args.flip_x,
        flip_y=args.flip_y,
        report=args.report,
        source_meta=source_meta,
    )


def inspect_video(path: Path) -> Dict[str, Any]:
    if cv2 is None:
        raise RuntimeError("opencv-python is required for video inspection.")
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()
    duration = frame_count / fps if fps else 0
    recommended_fps = 12 if fps >= 12 else max(1, int(round(fps)))
    recommended_cell = max(256, next_power_of_two(max(width, height)))
    recommended_cell = min(recommended_cell, 1024)
    return {
        "type": "video",
        "path": str(path),
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": duration,
        "recommendation": {
            "fps": recommended_fps,
            "cell_size": f"{recommended_cell}x{recommended_cell}",
            "start_command": f"python spriteforge.py video --input \"{path}\" --output output/{path.stem}_sprite --fps {recommended_fps} --cell-size {recommended_cell}x{recommended_cell} --key-color auto --anchor bottom-center --solidify 2 --preview-gif --report",
        },
    }


def inspect_frame_folder(path: Path) -> Dict[str, Any]:
    files = sorted([p for p in path.iterdir() if p.suffix.lower() in IMAGE_EXTS], key=natural_key)
    if not files:
        raise RuntimeError(f"No image frames found in {path}")
    sizes = []
    for p in files[:20]:
        with Image.open(p) as img:
            sizes.append(img.size)
    max_w = max(w for w, _ in sizes)
    max_h = max(h for _, h in sizes)
    recommended_cell = max(256, next_power_of_two(max(max_w, max_h)))
    recommended_cell = min(recommended_cell, 1024)
    return {
        "type": "frame_folder",
        "path": str(path),
        "frame_count": len(files),
        "sample_sizes": sizes[:5],
        "recommendation": {
            "fps": 12,
            "cell_size": f"{recommended_cell}x{recommended_cell}",
            "start_command": f"python spriteforge.py pack --input \"{path}\" --output output/{path.name}_sprite --fps 12 --cell-size {recommended_cell}x{recommended_cell} --anchor bottom-center --solidify 2 --preview-gif --report",
        },
    }


def cmd_inspect(args: argparse.Namespace) -> None:
    path = Path(args.input)
    if path.is_dir():
        data = inspect_frame_folder(path)
    elif path.suffix.lower() in VIDEO_EXTS:
        data = inspect_video(path)
    else:
        raise RuntimeError("Inspect supports video files or folders of image frames.")
    text = json.dumps(data, indent=2)
    print(text)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")


def cmd_batch(args: argparse.Namespace) -> None:
    config_path = Path(args.config)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    jobs = data.get("jobs", [])
    if not isinstance(jobs, list) or not jobs:
        raise RuntimeError("Batch config must contain a non-empty 'jobs' list.")

    for i, job in enumerate(jobs):
        print(f"\n=== Batch job {i + 1}/{len(jobs)} ===")
        mode = job.get("mode")
        if mode not in {"video", "pack"}:
            raise RuntimeError(f"Job {i + 1}: mode must be 'video' or 'pack'.")

        # Build a pseudo-argv from config, then reuse parser.
        argv = [mode]
        for key, value in job.items():
            if key == "mode":
                continue
            flag = "--" + key.replace("_", "-")
            if isinstance(value, bool):
                if value:
                    argv.append(flag)
            elif value is not None:
                argv.extend([flag, str(value)])
        parsed = build_parser().parse_args(argv)
        parsed.func(parsed)


def newest_matching_files(folder: Path, pattern: str) -> List[Path]:
    return sorted(
        [p for p in folder.iterdir() if p.is_file() and fnmatch.fnmatch(p.name.lower(), pattern.lower())],
        key=lambda p: p.stat().st_mtime,
    )


def wait_until_file_stable(path: Path, stable_seconds: float) -> bool:
    last_size = -1
    last_change = time.time()
    while True:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return False
        now = time.time()
        if size != last_size:
            last_size = size
            last_change = now
        if now - last_change >= stable_seconds:
            return True
        time.sleep(0.5)


def cmd_watch(args: argparse.Namespace) -> None:
    folder = Path(args.folder)
    if not folder.exists():
        raise RuntimeError(f"Watch folder does not exist: {folder}")
    out_root = Path(args.output)
    ensure_dir(out_root)
    seen = {p.resolve() for p in newest_matching_files(folder, args.pattern)}
    print(f"Watching {folder} for {args.pattern}. Press Ctrl+C to stop.")

    while True:
        try:
            files = newest_matching_files(folder, args.pattern)
            for p in files:
                rp = p.resolve()
                if rp in seen:
                    continue
                print(f"New file: {p}")
                if not wait_until_file_stable(p, args.stable_seconds):
                    continue
                seen.add(rp)
                out_dir = out_root / f"{p.stem}_sprite"
                # Reuse video path with defaults from watch args.
                class Obj:
                    pass
                fake = Obj()
                for k, v in vars(args).items():
                    setattr(fake, k, v)
                fake.input = str(p)
                fake.output = str(out_dir)
                fake.start = 0.0
                fake.end = None
                fake.max_frames = args.max_frames
                fake.stride = args.stride
                fake.save_raw_frames = False
                cmd_video(fake)  # type: ignore[arg-type]
            time.sleep(args.poll_seconds)
        except KeyboardInterrupt:
            print("Stopped.")
            return


def add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--output", required=True, help="Output folder")
    p.add_argument("--fps", type=float, default=12.0, help="Output animation FPS")
    p.add_argument("--cell-size", default=None, help="Final cell size, for example 512x512. Auto if omitted.")
    p.add_argument("--columns", type=int, default=None, help="Number of spritesheet columns. Auto if omitted.")
    p.add_argument("--animation", default="anim", help="Animation name for metadata")
    p.add_argument("--preview-gif", action="store_true", help="Export preview.gif")
    p.add_argument("--report", action="store_true", help="Export report.html and contact sheet")

    p.add_argument("--key-color", default=None, help="Chroma key color: auto or R,G,B. Example: --key-color 0,255,0")
    p.add_argument("--key-tolerance", type=float, default=45.0, help="Chroma key tolerance")
    p.add_argument("--key-feather", type=float, default=25.0, help="Soft edge width for chroma key")
    p.add_argument("--rembg", action="store_true", help="Optional AI background removal. Requires rembg + onnxruntime.")

    p.add_argument("--crop-mode", choices=["global", "per-frame", "none"], default="global", help="Canvas crop mode")
    p.add_argument("--pad", type=int, default=16, help="Padding around detected subject")
    p.add_argument("--alpha-threshold", type=int, default=8, help="Alpha threshold for subject bounds")
    p.add_argument("--anchor", choices=["center", "bottom-center", "top-center", "bottom-left", "bottom-right", "left-center", "right-center"], default="bottom-center", help="Where the subject should sit inside the sprite cell")
    p.add_argument("--ground-margin", type=int, default=0, help="Pixels from bottom/edge when using bottom/top/side anchors")

    p.add_argument("--spacing", type=int, default=0, help="Pixels between cells in the spritesheet")
    p.add_argument("--margin", type=int, default=0, help="Outer margin around the spritesheet")
    p.add_argument("--power-of-two", action="store_true", help="Pad final sheet to power-of-two dimensions")
    p.add_argument("--solidify", type=int, default=2, help="Fill transparent RGB edge pixels to reduce filtering fringes. 0 disables.")
    p.add_argument("--outline-width", type=int, default=0, help="Optional outline width in pixels")
    p.add_argument("--outline-color", default="0,0,0,255", help="Outline color as R,G,B,A")

    p.add_argument("--loop-mode", choices=["normal", "pingpong"], default="normal", help="Loop construction mode")
    p.add_argument("--drop-last", action="store_true", help="Drop the last frame manually")
    p.add_argument("--drop-loop-duplicate", action="store_true", help="Drop last frame if it is nearly identical to the first")
    p.add_argument("--reverse", action="store_true", help="Reverse frame order")
    p.add_argument("--flip-x", action="store_true", help="Flip frames horizontally")
    p.add_argument("--flip-y", action="store_true", help="Flip frames vertically")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SpriteForge v2 spritesheet toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    p_video = sub.add_parser("video", help="Convert a video to spritesheet")
    add_common_args(p_video)
    p_video.add_argument("--input", required=True, help="Input video file")
    p_video.add_argument("--start", type=float, default=0.0, help="Start time in seconds")
    p_video.add_argument("--end", type=float, default=None, help="End time in seconds")
    p_video.add_argument("--max-frames", type=int, default=None, help="Maximum frames to use")
    p_video.add_argument("--stride", type=int, default=1, help="Use every Nth source frame before FPS sampling")
    p_video.add_argument("--save-raw-frames", action="store_true", help="Save raw extracted frames")
    p_video.set_defaults(func=cmd_video)

    p_pack = sub.add_parser("pack", help="Pack image frames from a folder")
    add_common_args(p_pack)
    p_pack.add_argument("--input", required=True, help="Input folder containing PNG/JPG/etc frames")
    p_pack.add_argument("--max-frames", type=int, default=None, help="Maximum frames to use")
    p_pack.set_defaults(func=cmd_pack)

    p_inspect = sub.add_parser("inspect", help="Inspect a video or frame folder and print recommended command")
    p_inspect.add_argument("--input", required=True, help="Video file or image frame folder")
    p_inspect.add_argument("--output", default=None, help="Optional JSON output path")
    p_inspect.set_defaults(func=cmd_inspect)

    p_batch = sub.add_parser("batch", help="Process multiple jobs from a JSON config")
    p_batch.add_argument("--config", required=True, help="Batch config JSON")
    p_batch.set_defaults(func=cmd_batch)

    p_watch = sub.add_parser("watch", help="Watch a folder for new videos and auto-convert them")
    add_common_args(p_watch)
    p_watch.add_argument("--folder", required=True, help="Folder to watch, e.g. ComfyUI output folder")
    p_watch.add_argument("--pattern", default="*.mp4", help="Filename pattern to watch")
    p_watch.add_argument("--poll-seconds", type=float, default=3.0)
    p_watch.add_argument("--stable-seconds", type=float, default=3.0)
    p_watch.add_argument("--max-frames", type=int, default=None)
    p_watch.add_argument("--stride", type=int, default=1)
    p_watch.set_defaults(func=cmd_watch)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
