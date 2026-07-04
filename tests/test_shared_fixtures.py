import json

from PIL import Image


def test_synthetic_sprite_factory_creates_complete_sprite_output(synthetic_sprite_factory):
    sprite_dir = synthetic_sprite_factory(
        "fixture_sprite",
        size=(8, 8),
        colors=[(255, 0, 0, 255), (0, 255, 0, 255)],
        action="walk",
        direction="front",
        durations_ms=[120, 240],
        frame_names=["anticipation", "step"],
        qa_report={"score": 88, "metrics": {"loop_seam_rmse": 4}},
    )

    meta = json.loads((sprite_dir / "sheet.json").read_text(encoding="utf-8"))
    sheet = Image.open(sprite_dir / "sheet.png").convert("RGBA")
    frame_files = sorted((sprite_dir / "frames_processed").glob("frame_*.png"))
    qa = json.loads((sprite_dir / "qa" / "qa_report.json").read_text(encoding="utf-8"))

    assert meta["frame_count"] == 2
    assert meta["frame_width"] == 8
    assert meta["action"] == "walk"
    assert meta["direction"] == "front"
    assert meta["frames"][1]["x"] == 8
    assert meta["frames"][0]["name"] == "anticipation"
    assert meta["frames"][1]["duration_ms"] == 240
    assert meta["frame_durations_ms"] == [120, 240]
    assert sheet.size == (16, 8)
    assert len(frame_files) == 2
    assert qa["score"] == 88


def test_synthetic_frame_items_factory_returns_frame_items(synthetic_frame_items):
    frames = synthetic_frame_items(size=(4, 4), colors=[(1, 2, 3, 255)])

    assert len(frames) == 1
    assert frames[0].name == "frame_0000"
    assert frames[0].source_index == 0
    assert frames[0].image.size == (4, 4)
