import sys
import pytest
import numpy as np
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from spriteforge import build_parser
from services.sprite_video_loader import FrameItem
from services.sprite_processing_pipeline import process_common
from services.sprite_interpolation import interpolate_frames, interpolated_count
from services.sprite_temporal_matting import stabilize_temporal_alpha
from services.sprite_normal_map import SpriteNormalMapService
from services.sprite_bin_packer import SpriteBinPackerService
from services.sprite_alpha_tools import extract_dual_background_alpha, refine_alpha_edges
from services.sprite_chroma_alpha import (
    BIREFNET_MATTING_MODEL_ID,
    DEPTH_ANYTHING_MODEL_ID,
    apply_pixel_art_background_removal,
    apply_native_pixel_cleanup,
    fit_native_pixel_palette,
    try_birefnet,
    try_depth_anything,
    apply_pixeloe_pixelization,
)
from services.install_commands import WAN_VIDEO_CUSTOM_NODES


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


def test_native_depth_normal_engine_builds_distinct_heightmap():
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    for y in range(2, 6):
        for x in range(2, 6):
            shade = 60 + y * 25 + x * 6
            img.putpixel((x, y), (shade, shade, shade, 255))

    height = SpriteNormalMapService.build_heightmap(img, engine="height")
    depth = SpriteNormalMapService.build_heightmap(img, engine="native-depth")
    normal_img, _specular_img, _ao_img = SpriteNormalMapService.generate_maps(img, engine="native-depth")

    assert depth.shape == height.shape
    assert float(np.max(depth)) <= 1.0
    assert float(np.max(depth)) > float(np.min(depth))
    assert not np.allclose(height, depth)
    assert normal_img.size == img.size


def test_native_height_map_preserves_alpha_and_depth_variation():
    img = Image.new("RGBA", (6, 6), (0, 0, 0, 0))
    for y in range(1, 5):
        for x in range(1, 5):
            img.putpixel((x, y), (40 + x * 20, 40 + y * 20, 80, 255))

    height = SpriteNormalMapService.generate_height_map(img, engine="native-depth")

    assert height.size == img.size
    assert height.getpixel((0, 0))[3] == 0
    values = [height.getpixel((x, y))[0] for y in range(1, 5) for x in range(1, 5)]
    assert max(values) > min(values)


def test_pipeline_writes_native_height_sheet_when_generating_maps(tmp_path):
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    for y in range(2, 6):
        for x in range(2, 6):
            img.putpixel((x, y), (80 + x * 8, 70 + y * 10, 120, 255))

    process_common(
        frames=[FrameItem(img, "frame", 0)],
        output=tmp_path,
        fps=12.0,
        cell_size=(8, 8),
        key_color=None,
        key_tolerance=45.0,
        key_feather=20.0,
        rembg=False,
        crop_mode="none",
        pad=0,
        alpha_threshold=8,
        columns=1,
        animation_name="height_test",
        preview_gif=False,
        save_processed_frames=True,
        anchor="center",
        ground_margin=0,
        spacing=0,
        margin=0,
        solidify=0,
        outline_width=0,
        outline_color=(0, 0, 0, 255),
        power_of_two=False,
        loop_mode="none",
        drop_last=False,
        drop_loop_duplicate=False,
        reverse=False,
        flip_x=False,
        flip_y=False,
        report=False,
        generate_normal_maps=True,
        normal_map_engine="native-depth",
    )

    assert (tmp_path / "sheet_normal.png").exists()
    assert (tmp_path / "sheet_specular.png").exists()
    assert (tmp_path / "sheet_ao.png").exists()
    assert (tmp_path / "sheet_height.png").exists()
    assert (tmp_path / "frames_height" / "frame_0000.png").exists()


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


def test_depth_anything_defaults_to_small_checkpoint():
    assert DEPTH_ANYTHING_MODEL_ID == "LiheYoung/depth-anything-small-hf"


