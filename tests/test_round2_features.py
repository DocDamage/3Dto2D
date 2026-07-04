#!/usr/bin/env python3
"""Tests for Round 2 features: MaxRects bin packing, SAM2 segmenter with GrabCut fallback, and BitmapFlow interpolation."""
from __future__ import annotations

import sys
from pathlib import Path
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from services.sprite_bin_packer import SpriteBinPackerService
from services.sprite_sam2_service import SpriteSAM2Service
from services.sprite_interpolation import interpolate_frames
from services.sprite_video_loader import FrameItem

def test_maxrects_packing():
    # Define a list of rectangles with mixed sizes to pack: (w, h, metadata)
    rectangles = [
        (128, 64, "rect1"),
        (64, 128, "rect2"),
        (256, 256, "rect3"),
        (32, 32, "rect4"),
    ]
    
    # 1. Run MaxRects packing
    res = SpriteBinPackerService.pack(rectangles, max_width=512, pack_mode="maxrects", spacing=2, margin=4)
    
    assert "width" in res
    assert "height" in res
    assert "positions" in res
    assert len(res["positions"]) == len(rectangles)
    
    # Verify that packed positions do not overlap and fit within bounds
    # Note: spacing is 2, margin is 4
    for (x1, y1), meta1 in res["positions"]:
        w1, h1 = next(r[:2] for r in rectangles if r[2] == meta1)
        # Check within bounds
        assert x1 >= 4
        assert y1 >= 4
        assert x1 + w1 <= res["width"] - 4
        assert y1 + h1 <= res["height"] - 4
        
        # Check against all other rectangles for overlap
        for (x2, y2), meta2 in res["positions"]:
            if meta1 == meta2:
                continue
            w2, h2 = next(r[:2] for r in rectangles if r[2] == meta2)
            # Overlap check
            overlap_x = not (x1 + w1 + 2 <= x2 or x2 + w2 + 2 <= x1)
            overlap_y = not (y1 + h1 + 2 <= y2 or y2 + h2 + 2 <= y1)
            assert not (overlap_x and overlap_y), f"Overlapping: {meta1} and {meta2}"

def test_sam2_grabcut_fallback():
    # Create dummy frames with a subject (a red circle) on a green background
    frames = []
    for i in range(3):
        img = Image.new("RGBA", (100, 100), (0, 255, 0, 255)) # Green background
        # Draw a red circle (subject) that moves slightly frame-to-frame
        for y in range(100):
            for x in range(100):
                dist = (x - (50 + i * 5)) ** 2 + (y - 50) ** 2
                if dist < 15 ** 2: # Radius 15 circle
                    img.putpixel((x, y), (255, 0, 0, 255)) # Red subject
        frames.append(FrameItem(img, f"frame_{i}", i))
        
    # Define click prompts to segment the red circle: (x, y, label)
    # Target center of circle on frame 0: (50, 50, 1) (foreground)
    # Background click: (10, 10, 0) (background)
    click_prompts = {
        "circle": [(50, 50, 1), (10, 10, 0)]
    }
    
    # Run segmentation using GrabCut fallback (which automatically runs if SAM2 is not installed)
    segmented = SpriteSAM2Service.segment_parts(frames, click_prompts)
    
    assert "circle" in segmented
    assert len(segmented["circle"]) == len(frames)
    
    # Verify first frame segmented result has the circle but the green background is transparent
    first_segmented = segmented["circle"][0].image
    # Pixel at center (circle) should be preserved
    r, g, b, a = first_segmented.getpixel((50, 50))
    assert a > 0
    assert r > 200
    
    try:
        import cv2
    except ImportError:
        cv2 = None

    if cv2 is not None:
        r2, g2, b2, a2 = first_segmented.getpixel((10, 10))
        assert a2 == 0

def test_bitmapflow_interpolation_fallback():
    # Create a simple frame sequence
    frames = []
    for i in range(2):
        img = Image.new("RGBA", (32, 32), (100, 100, 100, 255))
        frames.append(FrameItem(img, f"f_{i}", i))
        
    # Request interpolation using bitmapflow engine.
    # Since bitmapflow executable is not present in typical test environments,
    # it should gracefully fallback to the native flow engine or blending.
    out, fps, info = interpolate_frames(
        frames,
        source_fps=10.0,
        target_fps=20.0,
        engine="bitmapflow"
    )
    
    # Should double the frame count (factor = 2)
    assert len(out) == 3
    assert fps == 20.0
    assert info["enabled"] is True
