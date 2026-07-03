#!/usr/bin/env python3
"""Native frame interpolation helpers for sprite animations."""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

from PIL import Image

try:
    import cv2
except Exception:
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
