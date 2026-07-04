import json
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def _green_screen_frame(size=(24, 24)) -> Image.Image:
    img = Image.new("RGBA", size, (0, 255, 0, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((7, 5, 16, 20), fill=(220, 40, 40, 255))
    return img


@pytest.mark.parametrize("matting_engine", ["chroma", "pixel-art", "rembg", "birefnet", "depth-anything"])
def test_process_common_keeps_matting_engines_selectable(tmp_path, monkeypatch, matting_engine):
    import services.sprite_processing_pipeline as pipeline
    from services.sprite_processing_pipeline import process_common
    from services.sprite_video_loader import FrameItem

    def unavailable(_img):
        raise RuntimeError("optional engine unavailable in test")

    monkeypatch.setattr(pipeline, "try_rembg", unavailable)
    monkeypatch.setattr(pipeline, "try_birefnet", unavailable)
    monkeypatch.setattr(pipeline, "try_depth_anything", unavailable)

    frames = [
        FrameItem(_green_screen_frame(), "idle_0000", 0),
        FrameItem(_green_screen_frame(), "idle_0001", 1),
    ]
    output = tmp_path / f"out_{matting_engine.replace('-', '_')}"

    result = process_common(
        frames=frames,
        output=output,
        fps=12.0,
        cell_size=(24, 24),
        key_color=(0, 255, 0),
        key_tolerance=40.0,
        key_feather=0.0,
        rembg=False,
        crop_mode="none",
        pad=0,
        alpha_threshold=8,
        columns=None,
        animation_name="idle",
        preview_gif=False,
        save_processed_frames=True,
        anchor="bottom-center",
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
        matting_engine=matting_engine,
    )

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))

    assert result.frame_count == 2
    assert result.sheet_path.exists()
    assert metadata["extra"]["matting_engine"] == matting_engine
    assert len(list((output / "frames_processed").glob("*.png"))) == 2
