import sys
import pytest
import numpy as np
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from services.sprite_normal_map import SpriteNormalMapService
from services.sprite_bin_packer import SpriteBinPackerService
from services.sprite_chroma_alpha import BIREFNET_MATTING_MODEL_ID, try_birefnet, apply_pixeloe_pixelization
from services.install_commands import PIXEL_ART_CUSTOM_NODES


def test_normal_map_generation():
    # Create a 64x64 RGBA dummy image with a white circle on transparent background
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for x in range(16, 48):
        for y in range(16, 48):
            if (x - 32)**2 + (y - 32)**2 < 256:
                img.putpixel((x, y), (255, 255, 255, 255))

    normal_img, specular_img, ao_img = SpriteNormalMapService.generate_maps(img)

    assert normal_img.size == (64, 64)
    assert specular_img.size == (64, 64)
    assert ao_img.size == (64, 64)

    # Check that transparent pixels remain transparent
    assert normal_img.getpixel((0, 0))[3] == 0
    assert specular_img.getpixel((0, 0))[3] == 0
    assert ao_img.getpixel((0, 0))[3] == 0

    # Check normal vector mapping range (e.g. center normal points straight up: RGB ~ 128, 128, 255)
    center_color = normal_img.getpixel((32, 32))
    assert center_color[3] == 255
    # Center should be close to flat surface normal (0, 0, 1) -> (128, 128, 255)
    assert 120 <= center_color[0] <= 136
    assert 120 <= center_color[1] <= 136
    assert 200 <= center_color[2] <= 255


def test_distance_transform_uses_interior_alpha_volume():
    alpha = Image.new("L", (9, 9), 0)
    for x in range(2, 7):
        for y in range(2, 7):
            alpha.putpixel((x, y), 255)

    dist = SpriteNormalMapService.compute_distance_transform(np.asarray(alpha))

    assert dist.shape == (9, 9)
    assert dist[0, 0] == 0.0
    assert dist[4, 4] > dist[2, 2]
    assert dist[4, 4] == pytest.approx(1.0)


def test_bin_packer():
    # Pack three rectangles
    rects = [
        (32, 32, "rect1"),
        (64, 16, "rect2"),
        (16, 64, "rect3"),
    ]
    packed = SpriteBinPackerService.pack(rects, max_width=512)

    assert packed["width"] > 0
    assert packed["height"] > 0
    assert len(packed["positions"]) == 3

    # Check coordinates and bounds
    for (x, y), meta in packed["positions"]:
        assert x >= 0
        assert y >= 0
        if meta == "rect1":
            assert x + 32 <= packed["width"]
            assert y + 32 <= packed["height"]


def test_pixeloe_fallback():
    # Make a dummy 64x64 image
    img = Image.new("RGBA", (64, 64), (255, 0, 0, 255))
    pixelized = apply_pixeloe_pixelization(img, pixel_size=4)
    assert pixelized.size == (64, 64)


def test_birefnet_failure_handling(monkeypatch):
    # Test that calling birefnet raises an error if packages aren't installed or mock imports
    img = Image.new("RGBA", (64, 64), (255, 255, 255, 255))
    
    # Force import error
    monkeypatch.setattr("sys.modules", {**sys.modules, "transformers": None})
    with pytest.raises(RuntimeError, match="BiRefNet option requires"):
        try_birefnet(img)


def test_birefnet_defaults_to_matting_checkpoint():
    assert BIREFNET_MATTING_MODEL_ID == "ZhengPeng7/BiRefNet-matting"


def test_pixel_art_comfy_nodes_are_in_auto_install_bundle():
    node_urls = {url for url, _name in PIXEL_ART_CUSTOM_NODES}

    assert "https://github.com/x0x0b/ComfyUI-spritefusion-pixel-snapper.git" in node_urls
    assert "https://github.com/dimtoneff/ComfyUI-PixelArt-Detector.git" in node_urls
    assert "https://github.com/ComfyNodePRs/PR-ComfyUI-PixelArt-Unfaker.git" in node_urls
