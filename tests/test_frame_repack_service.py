import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from spriteforge_web import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_repack_sprite_sheet_reorders_duplicates_and_duration(synthetic_sprite_factory):
    from services.frame_repack_service import repack_sprite_sheet
    from PIL import Image

    sprite_dir = synthetic_sprite_factory("sprite")
    result = repack_sprite_sheet(sprite_dir, {
        "frames": [
            {"source_index": 2, "duration_ms": 150},
            {"source_index": 0},
            {"source_index": 0, "duration_ms": 250},
        ],
        "fps": 10,
        "backup": False,
    })

    meta = json.loads((sprite_dir / "sheet.json").read_text(encoding="utf-8"))
    sheet = Image.open(sprite_dir / "sheet.png").convert("RGBA")
    frame_files = sorted((sprite_dir / "frames_processed").glob("*.png"))

    assert result["ok"] is True
    assert result["frame_count"] == 3
    assert meta["fps"] == 10
    assert meta["frames"][0]["source_index"] == 2
    assert meta["frames"][0]["duration_ms"] == 150
    assert meta["frames"][2]["source_index"] == 0
    assert meta["frames"][2]["duration_ms"] == 250
    history = meta["extra"]["frame_repack_history"]
    assert history["schema"] == "spriteforge.frame_repack_history.v1"
    assert len(history["operation_id"]) == 16
    assert history["source_frame_count"] == 3
    assert history["output_frame_count"] == 3
    assert history["duration_overrides"] == 2
    assert history["duplicate_outputs"] == 1
    assert history["deleted_source_indices"] == [1]
    assert history["mappings"][0]["source_index"] == 2
    assert history["mappings"][0]["duration_ms"] == 150
    assert history["mappings"][2]["source_index"] == 0
    assert history["mappings"][2]["duration_ms"] == 250
    assert meta["extra"]["timeline_edit"]["history_schema"] == history["schema"]
    assert result["frame_repack_history"]["operation_id"] == history["operation_id"]
    assert len(frame_files) == 3
    assert sheet.getpixel((1, 1)) == (40, 40, 220, 255)
    preview = Image.open(sprite_dir / "preview.gif")
    assert preview.info["duration"] == 150
    assert (sprite_dir / "report.html").exists()


def test_repack_sprite_sheet_sanitizes_frame_labels(synthetic_sprite_factory):
    from services.frame_repack_service import repack_sprite_sheet
    from services.frame_status_service import sanitize_review_note

    sprite_dir = synthetic_sprite_factory("sprite_labels")
    result = repack_sprite_sheet(sprite_dir, {
        "frames": [{"source_index": 0, "label": "../boss\\idle\x00frame"}],
        "backup": False,
    })

    assert result["timeline"][0]["label"] == "bossidleframe"
    assert "\x00" not in sanitize_review_note("bad\x00note")


def test_repack_sheet_api(client, tmp_path, monkeypatch, synthetic_sprite_factory):
    import web_helpers as web_mod

    sprite_dir = synthetic_sprite_factory("hero", root=tmp_path / "output")
    monkeypatch.setattr(web_mod, "ROOT", tmp_path)
    monkeypatch.setattr(web_mod, "OUTPUT", tmp_path / "output")

    response = client.post(
        "/api/repack-sheet",
        data=json.dumps({
            "path": "output/hero",
            "frames": [{"source_index": 1}, {"source_index": 1}, {"source_index": 0}],
            "fps": 8,
            "backup": False,
        }),
        content_type="application/json",
    )

    data = json.loads(response.data.decode("utf-8"))
    meta = json.loads((sprite_dir / "sheet.json").read_text(encoding="utf-8"))

    assert response.status_code == 200
    assert data["ok"] is True
    assert data["frame_count"] == 3
    assert meta["fps"] == 8
    assert meta["frames"][0]["source_index"] == 1