def test_depth_anything_failure_handling(monkeypatch):
    img = Image.new("RGBA", (64, 64), (255, 255, 255, 255))
    monkeypatch.setattr("sys.modules", {**sys.modules, "transformers": None})
    with pytest.raises(RuntimeError, match="depth-anything matting option requires"):
        try_depth_anything(img)


def test_pipeline_birefnet_falls_back_to_native_chroma(monkeypatch, tmp_path):
    from services import sprite_processing_pipeline as spp

    def _raise(_img):
        raise RuntimeError("missing optional birefnet deps")

    monkeypatch.setattr(spp, "try_birefnet", _raise)

    img = Image.new("RGBA", (32, 32), (0, 255, 0, 255))
    for x in range(10, 22):
        for y in range(8, 26):
            img.putpixel((x, y), (220, 20, 20, 255))

    result = process_common(
        frames=[FrameItem(img, "frame_0", 0)],
        output=tmp_path,
        fps=12.0,
        cell_size=(32, 32),
        key_color=None,
        key_tolerance=30.0,
        key_feather=16.0,
        rembg=False,
        crop_mode="none",
        pad=0,
        alpha_threshold=8,
        columns=1,
        animation_name="fallback_test",
        preview_gif=False,
        save_processed_frames=True,
        anchor="center",
        ground_margin=0,
        spacing=0,
        margin=0,
        solidify=0,
        outline_width=0,
        outline_color=(0, 0, 0, 255),
        power_of_two=False,
        loop_mode="normal",
        drop_last=False,
        drop_loop_duplicate=False,
        reverse=False,
        flip_x=False,
        flip_y=False,
        report=False,
        matting_engine="birefnet",
    )

    assert result.sheet_path.exists()
    processed = Image.open(tmp_path / "frames_processed" / "frame_0000.png").convert("RGBA")
    assert processed.getpixel((0, 0))[3] == 0
    assert processed.getpixel((16, 16))[3] > 0


def test_pipeline_depth_anything_falls_back_to_native_chroma(monkeypatch, tmp_path):
    from services import sprite_processing_pipeline as spp

    def _raise(_img):
        raise RuntimeError("missing optional depth deps")

    monkeypatch.setattr(spp, "try_depth_anything", _raise)

    img = Image.new("RGBA", (32, 32), (0, 255, 0, 255))
    for x in range(10, 22):
        for y in range(8, 26):
            img.putpixel((x, y), (220, 20, 20, 255))

    result = process_common(
        frames=[FrameItem(img, "frame_0", 0)],
        output=tmp_path,
        fps=12.0,
        cell_size=(32, 32),
        key_color=None,
        key_tolerance=30.0,
        key_feather=16.0,
        rembg=False,
        crop_mode="none",
        pad=0,
        alpha_threshold=8,
        columns=1,
        animation_name="fallback_test",
        preview_gif=False,
        save_processed_frames=True,
        anchor="center",
        ground_margin=0,
        spacing=0,
        margin=0,
        solidify=0,
        outline_width=0,
        outline_color=(0, 0, 0, 255),
        power_of_two=False,
        loop_mode="normal",
        drop_last=False,
        drop_loop_duplicate=False,
        reverse=False,
        flip_x=False,
        flip_y=False,
        report=False,
        matting_engine="depth-anything",
    )

    assert result.sheet_path.exists()
    processed = Image.open(tmp_path / "frames_processed" / "frame_0000.png").convert("RGBA")
    assert processed.getpixel((0, 0))[3] == 0
    assert processed.getpixel((16, 16))[3] > 0


def test_pixel_art_cleanup_is_native_not_comfy_node_auto_install():
    node_names = {name for _url, name in WAN_VIDEO_CUSTOM_NODES}

    assert node_names == {
        "ComfyUI-WanVideoWrapper",
        "ComfyUI-VideoHelperSuite",
        "ComfyUI_IPAdapter_plus",
        "ComfyUI-Wan-VACE-Prep",
    }


