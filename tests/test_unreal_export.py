import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from services.unreal_export_service import sheet_frames
from spriteforge_engine_export import export_unreal, validate_export


def _write_sprite(sprite_dir: Path) -> None:
    sprite_dir.mkdir()
    Image.new("RGBA", (128, 64), (20, 40, 80, 255)).save(sprite_dir / "sheet.png")
    (sprite_dir / "sheet.json").write_text(
        json.dumps(
            {
                "animation": "walk",
                "direction": "right",
                "frame_width": 64,
                "frame_height": 64,
                "frame_count": 2,
                "columns": 2,
                "rows": 1,
                "fps": 12,
                "image": "sheet.png",
            }
        ),
        encoding="utf-8",
    )


def test_sheet_frames_falls_back_to_grid_metadata():
    frames = sheet_frames({"frame_width": 32, "frame_height": 24, "frame_count": 3, "columns": 2, "rows": 2})

    assert frames == [
        {"index": 0, "x": 0, "y": 0, "w": 32, "h": 24},
        {"index": 1, "x": 32, "y": 0, "w": 32, "h": 24},
        {"index": 2, "x": 0, "y": 24, "w": 32, "h": 24},
    ]


def test_unreal_export_generates_paper2d_helper_from_grid_metadata(tmp_path):
    sprite_dir = tmp_path / "hero_walk"
    out_dir = tmp_path / "unreal_out"
    _write_sprite(sprite_dir)

    export_unreal(
        sprite_dir,
        output=out_dir,
        name="hero",
        naming_convention="prefix",
        pivot_mode="center",
        ppu=128,
        filter_mode="linear",
        loop_flag=False,
        import_path="/Game/Characters/Hero",
    )

    helper = (out_dir / "unreal_import_helper.py").read_text(encoding="utf-8")
    notes = (out_dir / "UNREAL_IMPORT_NOTES.md").read_text(encoding="utf-8")
    assert "DESTINATION_PATH = \"/Game/Characters/Hero\"" in helper
    assert "unreal.TextureFilter.TF_LINEAR" in helper
    assert "PIXELS_PER_UNIT = 128" in helper
    assert "LOOP_ANIMATION = False" in helper
    assert '"x": 64' in helper
    assert "PaperFlipbookFactory" in helper
    assert "destination = /Game/Characters/Hero" in notes
    assert validate_export(out_dir, engine="unreal") is True
