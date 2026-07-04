#!/usr/bin/env python3
"""Tests for Round 3 features: Pixel Snapping and PBR Maps (Specular/AO)."""
from __future__ import annotations

import pytest
import numpy as np
from PIL import Image

from services.sprite_pixel_snapper import SpritePixelSnapper
from services.sprite_normal_map import SpriteNormalMapService
from services.sprite_video_loader import FrameItem
from services.sprite_processing_pipeline import process_common

def test_pixel_snapping():
    # Create an image with a solid center and a fuzzy/anti-aliased edge
    # Size 8x8. We'll use scale=2.
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    
    # Draw a 2x2 solid red block in the center (coordinates 2,2 to 3,3)
    for y in range(2, 4):
        for x in range(2, 4):
            img.putpixel((x, y), (255, 0, 0, 255))
            
    # Draw some fuzzy/semi-transparent pixels at coordinates 4,4 (alpha=50) and 5,5 (alpha=200)
    # The block at (4,4) to (5,5) will have average alpha: (50 + 200 + 0 + 0) / 4 = 62.5
    # Since 62.5 < 128 (default threshold), this block should be snapped to transparent.
    img.putpixel((4, 4), (255, 0, 0, 50))
    img.putpixel((5, 5), (255, 0, 0, 200))
    
    # Draw another block at (6,6) to (7,7) with higher average alpha: (200 + 200 + 200 + 0) / 4 = 150
    # Since 150 >= 128, this block should be snapped to solid opaque.
    img.putpixel((6, 6), (255, 0, 0, 200))
    img.putpixel((6, 7), (255, 0, 0, 200))
    img.putpixel((7, 6), (255, 0, 0, 200))
    
    snapped = SpritePixelSnapper.snap_pixels_to_grid(img, scale=2, alpha_threshold=128)
    
    # Verify dimensions
    assert snapped.size == (8, 8)
    
    # The center block (2,2 to 3,3) should remain solid red
    for y in range(2, 4):
        for x in range(2, 4):
            assert snapped.getpixel((x, y)) == (255, 0, 0, 255)
            
    # The fuzzy block (4,4 to 5,5) should be completely transparent
    for y in range(4, 6):
        for x in range(4, 6):
            assert snapped.getpixel((x, y)) == (0, 0, 0, 0)
            
    # The high-alpha block (6,6 to 7,7) should be fully opaque red
    for y in range(6, 8):
        for x in range(6, 8):
            assert snapped.getpixel((x, y)) == (255, 0, 0, 255)

def test_pbr_specular_ao_maps():
    # Create a simple test image
    img = Image.new("RGBA", (16, 16), (128, 128, 128, 255))
    
    # Call generate_maps from SpriteNormalMapService
    normal_img, specular_img, ao_img = SpriteNormalMapService.generate_maps(img)
    
    assert normal_img.size == (16, 16)
    assert specular_img.size == (16, 16)
    assert ao_img.size == (16, 16)
    
    # Assert alpha channel is preserved
    assert normal_img.getpixel((0, 0))[3] == 255
    assert specular_img.getpixel((0, 0))[3] == 255
    assert ao_img.getpixel((0, 0))[3] == 255
