import sys
from pathlib import Path
import pytest
from PIL import Image
import numpy as np

# Add app directory to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from services.sprite_service import SpriteService

def test_chroma_keying():
    # Create a solid green image (chroma key)
    # Green = (0, 255, 0)
    img = Image.new("RGBA", (100, 100), (0, 255, 0, 255))
    
    # Apply chroma key with "auto" (should detect green corner)
    keyed = SpriteService.apply_chroma_key(img, "auto", tolerance=30, feather=0)
    arr = np.asarray(keyed)
    # Alpha should be 0 for all pixels
    assert np.all(arr[:, :, 3] == 0)

    # Keying with explicit color
    keyed_explicit = SpriteService.apply_chroma_key(img, (0, 255, 0), tolerance=30, feather=0)
    arr_explicit = np.asarray(keyed_explicit)
    assert np.all(arr_explicit[:, :, 3] == 0)

    # Keying with different color should retain alpha
    keyed_diff = SpriteService.apply_chroma_key(img, (255, 0, 0), tolerance=30, feather=0)
    arr_diff = np.asarray(keyed_diff)
    assert np.all(arr_diff[:, :, 3] == 255)

def test_auto_chroma_key_ignores_letterbox_bars():
    img = Image.new("RGBA", (120, 80), (0, 0, 0, 255))
    pixels = np.asarray(img).copy()
    pixels[20:80, :] = [0, 220, 20, 255]
    pixels[36:58, 48:72] = [210, 40, 180, 255]
    img = Image.fromarray(pixels, mode="RGBA")

    keyed = SpriteService.apply_chroma_key(img, "auto", tolerance=45, feather=0)
    arr = np.asarray(keyed)

    assert arr[5, 10, 3] == 0
    assert arr[30, 10, 3] == 0
    assert arr[45, 60, 3] == 255

def test_auto_chroma_key_prefers_green_screen_over_yellow_floor():
    img = Image.new("RGBA", (160, 100), (25, 220, 25, 255))
    pixels = np.asarray(img).copy()
    pixels[72:100, :] = [222, 205, 104, 255]
    pixels[34:76, 58:102] = [35, 50, 150, 255]
    pixels[76:96, 54:76] = [145, 25, 18, 255]
    pixels[76:96, 84:106] = [145, 25, 18, 255]
    img = Image.fromarray(pixels, mode="RGBA")

    assert SpriteService.guess_key_color_from_corners(img)[1] > 180
    keyed = SpriteService.apply_chroma_key(img, "auto", tolerance=45, feather=0)
    arr = np.asarray(keyed)

    assert arr[10, 10, 3] == 0
    assert arr[88, 64, 3] == 255
    assert arr[88, 94, 3] == 255

def test_auto_chroma_key_removes_detached_floor_dashes():
    img = Image.new("RGBA", (180, 120), (25, 220, 25, 255))
    pixels = np.asarray(img).copy()
    pixels[42:88, 70:110] = [35, 50, 150, 255]
    pixels[88:112, 66:84] = [145, 25, 18, 255]
    pixels[88:112, 96:114] = [145, 25, 18, 255]
    for x in range(8, 168, 24):
        pixels[96:99, x : x + 10] = [146, 212, 72, 255]
    img = Image.fromarray(pixels, mode="RGBA")

    keyed = SpriteService.apply_chroma_key(img, "auto", tolerance=45, feather=0)
    arr = np.asarray(keyed)

    assert arr[97, 12, 3] == 0
    assert arr[100, 74, 3] == 255
    assert arr[100, 104, 3] == 255

def test_alpha_bbox():
    # Transparent image
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    # Draw a 20x20 solid square at (10, 20) to (29, 39)
    pixels = np.asarray(img).copy()
    pixels[20:40, 10:30] = [255, 255, 255, 255]
    img_with_box = Image.fromarray(pixels, mode="RGBA")

    bbox = SpriteService.alpha_bbox(img_with_box, threshold=8)
    assert bbox is not None
    l, t, r, b = bbox
    assert l == 10
    assert t == 20
    assert r == 30
    assert b == 40

def test_smooth_sequence():
    coords = [10.0, 10.0, 50.0, 10.0, 10.0]  # outlier 50.0 in the middle
    smoothed = SpriteService.smooth_sequence(coords, window_size=5)
    # The middle element (50.0) should be smoothed out by rolling median to 10.0
    assert smoothed[2] == 10.0

def test_blend_loop_seam():
    # Simple list of images with different colors to test blending
    frames = [Image.new("RGBA", (10, 10), (0, 0, 0, 255)) for _ in range(10)]
    frames[0] = Image.new("RGBA", (10, 10), (255, 0, 0, 255)) # Red
    frames[9] = Image.new("RGBA", (10, 10), (0, 0, 255, 255)) # Blue
    blended = SpriteService.blend_loop_seam(frames, blend_frames=2)
    assert len(blended) == 10
    # The last frame (index 9) should now be blended with the first frame (index 0), so it won't be pure blue
    assert blended[9] != frames[9]

def test_solidify_transparent_rgb():
    img = Image.new("RGBA", (10, 10), (255, 0, 0, 0))  # fully transparent red
    solid = SpriteService.solidify_transparent_rgb(img, radius=1)
    arr = np.asarray(solid)
    # Alpha remains transparent, but colors are modified by solidify
    assert np.all(arr[:, :, 3] == 0)
