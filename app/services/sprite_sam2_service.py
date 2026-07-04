#!/usr/bin/env python3
"""Segment Anything Model 2 (SAM2) service with robust OpenCV GrabCut fallback.

Supports interactive part decomposition (e.g., separating body, weapon, hair)
using click prompts, and propagates the masks across the frame sequence.
"""
from __future__ import annotations

import os
import importlib.util
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
from PIL import Image

try:
    import cv2
except Exception as exc:
    logging.getLogger(__name__).debug("OpenCV unavailable for SAM2 fallback segmentation: %s", exc)
    cv2 = None

from services.sprite_video_loader import FrameItem
logger = logging.getLogger(__name__)

class SpriteSAM2Service:
    @classmethod
    def segment_parts(
        cls,
        frames: List[FrameItem],
        click_prompts: Dict[str, List[Tuple[int, int, int]]],
        model_path: Optional[str] = None
    ) -> Dict[str, List[FrameItem]]:
        """Segments character parts across frames using click prompts.

        Args:
            frames: List of FrameItems to segment.
            click_prompts: Dict mapping part name (e.g. 'weapon') to list of (x, y, label) clicks,
                          where label is 1 for foreground and 0 for background.
            model_path: Path to SAM2 weights (optional).

        Returns:
            Dict mapping part name to a list of segmented FrameItems.
        """
        if not frames:
            return {}

        results: Dict[str, List[FrameItem]] = {}
        for part_name, clicks in click_prompts.items():
            results[part_name] = cls.segment_single_part(frames, clicks, model_path, part_name)

        return results

    @classmethod
    def segment_single_part(
        cls,
        frames: List[FrameItem],
        clicks: List[Tuple[int, int, int]],
        model_path: Optional[str],
        part_name: str
    ) -> List[FrameItem]:
        """Segments a single part across all frames."""
        try:
            # Try to load and run SAM2 if installed
            return cls._run_sam2(frames, clicks, model_path, part_name)
        except Exception as exc:
            # Friendly log and fallback to OpenCV GrabCut
            print(f"[SAM2] Could not load or run SAM2 model ({exc}). Falling back to OpenCV GrabCut...")
            return cls._run_grabcut_fallback(frames, clicks, part_name)

    @classmethod
    def _run_sam2(
        cls,
        frames: List[FrameItem],
        clicks: List[Tuple[int, int, int]],
        model_path: Optional[str],
        part_name: str
    ) -> List[FrameItem]:
        """Runs the actual Segment Anything Model 2 video predictor."""
        # Avoid importing heavy native runtimes unless SAM2 itself is present.
        if importlib.util.find_spec("sam2") is None:
            raise RuntimeError("SAM2 package is not installed")

        # Import dynamically so the OpenCV fallback remains lightweight.
        import torch
        from sam2.build_sam import build_sam2_video_predictor

        # Locate model weights
        if not model_path:
            model_path = os.getenv("SAM2_MODEL_PATH", "sam2_hiera_small.pt")
        config_name = "sam2_hiera_s.yaml"

        device = "cuda" if torch.cuda.is_available() else "cpu"
        predictor = build_sam2_video_predictor(config_name, model_path, device=device)

        # Write temporary frames for SAM2 video predictor
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            for idx, item in enumerate(frames):
                item.image.save(tmp_path / f"frame_{idx:05d}.jpg", "JPEG")

            state = predictor.init_state(video_path=str(tmp_path))

            # Add click prompts on frame 0
            for click_idx, (x, y, label) in enumerate(clicks):
                predictor.add_new_points(
                    inference_state=state,
                    frame_idx=0,
                    obj_id=1,
                    points=np.array([[x, y]], dtype=np.float32),
                    labels=np.array([label], dtype=np.int32)
                )

            # Propagate masks across the video
            segmented_frames: List[FrameItem] = []
            for frame_idx, out_frame_idx, out_mask_logits in predictor.propagate_in_video(state):
                mask = (out_mask_logits[0] > 0.0).cpu().numpy().astype(np.uint8) * 255
                mask_img = Image.fromarray(mask, mode="L")
                
                # Apply mask to the original frame
                orig = frames[out_frame_idx]
                masked_img = Image.new("RGBA", orig.image.size, (0, 0, 0, 0))
                masked_img.paste(orig.image, (0, 0), mask_img)
                segmented_frames.append(FrameItem(masked_img, f"{orig.name}_{part_name}", orig.source_index))

            return segmented_frames

    @classmethod
    def _run_grabcut_fallback(
        cls,
        frames: List[FrameItem],
        clicks: List[Tuple[int, int, int]],
        part_name: str
    ) -> List[FrameItem]:
        """Fallback GrabCut segmentation that propagates mask priors frame-to-frame."""
        if cv2 is None:
            # Ultimate fallback if OpenCV is completely missing: just return original frames
            print("[WARN] OpenCV (cv2) is not available. SAM2 and GrabCut fallbacks skipped.")
            return list(frames)

        out_frames: List[FrameItem] = []
        prev_mask: Optional[np.ndarray] = None

        for idx, item in enumerate(frames):
            arr = np.asarray(item.image.convert("RGBA"))
            rgb = np.ascontiguousarray(arr[:, :, :3], dtype=np.uint8)
            alpha = np.ascontiguousarray(arr[:, :, 3], dtype=np.uint8)

            h, w = alpha.shape
            gc_mask = np.zeros((h, w), dtype=np.uint8)

            # 1. Background is definitely 0 where alpha is 0
            gc_mask[alpha <= 10] = cv2.GC_BGD
            gc_mask[alpha > 10] = cv2.GC_PR_BGD

            # 2. Add click prompts (only on frame 0 or seed)
            if idx == 0:
                for x, y, label in clicks:
                    if 0 <= x < w and 0 <= y < h:
                        if label == 1:
                            cv2.circle(gc_mask, (x, y), 5, cv2.GC_FGD, -1)
                        else:
                            cv2.circle(gc_mask, (x, y), 5, cv2.GC_BGD, -1)
            else:
                # Propagate from previous frame's mask as a seed
                if prev_mask is not None:
                    # Probable foreground is where previous frame was foreground
                    gc_mask[prev_mask > 0] = cv2.GC_PR_FGD

            # Run GrabCut
            bgdModel = np.zeros((1, 65), np.float64)
            fgdModel = np.zeros((1, 65), np.float64)

            # Check if we have at least one foreground pixel to start GrabCut
            if (gc_mask == cv2.GC_FGD).any() or (gc_mask == cv2.GC_PR_FGD).any():
                try:
                    cv2.grabCut(rgb, gc_mask, None, bgdModel, fgdModel, 3, cv2.GC_INIT_WITH_MASK)
                    # Create binary mask: pixels that are definitely or probably foreground
                    mask = np.where((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
                except Exception as exc:
                    logger.debug("GrabCut refinement failed for frame %s; using alpha fallback mask: %s", frame.name, exc)
                    mask = (alpha > 10).astype(np.uint8) * 255
            else:
                mask = (alpha > 10).astype(np.uint8) * 255

            prev_mask = mask

            # Extract part and save as FrameItem
            mask_img = Image.fromarray(mask, mode="L")
            masked_img = Image.new("RGBA", item.image.size, (0, 0, 0, 0))
            masked_img.paste(item.image, (0, 0), mask_img)
            out_frames.append(FrameItem(masked_img, f"{item.name}_{part_name}", item.source_index))

        return out_frames
