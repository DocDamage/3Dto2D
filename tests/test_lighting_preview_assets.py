from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def test_lighting_preview_assets_are_wired():
    index = (APP / "web" / "index.html").read_text(encoding="utf-8")
    component = (APP / "web" / "components" / "lighting_preview.html").read_text(encoding="utf-8")
    script = (APP / "web" / "js" / "lighting_preview.js").read_text(encoding="utf-8")
    css = (APP / "web" / "lighting_preview.css").read_text(encoding="utf-8")

    assert "lighting_preview.css" in index
    assert "components/' + name" in index
    assert "'lighting_preview'" in index
    assert "js/lighting_preview.js" in index
    assert 'data-view="lighting_preview"' in index
    assert 'id="lightingCanvas"' in component
    assert 'id="lightingExportGif"' in component
    assert "sheet_normal.png" in script
    assert "sheet_specular.png" in script
    assert "sheet_ao.png" in script
    assert "specMask" in script
    assert "aoMask" in script
    assert "renderLightingPreview" in script
    assert "pointerdown" in script
    assert "/api/sprite/export_lighting_preview" in script
    assert ".lighting-preview-layout" in css
