from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def test_skeletal_export_ui_is_wired():
    html = (APP / "web" / "components" / "packs.html").read_text(encoding="utf-8")
    js = (APP / "web" / "js" / "app_forms.js").read_text(encoding="utf-8")

    assert 'id="skeletalExportForm"' in html
    assert 'id="skeletalExportResult"' in html
    assert "Export Spine / DragonBones" in html
    assert "/api/sprite/export_skeletal" in js
    assert "skeletalExportUseSelected" in js
    assert "Open Spine JSON" in js
    assert "Open DragonBones JSON" in js
    assert "Open skeletal manifest" in js
    assert "exported.segmentation?.method" in js
