import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def _solid_frame(color, name):
    from services.sprite_video_loader import FrameItem

    return FrameItem(Image.new("RGBA", (4, 4), color), name, 0)


def test_temporal_smooth_reduces_rgb_flicker():
    from services.sprite_temporal_smooth import stabilize_temporal_coherence

    frames = [
        _solid_frame((100, 40, 40, 255), "a"),
        _solid_frame((240, 40, 40, 255), "b"),
        _solid_frame((102, 40, 40, 255), "c"),
    ]

    out, info = stabilize_temporal_coherence(
        frames,
        radius=1,
        color_strength=0.75,
        alpha_strength=0,
        histogram_match=False,
    )

    before = np.asarray(frames[1].image)[0, 0, 0]
    after = np.asarray(out[1].image)[0, 0, 0]
    assert info["enabled"] is True
    assert after < before
    assert after > 100


def test_process_common_writes_temporal_smooth_metadata(tmp_path):
    from services.sprite_processing_pipeline import process_common

    frames = [
        _solid_frame((100, 20, 20, 255), "a"),
        _solid_frame((230, 20, 20, 255), "b"),
        _solid_frame((102, 20, 20, 255), "c"),
    ]
    out = tmp_path / "sprite"
    process_common(
        frames=frames,
        output=out,
        fps=12,
        cell_size=(4, 4),
        key_color=None,
        key_tolerance=45,
        key_feather=0,
        rembg=False,
        crop_mode="none",
        pad=0,
        alpha_threshold=8,
        columns=3,
        animation_name="idle",
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
        temporal_smooth=True,
        temporal_smooth_radius=1,
        temporal_smooth_color_strength=0.5,
        temporal_smooth_alpha_strength=0.25,
    )

    meta = json.loads((out / "sheet.json").read_text(encoding="utf-8"))
    assert meta["extra"]["temporal_smooth"]["enabled"] is True
    assert meta["extra"]["temporal_smooth"]["radius"] == 1


def test_temporal_smooth_flags_parse_and_forward():
    from services.web_helpers_cmd import build_action_command
    from spriteforge_unified import build_parser

    _, cmd = build_action_command({
        "action": "generate_sprite",
        "quality_check": False,
        "temporal_smooth": True,
        "temporal_smooth_radius": "2",
        "temporal_smooth_color_strength": "0.4",
        "temporal_smooth_alpha_strength": "0.6",
        "temporal_smooth_no_histogram": True,
    })

    assert "--temporal-smooth" in cmd
    assert "--temporal-smooth-radius" in cmd
    assert "--temporal-smooth-color-strength" in cmd
    assert "--temporal-smooth-alpha-strength" in cmd
    assert "--temporal-smooth-no-histogram" in cmd

    args = build_parser().parse_args([
        "generate-sprite",
        "--temporal-smooth",
        "--temporal-smooth-radius",
        "2",
        "--temporal-smooth-color-strength",
        "0.4",
        "--temporal-smooth-alpha-strength",
        "0.6",
        "--temporal-smooth-no-histogram",
    ])

    assert args.temporal_smooth is True
    assert args.temporal_smooth_radius == 2
    assert args.temporal_smooth_color_strength == 0.4
    assert args.temporal_smooth_alpha_strength == 0.6
    assert args.temporal_smooth_no_histogram is True


def test_rife_interpolation_engine_falls_back_to_blend(monkeypatch):
    from services import sprite_interpolation

    monkeypatch.setattr(sprite_interpolation, "_rife_executable", lambda: None)
    frames = [
        _solid_frame((0, 0, 0, 255), "a"),
        _solid_frame((100, 0, 0, 255), "b"),
    ]

    out, fps, info = sprite_interpolation.interpolate_frames(frames, 12, 24, engine="rife")

    assert fps == 24
    assert info["engine"] == "rife"
    assert len(out) == 3
    assert out[1].name.endswith("_interp_0001")


def test_rife_interpolation_flags_parse_and_forward():
    from services.web_helpers_cmd import build_action_command
    from spriteforge_unified import build_parser

    _, cmd = build_action_command({
        "action": "generate_sprite",
        "quality_check": False,
        "interpolate_fps": "24",
        "interpolation_engine": "rife",
    })

    assert "--interpolation-engine" in cmd
    assert "rife" in cmd

    args = build_parser().parse_args([
        "generate-sprite",
        "--interpolate-fps",
        "24",
        "--interpolation-engine",
        "rife",
    ])

    assert args.interpolate_fps == 24
    assert args.interpolation_engine == "rife"
