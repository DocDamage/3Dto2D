from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def test_animated_export_ui_is_wired():
    html = (APP / "web" / "components" / "packs.html").read_text(encoding="utf-8")
    js = (APP / "web" / "js" / "app_forms.js").read_text(encoding="utf-8")

    assert 'id="animatedExportForm"' in html
    assert 'value="apng"' in html
    assert 'value="webp"' in html
    assert 'value="lottie"' in html
    assert 'id="animatedExportResult"' in html
    assert "/api/sprite/export_animation" in js
    assert "animatedExportUseSelected" in js
    assert "Open export" in js
