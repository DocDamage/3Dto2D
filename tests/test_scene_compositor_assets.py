from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def test_scene_compositor_assets_are_loaded():
    index = (APP / "web" / "index.html").read_text(encoding="utf-8")
    script = (APP / "web" / "js" / "scene_compositor.js").read_text(encoding="utf-8")

    assert "/web/scene_compositor.css" in index
    assert "/web/js/scene_compositor.js" in index
    assert "/api/scene_compositor/preview" in script
    assert "sceneCompositorCanvas" in script
