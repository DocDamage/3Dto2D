import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def _sprite(root: Path, rel: str, animation: str) -> None:
    sprite_dir = root / rel
    sprite_dir.mkdir(parents=True)
    (sprite_dir / "sheet.png").write_bytes(b"fake")
    (sprite_dir / "sheet.json").write_text(
        json.dumps(
            {
                "animation": animation,
                "image": "sheet.png",
                "frame_width": 16,
                "frame_height": 16,
                "frame_count": 2,
                "columns": 2,
                "rows": 1,
                "fps": 12,
            }
        ),
        encoding="utf-8",
    )


def test_scene_compositor_builds_layer_manifest(tmp_path):
    from services.scene_compositor_service import build_scene_manifest

    _sprite(tmp_path, "output/hero_idle", "idle")
    _sprite(tmp_path, "output/slime_walk", "walk")

    manifest = build_scene_manifest(
        tmp_path,
        {
            "name": "test_scene",
            "width": 320,
            "height": 180,
            "layers": [
                {"name": "Hero", "sprite_path": "output/hero_idle", "x": 120, "y": 90, "scale": 2},
                {"name": "Slime", "sprite_path": "output/slime_walk", "x": 180, "y": 110, "scale": 1.5},
            ],
        },
    )

    assert manifest["ok"] is True
    assert manifest["scene"]["width"] == 320
    assert manifest["scene"]["height"] == 180
    assert [layer["name"] for layer in manifest["layers"]] == ["Hero", "Slime"]
    assert manifest["layers"][0]["sheet_url"] == "/file/output/hero_idle/sheet.png"
    assert manifest["layers"][1]["frame_count"] == 2
    assert manifest["handoff"]["schema"] == "spriteforge.scene_handoff.v1"
    assert manifest["handoff"]["engine_import"]["texture_filter"] == "nearest"
    assert manifest["handoff"]["dependencies"][0]["sheet_json"] == "output/hero_idle/sheet.json"


def test_scene_compositor_snaps_sorts_and_exports_godot_scene(tmp_path):
    from services.scene_compositor_service import build_scene_manifest

    _sprite(tmp_path, "output/hero_idle", "idle")
    _sprite(tmp_path, "output/slime_walk", "walk")

    manifest = build_scene_manifest(
        tmp_path,
        {
            "name": "battle_scene",
            "width": 320,
            "height": 180,
            "grid_size": 16,
            "snap_to_grid": True,
            "background_color": "#203040",
            "write_exports": True,
            "output_dir": "output/scenes/battle_scene",
            "layers": [
                {"name": "Slime", "sprite_path": "output/slime_walk", "x": 181, "y": 111, "scale": 1.5, "z": 5},
                {"name": "Hero", "sprite_path": "output/hero_idle", "x": 123, "y": 91, "scale": 2, "z": 1},
            ],
        },
    )

    assert [layer["name"] for layer in manifest["layers"]] == ["Hero", "Slime"]
    assert manifest["layers"][0]["x"] == 128
    assert manifest["layers"][0]["y"] == 96
    assert manifest["scene"]["background"]["color"] == "#203040"
    assert manifest["exports"]["manifest_path"] == "output/scenes/battle_scene/scene_manifest.json"
    assert manifest["exports"]["godot_scene_path"] == "output/scenes/battle_scene/battle_scene.tscn"
    assert manifest["exports"]["animation_exports"]["render_status"] == "planned"
    assert manifest["handoff"]["validation"]["layer_count"] == 2
    assert manifest["exports"]["animation_exports"]["gif_path"] == "output/scenes/battle_scene/composite.gif"
    assert manifest["exports"]["animation_exports"]["webm_path"] == "output/scenes/battle_scene/composite.webm"
    godot_text = (tmp_path / "output/scenes/battle_scene/battle_scene.tscn").read_text(encoding="utf-8")
    assert "AnimatedSprite2D" in godot_text
    assert "z_index = 1" in godot_text
    exported_manifest = json.loads((tmp_path / "output/scenes/battle_scene/scene_manifest.json").read_text(encoding="utf-8"))
    assert exported_manifest["exports"]["animation_exports"]["schema"] == "spriteforge.scene_composite_exports.v1"
    assert exported_manifest["handoff"]["schema"] == "spriteforge.scene_handoff.v1"


def test_scene_compositor_api_returns_manifest(monkeypatch, tmp_path):
    from spriteforge_web import app

    routes_projects_mod = sys.modules["web_routes.routes_projects"]
    monkeypatch.setattr(routes_projects_mod, "ROOT", tmp_path)
    _sprite(tmp_path, "output/hero_idle", "idle")

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.post(
            "/api/scene_compositor/preview",
            json={"layers": [{"name": "Hero", "sprite_path": "output/hero_idle"}]},
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["layers"][0]["animation"] == "idle"
