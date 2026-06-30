#!/usr/bin/env python3
"""Video/frame loading, extraction, and inspection for sprite processing."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

try:
    import cv2
except Exception:
    cv2 = None

from dataclasses import dataclass

from spriteforge_utils import natural_key

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


@dataclass
class FrameItem:
    image: Image.Image
    name: str
    source_index: int = 0


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_image(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def extract_video_frames(
    input_path: Path,
    target_fps: Optional[float],
    start_seconds: float,
    end_seconds: Optional[float],
    max_frames: Optional[int],
    stride: int,
) -> Tuple[List[FrameItem], float, Dict[str, Any]]:
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
                cap.release()
            except Exception:
                pass
            errors.append(f"OpenCV failed: {exc}")
    else:
        errors.append("OpenCV is not installed")

    # Fallback: imageio with ffmpeg
    try:
        import imageio.v2 as imageio

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
    return recommender(path, width, height, fps, frame_count, duration, recommended_fps, recommended_cell)


def recommender(path, width, height, fps, frame_count, duration, recommended_fps, recommended_cell):
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
            "start_command": f"python spriteforge.py video --input \"{path}\" --output output/{Path(path).stem}_sprite --fps {recommended_fps} --cell-size {recommended_cell}x{recommended_cell} --key-color auto --anchor bottom-center --solidify 2 --preview-gif --report",
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


def next_power_of_two(n: int) -> int:
    if n <= 1:
        return 1
    return 1 << (n - 1).bit_length()