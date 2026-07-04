import base64
import importlib
import sys
from pathlib import Path
from unittest.mock import patch

from flask import Flask


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_sanitize_frame_filename_rejects_traversal_and_bad_extensions():
    from services.frame_status_service import sanitize_frame_filename

    assert sanitize_frame_filename("frame_0001.png") == "frame_0001.png"

    for bad_name in ["../evil.png", "..\\evil.png", "evil.txt", "bad:name.png", "nested/frame.png"]:
        try:
            sanitize_frame_filename(bad_name)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected rejection for {bad_name}")


def test_save_edited_frame_rejects_traversal_frame_name(tmp_path):
    routes_module = importlib.import_module("web_routes.routes_sprites")

    sprite_dir = tmp_path / "sprite"
    (sprite_dir / "frames").mkdir(parents=True)
    (sprite_dir / "sheet.json").write_text(
        '{"fps": 12, "frame_width": 32, "frame_height": 32, "animation": "idle", "anchor": "bottom-center"}',
        encoding="utf-8",
    )

    app = Flask(__name__)
    app.register_blueprint(routes_module.routes_sprites)
    image_data = "data:image/png;base64," + base64.b64encode(b"not-a-real-png").decode("ascii")

    with patch.object(routes_module, "_resolve_sprite_output_dir", return_value=sprite_dir):
        response = app.test_client().post("/api/sprite/frame/save", json={
            "path": "output/sprite",
            "frame_name": "../evil.png",
            "image_data": image_data,
        })

    assert response.status_code == 400
    assert not (tmp_path / "evil.png").exists()


def test_skeletal_export_rejects_output_path_escape(tmp_path):
    routes_module = importlib.import_module("web_routes.routes_sprites")

    sprite_dir = tmp_path / "sprite"
    sprite_dir.mkdir(parents=True)

    app = Flask(__name__)
    app.register_blueprint(routes_module.routes_sprites)

    with (
        patch.object(routes_module, "_resolve_sprite_output_dir", return_value=sprite_dir),
        patch.object(routes_module, "export_skeletal_parts") as export_mock,
    ):
        response = app.test_client().post("/api/sprite/export_skeletal", json={
            "path": "output/sprite",
            "output": "../outside",
        })

    assert response.status_code == 400
    assert "workspace" in response.get_json()["message"]
    export_mock.assert_not_called()
