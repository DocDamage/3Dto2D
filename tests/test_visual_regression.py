import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def _sprite(path: Path, color=(10, 20, 30, 255)) -> None:
    path.mkdir(parents=True)
    Image.new("RGBA", (16, 16), color).save(path / "sheet.png")
    (path / "sheet.json").write_text(
        '{"image":"sheet.png","frame_width":16,"frame_height":16,"frame_count":1,"columns":1,"rows":1}',
        encoding="utf-8",
    )


def test_visual_regression_passes_matching_sheet_and_writes_report(tmp_path):
    from services.visual_regression_service import compare_sprite_to_golden

    current = tmp_path / "current"
    golden = tmp_path / "golden"
    report_path = tmp_path / "visual_report.json"
    _sprite(current)
    _sprite(golden)

    report = compare_sprite_to_golden(current, golden, report_path=report_path)

    assert report["ok"] is True
    assert report["max_channel_delta"] == 0
    assert report["pixel_mismatch_ratio"] == 0.0
    assert report_path.exists()


def test_visual_regression_fails_when_pixels_exceed_tolerance(tmp_path):
    from services.visual_regression_service import compare_sprite_to_golden

    current = tmp_path / "current"
    golden = tmp_path / "golden"
    _sprite(current, color=(10, 20, 30, 255))
    _sprite(golden, color=(30, 20, 10, 255))

    report = compare_sprite_to_golden(current, golden, max_channel_delta=4, mismatch_ratio=0.0)

    assert report["ok"] is False
    assert report["max_channel_delta"] == 20
    assert report["pixel_mismatch_ratio"] == 1.0


def test_ui_visual_regression_uses_pixel_tolerance(tmp_path):
    from services.visual_regression_service import compare_ui_screenshot
    current, golden = tmp_path / "current.png", tmp_path / "golden.png"
    Image.new("RGBA", (100, 50), (20, 30, 40, 255)).save(current)
    Image.new("RGBA", (100, 50), (20, 30, 40, 255)).save(golden)
    report = compare_ui_screenshot(current, golden, report_path=tmp_path / "report.json")
    assert report["ok"] is True
    Image.new("RGBA", (100, 50), (200, 30, 40, 255)).save(current)
    assert compare_ui_screenshot(current, golden, mismatch_ratio=0.0)["ok"] is False