def test_blend_interpolation_expands_frame_count_and_metadata():
    frames = [
        FrameItem(Image.new("RGBA", (4, 4), (255, 0, 0, 255)), "red", 0),
        FrameItem(Image.new("RGBA", (4, 4), (0, 0, 255, 255)), "blue", 1),
    ]

    out, fps, info = interpolate_frames(frames, 12.0, 24.0)

    assert interpolated_count(2, 12.0, 24.0) == 3
    assert len(out) == 3
    assert fps == 24.0
    assert info["enabled"] is True
    assert info["engine"] == "blend"
    assert out[1].image.getpixel((0, 0))[:3] in {(127, 0, 127), (128, 0, 128)}


def test_interpolation_can_hold_impact_transitions():
    frames = [
        FrameItem(Image.new("RGBA", (4, 4), (255, 0, 0, 255)), "windup", 0),
        FrameItem(Image.new("RGBA", (4, 4), (0, 255, 0, 255)), "impact", 1),
        FrameItem(Image.new("RGBA", (4, 4), (0, 0, 255, 255)), "recover", 2),
    ]

    out, fps, info = interpolate_frames(
        frames,
        12.0,
        24.0,
        hold_name_patterns=["impact"],
    )

    assert fps == 24.0
    assert info["held_transitions"] == 2
    assert out[1].image.getpixel((0, 0))[:3] in {(255, 0, 0), (0, 255, 0)}
    assert out[1].image.getpixel((0, 0))[:3] != (127, 127, 0)


def test_dual_background_alpha_extracts_expected_rgba():
    black = Image.new("RGB", (1, 1), (50, 25, 0))
    white = Image.new("RGB", (1, 1), (177, 152, 127))

    out = extract_dual_background_alpha(black, white)

    r, g, b, a = out.getpixel((0, 0))
    assert 126 <= a <= 129
    assert 98 <= r <= 102
    assert 48 <= g <= 52
    assert b <= 2


def test_pixel_art_background_removal_keeps_interior_matching_pixels():
    img = Image.new("RGBA", (5, 5), (10, 20, 30, 255))
    for y in range(1, 4):
        for x in range(1, 4):
            img.putpixel((x, y), (200, 50, 40, 255))
    img.putpixel((2, 2), (10, 20, 30, 255))

    out = apply_pixel_art_background_removal(img, tolerance=2)

    assert out.getpixel((0, 0))[3] == 0
    assert out.getpixel((1, 1))[3] == 255
    assert out.getpixel((2, 2)) == (10, 20, 30, 255)


def test_native_alpha_refine_preserves_size_and_rgb():
    img = Image.new("RGBA", (5, 5), (20, 40, 60, 0))
    img.putpixel((2, 2), (20, 40, 60, 255))

    refined = refine_alpha_edges(img, radius=1)

    assert refined.size == img.size
    assert refined.getpixel((2, 2))[:3] == (20, 40, 60)
    assert refined.getpixel((2, 1))[3] > 0


def test_cli_exposes_research_pipeline_options():
    parser = build_parser()

    args = parser.parse_args([
        "pack",
        "--input",
        "frames",
        "--output",
        "out",
        "--alpha-refine",
        "--temporal-alpha-stabilize",
        "--temporal-alpha-strength",
        "0.7",
        "--pixel-cleanup",
        "--pixel-cleanup-colors",
        "8",
        "--pixel-cleanup-palette",
        "pico8",
        "--pixel-cleanup-dither-mode",
        "bayer",
        "--interpolate-fps",
        "24",
        "--interpolation-engine",
        "flow",
        "--interpolation-skip-pixel-art",
        "--interpolation-skip-impact-frames",
        "--interpolation-skip-patterns",
        "impact,contact",
        "--generate-normal-maps",
        "--normal-map-engine",
        "native-depth",
        "--matting-engine",
        "pixel-art",
    ])
    assert args.matting_engine == "pixel-art"
    assert args.alpha_refine is True
    assert args.temporal_alpha_stabilize is True
    assert args.temporal_alpha_strength == pytest.approx(0.7)
    assert args.pixel_cleanup is True
    assert args.pixel_cleanup_colors == 8
    assert args.pixel_cleanup_palette == "pico8"
    assert args.pixel_cleanup_dither_mode == "bayer"
    assert args.interpolate_fps == 24
    assert args.interpolation_engine == "flow"
    assert args.interpolation_skip_pixel_art is True
    assert args.interpolation_skip_impact_frames is True
    assert args.interpolation_skip_patterns == "impact,contact"
    assert args.generate_normal_maps is True
    assert args.normal_map_engine == "native-depth"

    dual = parser.parse_args(["dual-alpha", "--black", "black.png", "--white", "white.png", "--output", "out.png"])
    assert dual.func.__name__ == "cmd_dual_alpha"


