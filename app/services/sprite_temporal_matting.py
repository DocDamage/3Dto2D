#!/usr/bin/env python3
"""Native temporal alpha stabilization for sprite frame sequences."""
from __future__ import annotations

from typing import List, Sequence

import numpy as np
from PIL import Image

from services.sprite_video_loader import FrameItem


def stabilize_temporal_alpha(
    frames: Sequence[FrameItem],
    strength: float = 0.55,
    motion_threshold: float = 42.0,
) -> List[FrameItem]:
    """Reduce alpha flicker across a frame sequence with motion-aware smoothing."""
    if len(frames) <= 1:
        return list(frames)

    strength = max(0.0, min(0.95, float(strength)))
    motion_threshold = max(1.0, float(motion_threshold))
    if strength <= 0:
        return list(frames)

    arrays = [np.asarray(item.image.convert("RGBA")).astype(np.float32) for item in frames]
    smoothed = [arr.copy() for arr in arrays]

    prev_alpha = arrays[0][:, :, 3].copy()
    prev_rgb = arrays[0][:, :, :3].copy()
    for idx in range(1, len(arrays)):
        arr = arrays[idx]
        if arr.shape != arrays[idx - 1].shape:
            prev_alpha = arr[:, :, 3].copy()
            prev_rgb = arr[:, :, :3].copy()
            continue
        motion = np.mean(np.abs(arr[:, :, :3] - prev_rgb), axis=2)
        stable_weight = np.clip(1.0 - (motion / motion_threshold), 0.0, 1.0) * strength
        alpha = arr[:, :, 3]
        blended = alpha * (1.0 - stable_weight) + prev_alpha * stable_weight
        smoothed[idx][:, :, 3] = blended
        prev_alpha = blended
        prev_rgb = arr[:, :, :3]

    next_alpha = arrays[-1][:, :, 3].copy()
    next_rgb = arrays[-1][:, :, :3].copy()
    for idx in range(len(arrays) - 2, -1, -1):
        arr = arrays[idx]
        if arr.shape != arrays[idx + 1].shape:
            next_alpha = arr[:, :, 3].copy()
            next_rgb = arr[:, :, :3].copy()
            continue
        motion = np.mean(np.abs(arr[:, :, :3] - next_rgb), axis=2)
        stable_weight = np.clip(1.0 - (motion / motion_threshold), 0.0, 1.0) * (strength * 0.5)
        alpha = smoothed[idx][:, :, 3]
        blended = alpha * (1.0 - stable_weight) + next_alpha * stable_weight
        smoothed[idx][:, :, 3] = blended
        next_alpha = blended
        next_rgb = arr[:, :, :3]

    out: List[FrameItem] = []
    for item, arr in zip(frames, smoothed):
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGBA")
        out.append(FrameItem(img, item.name, item.source_index))
    return out
