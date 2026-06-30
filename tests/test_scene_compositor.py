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
