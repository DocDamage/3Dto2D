import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_resolution_hierarchy_exports_nearest_pixel_art_targets(tmp_path):
    from services.sprite_processing_pipeline import process_common
    from services.sprite_video_loader import FrameItem

    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    for y in range(2, 6):
        for x in range(2, 6):
            img.putpixel((x, y), (255, 0, 0, 255))

    process_common(
        frames=[FrameItem(img, "frame_0", 0)],
        output=tmp_path,
        fps=12,
        cell_size=(8, 8),
        key_color=None,
        key_tolerance=45,
        key_feather=0,
        rembg=False,
        crop_mode="none",
        pad=0,
        alpha_threshold=8,
        columns=1,
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
        resolutions="4",
        pixel_cleanup=True,
        pixel_cleanup_colors=2,
    )

    scaled = Image.open(tmp_path / "sheet_4.png").convert("RGBA")
    meta = json.loads((tmp_path / "sheet_4.json").read_text(encoding="utf-8"))

    assert scaled.size == (4, 4)
    assert meta["frame_width"] == 4
    assert meta["frame_height"] == 4
    assert meta["extra"]["resolution_export"]["resample"] == "nearest"
    assert meta["extra"]["resolution_export"]["readability"]["readable"] is True
    assert (tmp_path / "sheet_4.aseprite.json").exists()


def test_resolution_hierarchy_alias_parses_and_forwards():
    from services.web_helpers_cmd import build_action_command
    from spriteforge_unified import build_parser

    args = build_parser().parse_args([
        "generate-sprite",
        "--resolution-hierarchy",
        "128,64,32",
    ])
    assert args.resolution_hierarchy == "128,64,32"

    _, cmd = build_action_command({
        "action": "generate_sprite",
        "quality_check": False,
        "resolution_hierarchy": "128,64,32",
    })
    assert "--resolution-hierarchy" in cmd
    assert cmd[cmd.index("--resolution-hierarchy") + 1] == "128,64,32"
