#!/usr/bin/env python3
"""Native frame interpolation helpers for sprite animations."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple
import logging
import os
import shutil
import subprocess
import tempfile

import numpy as np

from PIL import Image

try:
    import cv2
except Exception as exc:
    logging.getLogger(__name__).debug("OpenCV unavailable for optical-flow interpolation; blend fallback will be used: %s", exc)
    cv2 = None

from services.sprite_video_loader import FrameItem


DEFAULT_IMPACT_PATTERNS = ("impact", "hit", "contact", "strike", "slash", "smear", "anticipation")


def interpolated_count(source_count: int, source_fps: float, target_fps: float) -> int:
    if source_count <= 1 or source_fps <= 0 or target_fps <= source_fps:
        return source_count
    duration = (source_count - 1) / source_fps
    return int(round(duration * target_fps)) + 1


def interpolate_frames_blend(
    frames: Sequence[FrameItem],
    source_fps: float,
    target_fps: float,
    hold_all_transitions: bool = False,
    hold_name_patterns: Sequence[str] = (),
) -> Tuple[List[FrameItem], float]:
    """Interpolate frames with alpha-aware linear blending.

    This is not a RIFE replacement, but it gives SpriteForge a deterministic
    built-in polish pass and the same pipeline shape used by optional RIFE.
    """
    if len(frames) <= 1 or source_fps <= 0 or target_fps <= source_fps:
        return list(frames), source_fps

    total = interpolated_count(len(frames), source_fps, target_fps)
    out: List[FrameItem] = []
    for out_idx in range(total):
        t = out_idx / target_fps
        source_pos = min(t * source_fps, len(frames) - 1)
        left = int(source_pos)
        right = min(left + 1, len(frames) - 1)
        frac = source_pos - left
        if right == left or frac <= 1e-6:
            img = frames[left].image.copy()
        elif _should_hold_transition(frames[left], frames[right], hold_all_transitions, hold_name_patterns):
            chosen = left if frac < 0.5 else right
            img = frames[chosen].image.copy()
        else:
            a = frames[left].image.convert("RGBA")
            b = frames[right].image.convert("RGBA")
            img = Image.blend(a, b, frac)
        out.append(FrameItem(img, f"{frames[left].name}_interp_{out_idx:04d}", frames[left].source_index))
    return out, target_fps


def _warp_with_flow(arr: np.ndarray, flow: np.ndarray, amount: float) -> np.ndarray:
    h, w = flow.shape[:2]
    grid_x, grid_y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    map_x = grid_x + flow[:, :, 0] * amount
    map_y = grid_y + flow[:, :, 1] * amount
    return cv2.remap(arr, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def interpolate_frames_flow(
    frames: Sequence[FrameItem],
    source_fps: float,
    target_fps: float,
    hold_all_transitions: bool = False,
    hold_name_patterns: Sequence[str] = (),
) -> Tuple[List[FrameItem], float]:
    """Interpolate with native OpenCV optical flow, falling back to blending."""
    if cv2 is None:
        return interpolate_frames_blend(frames, source_fps, target_fps, hold_all_transitions, hold_name_patterns)
    if len(frames) <= 1 or source_fps <= 0 or target_fps <= source_fps:
        return list(frames), source_fps

    total = interpolated_count(len(frames), source_fps, target_fps)
    rgba = [np.asarray(frame.image.convert("RGBA")).astype(np.uint8) for frame in frames]
    gray = [cv2.cvtColor(arr[:, :, :3], cv2.COLOR_RGB2GRAY) for arr in rgba]
    out: List[FrameItem] = []

    for out_idx in range(total):
        t = out_idx / target_fps
        source_pos = min(t * source_fps, len(frames) - 1)
        left = int(source_pos)
        right = min(left + 1, len(frames) - 1)
        frac = source_pos - left
        if right == left or frac <= 1e-6:
            img = frames[left].image.copy()
        elif _should_hold_transition(frames[left], frames[right], hold_all_transitions, hold_name_patterns):
            chosen = left if frac < 0.5 else right
            img = frames[chosen].image.copy()
        else:
            flow_lr = cv2.calcOpticalFlowFarneback(gray[left], gray[right], None, 0.5, 3, 15, 3, 5, 1.2, 0)
            flow_rl = cv2.calcOpticalFlowFarneback(gray[right], gray[left], None, 0.5, 3, 15, 3, 5, 1.2, 0)
            left_warp = _warp_with_flow(rgba[left], flow_lr, frac)
            right_warp = _warp_with_flow(rgba[right], flow_rl, 1.0 - frac)
            blended = left_warp.astype(np.float32) * (1.0 - frac) + right_warp.astype(np.float32) * frac
            img = Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8), mode="RGBA")
        out.append(FrameItem(img, f"{frames[left].name}_flow_{out_idx:04d}", frames[left].source_index))
    return out, target_fps


def _normalized_patterns(patterns: Optional[Iterable[str]]) -> Tuple[str, ...]:
    return tuple(str(p).strip().lower() for p in (patterns or ()) if str(p).strip())


def _should_hold_transition(
    left: FrameItem,
    right: FrameItem,
    hold_all_transitions: bool,
    hold_name_patterns: Sequence[str],
) -> bool:
    if hold_all_transitions:
        return True
    if not hold_name_patterns:
        return False
    names = f"{left.name} {right.name}".lower()
    return any(pattern in names for pattern in hold_name_patterns)


def held_transition_count(
    frames: Sequence[FrameItem],
    hold_all_transitions: bool = False,
    hold_name_patterns: Sequence[str] = (),
) -> int:
    return sum(
        1
        for idx in range(max(0, len(frames) - 1))
        if _should_hold_transition(frames[idx], frames[idx + 1], hold_all_transitions, hold_name_patterns)
    )


def interpolate_frames_bitmapflow(
    frames: Sequence[FrameItem],
    source_fps: float,
    target_fps: float,
    hold_all_transitions: bool = False,
    hold_name_patterns: Sequence[str] = (),
) -> Tuple[List[FrameItem], float]:
    """Interpolate frames using external BitmapFlow executable, with flow fallback."""
    bitmapflow_exe = shutil.which("bitmapflow")
    if not bitmapflow_exe:
        bin_candidate = Path(__file__).resolve().parent.parent / "bin" / "bitmapflow.exe"
        if bin_candidate.exists():
            bitmapflow_exe = str(bin_candidate)
        else:
            bin_candidate_linux = Path(__file__).resolve().parent.parent / "bin" / "bitmapflow"
            if bin_candidate_linux.exists():
                bitmapflow_exe = str(bin_candidate_linux)

    if not bitmapflow_exe:
        print("[BitmapFlow] executable 'bitmapflow' not found in PATH or bin/ directory. Falling back to OpenCV Farneback flow...")
        return interpolate_frames_flow(frames, source_fps, target_fps, hold_all_transitions, hold_name_patterns)

    if len(frames) <= 1 or source_fps <= 0 or target_fps <= source_fps:
        return list(frames), source_fps

    factor = int(round(target_fps / source_fps))
    if factor <= 1:
        return list(frames), source_fps

    with tempfile.TemporaryDirectory() as tmp_in_dir, tempfile.TemporaryDirectory() as tmp_out_dir:
        for idx, item in enumerate(frames):
            item.image.save(os.path.join(tmp_in_dir, f"frame_{idx:05d}.png"))

        num_inbetweens = factor - 1
        cmd = [
            bitmapflow_exe,
            "-i", tmp_in_dir,
            "-o", tmp_out_dir,
            "-n", str(num_inbetweens)
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            out_files = sorted(Path(tmp_out_dir).glob("*.png"))
            if not out_files:
                raise RuntimeError("BitmapFlow produced no output files")

            out_frames = []
            for idx, out_file in enumerate(out_files):
                img = Image.open(out_file).convert("RGBA")
                out_frames.append(FrameItem(img, f"{frames[0].name}_bitmapflow_{idx:04d}", frames[0].source_index))
            return out_frames, target_fps
        except Exception as exc:
            print(f"[BitmapFlow] execution failed: {exc}. Falling back to OpenCV Farneback flow...")
            return interpolate_frames_flow(frames, source_fps, target_fps, hold_all_transitions, hold_name_patterns)


def _rife_executable() -> Optional[str]:
    for name in ("rife-ncnn-vulkan", "rife-ncnn-vulkan.exe", "rife"):
        found = shutil.which(name)
        if found:
            return found
    bin_dir = Path(__file__).resolve().parent.parent / "bin"
    for name in ("rife-ncnn-vulkan.exe", "rife-ncnn-vulkan", "rife.exe", "rife"):
        candidate = bin_dir / name
        if candidate.exists():
            return str(candidate)
    return None


def _nearest_alpha_frame(left: Image.Image, right: Image.Image, frac: float) -> Image.Image:
    source = left if frac < 0.5 else right
    return source.convert("RGBA").getchannel("A")


def _rife_midpoint(left: Image.Image, right: Image.Image, exe: str) -> Image.Image:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        left_path = tmp / "left.png"
        right_path = tmp / "right.png"
        out_path = tmp / "mid.png"
        left.convert("RGB").save(left_path)
        right.convert("RGB").save(right_path)
        cmd = [exe, "-0", str(left_path), "-1", str(right_path), "-o", str(out_path)]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
        rgb = Image.open(out_path).convert("RGBA")
        rgb.putalpha(_nearest_alpha_frame(left, right, 0.5))
        return rgb


def interpolate_frames_rife(
    frames: Sequence[FrameItem],
    source_fps: float,
    target_fps: float,
    hold_all_transitions: bool = False,
    hold_name_patterns: Sequence[str] = (),
) -> Tuple[List[FrameItem], float]:
    """Interpolate with optional RIFE midpoint generation, falling back to blend.

    The supported external path is ``rife-ncnn-vulkan``. It is treated as
    optional because most SpriteForge installs will not have it locally.
    Non-midpoint timing still uses alpha-aware blending so arbitrary target FPS
    remains deterministic.
    """
    exe = _rife_executable()
    if not exe:
        print("[RIFE] executable not found. Falling back to alpha-aware blend interpolation...")
        return interpolate_frames_blend(frames, source_fps, target_fps, hold_all_transitions, hold_name_patterns)
    if len(frames) <= 1 or source_fps <= 0 or target_fps <= source_fps:
        return list(frames), source_fps

    total = interpolated_count(len(frames), source_fps, target_fps)
    out: List[FrameItem] = []
    midpoint_cache = {}
    for out_idx in range(total):
        t = out_idx / target_fps
        source_pos = min(t * source_fps, len(frames) - 1)
        left = int(source_pos)
        right = min(left + 1, len(frames) - 1)
        frac = source_pos - left
        if right == left or frac <= 1e-6:
            img = frames[left].image.copy()
        elif _should_hold_transition(frames[left], frames[right], hold_all_transitions, hold_name_patterns):
            chosen = left if frac < 0.5 else right
            img = frames[chosen].image.copy()
        elif abs(frac - 0.5) <= 1e-6:
            key = (left, right)
            if key not in midpoint_cache:
                try:
                    midpoint_cache[key] = _rife_midpoint(frames[left].image, frames[right].image, exe)
                except Exception as exc:
                    print(f"[RIFE] midpoint generation failed: {exc}. Falling back to blend for this transition...")
                    midpoint_cache[key] = Image.blend(frames[left].image.convert("RGBA"), frames[right].image.convert("RGBA"), frac)
            img = midpoint_cache[key].copy()
        else:
            img = Image.blend(frames[left].image.convert("RGBA"), frames[right].image.convert("RGBA"), frac)
        out.append(FrameItem(img, f"{frames[left].name}_rife_{out_idx:04d}", frames[left].source_index))
    return out, target_fps


def interpolate_frames(
    frames: Sequence[FrameItem],
    source_fps: float,
    target_fps: Optional[float],
    engine: str = "blend",
    hold_all_transitions: bool = False,
    hold_name_patterns: Optional[Sequence[str]] = None,
) -> Tuple[List[FrameItem], float, dict]:
    if target_fps is None or target_fps <= 0 or target_fps <= source_fps:
        return list(frames), source_fps, {"enabled": False}

    patterns = _normalized_patterns(hold_name_patterns)
    if engine == "blend":
        out, fps = interpolate_frames_blend(frames, source_fps, target_fps, hold_all_transitions, patterns)
    elif engine == "flow":
        out, fps = interpolate_frames_flow(frames, source_fps, target_fps, hold_all_transitions, patterns)
    elif engine == "bitmapflow":
        out, fps = interpolate_frames_bitmapflow(frames, source_fps, target_fps, hold_all_transitions, patterns)
    elif engine == "rife":
        out, fps = interpolate_frames_rife(frames, source_fps, target_fps, hold_all_transitions, patterns)
    else:
        raise RuntimeError(f"Unknown interpolation engine: {engine}")

    held = held_transition_count(frames, hold_all_transitions, patterns)
    return out, fps, {
        "enabled": True,
        "engine": engine,
        "source_fps": source_fps,
        "target_fps": target_fps,
        "source_frame_count": len(frames),
        "frame_count": len(out),
        "held_transitions": held,
        "hold_all_transitions": bool(hold_all_transitions),
        "hold_name_patterns": list(patterns),
    }
