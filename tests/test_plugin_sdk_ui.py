from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def test_plugin_sdk_starter_ui_is_wired():
    html = (WEB / "components" / "release.html").read_text(encoding="utf-8")
    js = (WEB / "js" / "marketplace_gallery.js").read_text(encoding="utf-8")
    css = (WEB / "marketplace_gallery.css").read_text(encoding="utf-8")

    assert 'id="pluginSdkId"' in html
    assert 'id="loadPluginSdkStarter"' in html
    assert 'id="pluginSdkSummary"' in html
    assert 'id="pluginSdkScaffold"' in html
    assert "function loadPluginSdkStarter" in js
    assert "/api/plugins/sdk?id=" in js
    assert "contract.known_hooks" in js
    assert "starter.manifest" in js
    assert "starter.files" in js
    assert ".plugin-sdk-card" in css
    assert ".plugin-sdk-scaffold" in css
