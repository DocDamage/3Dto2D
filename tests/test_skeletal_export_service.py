import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def _sprite_with_parts(tmp_path: Path) -> Path:
    sprite = tmp_path / "output" / "hero"
    sprite.mkdir(parents=True)
    (sprite / "sheet.json").write_text(json.dumps({
        "animation": "idle",
        "image": "sheet.png",
        "frame_width": 8,
        "frame_height": 8,
        "frame_count": 1,
        "columns": 1,
        "fps": 12,
    }), encoding="utf-8")
    Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(sprite / "sheet.png")
    body = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    for x in range(2, 6):
        for y in range(1, 8):
            body.putpixel((x, y), (220, 20, 20, 255))
    body.save(sprite / "sheet_body.png")
    weapon = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    for x in range(5, 8):
        weapon.putpixel((x, 3), (230, 230, 40, 255))
    weapon.save(sprite / "sheet_weapon.png")
    return sprite


def test_skeletal_export_writes_spine_and_dragonbones_json(tmp_path):
    from services.skeletal_export_service import export_skeletal_parts

    sprite = _sprite_with_parts(tmp_path)
    result = export_skeletal_parts(sprite, output_dir=tmp_path / "skeletal", name="hero_idle")

    assert result["ok"] is True
    assert result["parts"] == ["body", "weapon"]
    body_meta = next(part for part in result["part_metadata"] if part["name"] == "body")
    assert body_meta["pivot"]["mode"] == "alpha-bottom-center"
    assert body_meta["pivot"]["normalized_x"] == 0.5
    assert body_meta["pivot"]["normalized_y"] == 1.0
    assert body_meta["segmentation_source"] == "segmented_layers"
    assert body_meta["frame_bounds"][0]["w"] == 4
    assert result["segmentation"]["method"] == "sam2_or_grabcut_layer_sheets"
    assert result["engine_import"]["texture_filter"] == "nearest"
    assert result["engine_import"]["coordinate_space"]["pivot_mode"] == "alpha-bottom-center"
    assert result["engine_import"]["spine"]["slot_order"] == ["body", "weapon"]
    assert result["engine_import"]["dragonbones"]["armature"] == "hero_idle"
    assert result["engine_import"]["parts"][0]["path"] == "parts/sheet_body.png"
    spine = json.loads((tmp_path / "skeletal" / "spine.json").read_text(encoding="utf-8"))
    assert [slot["name"] for slot in spine["slots"]] == ["body", "weapon"]
    dragonbones = json.loads((tmp_path / "skeletal" / "dragonbones.json").read_text(encoding="utf-8"))
    body_bone = next(bone for bone in dragonbones["armature"][0]["bone"] if bone["name"] == "body")
    assert body_bone["transform"]["x"] == 4.0
    assert body_bone["transform"]["y"] == 8.0
    assert (tmp_path / "skeletal" / "parts" / "sheet_body.png").exists()
    manifest = json.loads((tmp_path / "skeletal" / "skeletal_manifest.json").read_text(encoding="utf-8"))
    assert manifest["segmentation"]["part_sheet_count"] == 2
    assert manifest["engine_import"]["spine"]["json"] == "spine.json"
    assert result["skeletal_manifest"].endswith("skeletal_manifest.json")


def test_skeletal_export_cli_parses_command():
    from spriteforge_unified import build_parser

    args = build_parser().parse_args([
        "export-skeletal",
        "--sprite-dir",
        "output/hero",
        "--output",
        "output/hero/skeletal",
        "--name",
        "hero",
    ])

    assert args.sprite_dir == "output/hero"
    assert args.output == "output/hero/skeletal"
    assert args.name == "hero"


def test_skeletal_export_api_returns_relative_paths(monkeypatch, tmp_path):
    from spriteforge_web import app

    sprite = _sprite_with_parts(tmp_path)
    routes_sprites = sys.modules["web_routes.routes_sprites"]
    web_helpers = sys.modules["web_helpers"]
    monkeypatch.setattr(routes_sprites, "ROOT", tmp_path)
    monkeypatch.setattr(web_helpers, "ROOT", tmp_path)
    monkeypatch.setattr(web_helpers, "OUTPUT", tmp_path / "output")

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.post("/api/sprite/export_skeletal", json={
            "path": "output/hero",
            "output": "output/hero/skeletal",
            "name": "hero",
        })

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["spine_json"] == "output/hero/skeletal/spine.json"
    assert data["dragonbones_json"] == "output/hero/skeletal/dragonbones.json"
    assert data["skeletal_manifest"] == "output/hero/skeletal/skeletal_manifest.json"
