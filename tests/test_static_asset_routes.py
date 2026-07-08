import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from spriteforge_web import app


def test_root_relative_web_assets_are_served():
    app.config["TESTING"] = True
    with app.test_client() as client:
        for path in [
            "/styles.css",
            "/sprite_preview.css",
            "/js/globals.js",
            "/components/dashboard.html",
            "/logo.svg",
        ]:
            response = client.get(path)
            assert response.status_code == 200, path


def test_root_relative_web_asset_route_blocks_traversal():
    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/../spriteforge_web.py")
        assert response.status_code in {403, 404}
