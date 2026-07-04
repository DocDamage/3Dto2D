from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def test_recent_sprite_gallery_has_hover_preview_layer():
    js = (WEB / "js" / "gallery.js").read_text(encoding="utf-8")
    css = (WEB / "css" / "components.css").read_text(encoding="utf-8")

    assert "sprite-card-media" in js
    assert "sprite-card-hover-preview" in js
    assert "hover.loading = 'lazy'" in js
    assert ".sprite-card-hover-preview" in css
    assert ".sprite-card:hover .sprite-card-hover-preview" in css