def test_blender_renderer_exposes_native_dual_background_alpha():
    text = (APP / "blender_render_ortho.py").read_text(encoding="utf-8")

    assert "--dual-background-alpha" in text
    assert "combine_dual_alpha_folder" in text
    assert "extract_dual_background_alpha" in text
    assert "film_transparent = False" in text


def test_temporal_alpha_stabilizer_reduces_mask_flicker():
    frames = []
    for idx, alpha in enumerate([80, 180, 90]):
        img = Image.new("RGBA", (3, 3), (255, 255, 255, 0))
        img.putpixel((1, 1), (255, 255, 255, alpha))
        frames.append(FrameItem(img, f"f{idx}", idx))

    before = np.std([f.image.getpixel((1, 1))[3] for f in frames])
    out = stabilize_temporal_alpha(frames, strength=0.8, motion_threshold=255)
    after = np.std([f.image.getpixel((1, 1))[3] for f in out])

    assert after < before


def test_native_pixel_cleanup_reduces_visible_palette():
    img = Image.new("RGBA", (4, 1), (0, 0, 0, 0))
    for x, color in enumerate([(250, 0, 0), (230, 20, 0), (0, 0, 240), (20, 10, 220)]):
        img.putpixel((x, 0), (*color, 255))

    out = apply_native_pixel_cleanup(img, colors=2)
    colors = {out.getpixel((x, 0))[:3] for x in range(4)}

    assert len(colors) <= 2


def test_native_pixel_cleanup_supports_retro_palette_and_bayer_dither():
    img = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
    img.putpixel((0, 0), (250, 10, 70, 255))
    img.putpixel((1, 0), (30, 170, 250, 255))
    img.putpixel((0, 1), (250, 230, 40, 255))
    img.putpixel((1, 1), (20, 220, 60, 255))

    out = apply_native_pixel_cleanup(
        img,
        palette=[
            (0, 0, 0),
            (255, 0, 77),
            (41, 173, 255),
            (255, 236, 39),
            (0, 228, 54),
        ],
        dither_mode="bayer",
    )
    allowed = {
        (0, 0, 0),
        (255, 0, 77),
        (41, 173, 255),
        (255, 236, 39),
        (0, 228, 54),
    }

    assert {out.getpixel((x, y))[:3] for y in range(2) for x in range(2)} <= allowed


def test_native_pixel_cleanup_can_share_palette_across_frames():
    redish = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
    redish.putpixel((0, 0), (250, 0, 0, 255))
    redish.putpixel((1, 0), (230, 10, 0, 255))
    blueish = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
    blueish.putpixel((0, 0), (0, 0, 245, 255))
    blueish.putpixel((1, 0), (15, 0, 220, 255))

    palette = fit_native_pixel_palette([redish, blueish], colors=2)
    cleaned_a = apply_native_pixel_cleanup(redish, palette=palette)
    cleaned_b = apply_native_pixel_cleanup(blueish, palette=palette)
    shared = {tuple(color) for color in palette.tolist()}

    assert cleaned_a.getpixel((0, 0))[:3] in shared
    assert cleaned_b.getpixel((0, 0))[:3] in shared
    assert len(shared) == 2
