from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
from PIL import Image

from services.sprite_video_loader import FrameItem


def _window_indices(index: int, count: int, radius: int) -> range:
    return range(max(0, index - radius), min(count, index + radius + 1))


def _match_rgb_histogram(source: np.ndarray, reference: np.ndarray, mask: np.ndarray) -> np.ndarray:
    out = source.copy()
    if not mask.any():
        return out
    for channel in range(3):
        src = source[:, :, channel][mask].astype(np.float32)
        ref = reference[:, :, channel][mask].astype(np.float32)
        if len(src) < 2 or len(ref) < 2:
            continue
        src_mean = float(src.mean())
        ref_mean = float(ref.mean())
        src_std = float(src.std()) or 1.0
        ref_std = float(ref.std()) or 1.0
        adjusted = ((source[:, :, channel].astype(np.float32) - src_mean) / src_std) * ref_std + ref_mean
        out[:, :, channel] = np.clip(adjusted, 0, 255).astype(np.uint8)
    return out


def stabilize_temporal_coherence(
    frames: Sequence[FrameItem],
    radius: int = 1,
    color_strength: float = 0.35,
    alpha_strength: float = 0.55,
    alpha_threshold: int = 8,
    histogram_match: bool = True,
) -> Tuple[List[FrameItem], Dict[str, Any]]:
    """Reduce color flicker and alpha-edge jitter across similarly sized frames."""
    if len(frames) <= 1:
        return list(frames), {"enabled": False, "reason": "not_enough_frames"}

    radius = max(1, int(radius))
    color_strength = max(0.0, min(0.95, float(color_strength)))
    alpha_strength = max(0.0, min(0.95, float(alpha_strength)))
    arrays = [np.asarray(item.image.convert("RGBA")).copy() for item in frames]
    if len({arr.shape for arr in arrays}) != 1:
        return list(frames), {"enabled": False, "reason": "mixed_frame_sizes"}

    reference = arrays[0]
    matched = []
    for arr in arrays:
        visible = (arr[:, :, 3] > alpha_threshold) & (reference[:, :, 3] > alpha_threshold)
        matched.append(_match_rgb_histogram(arr, reference, visible) if histogram_match else arr.copy())

    out_arrays: List[np.ndarray] = []
    for idx, arr in enumerate(matched):
        neighbors = np.stack([matched[j] for j in _window_indices(idx, len(matched), radius)], axis=0)
        median = np.median(neighbors, axis=0)
        result = arr.astype(np.float32).copy()
        visible = arr[:, :, 3] > alpha_threshold
        edge = (median[:, :, 3] > alpha_threshold) | visible
        if color_strength > 0:
            result[:, :, :3][visible] = (
                result[:, :, :3][visible] * (1.0 - color_strength)
                + median[:, :, :3][visible] * color_strength
            )
        if alpha_strength > 0:
            result[:, :, 3][edge] = (
                result[:, :, 3][edge] * (1.0 - alpha_strength)
                + median[:, :, 3][edge] * alpha_strength
            )
        result[:, :, 3] = np.where(result[:, :, 3] > 240, 255, np.where(result[:, :, 3] < alpha_threshold, 0, result[:, :, 3]))
        out_arrays.append(np.clip(result, 0, 255).astype(np.uint8))

    output = [
        FrameItem(Image.fromarray(arr, mode="RGBA"), item.name, item.source_index)
        for item, arr in zip(frames, out_arrays)
    ]
    return output, {
        "enabled": True,
        "radius": radius,
        "color_strength": color_strength,
        "alpha_strength": alpha_strength,
        "alpha_threshold": alpha_threshold,
        "histogram_match": bool(histogram_match),
    }
