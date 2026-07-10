from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB_JS = ROOT / "app" / "web" / "js"


def test_api_helper_does_not_cancel_mutations_or_leave_pending_promises():
    source = (WEB_JS / "globals.js").read_text(encoding="utf-8")

    assert "method === 'GET' || method === 'HEAD'" in source
    assert "return { ok: false, aborted: true };" in source
    assert "new Promise(() => {})" not in source


def test_dynamic_asset_metadata_uses_dom_text_apis():
    pixel = (WEB_JS / "pixel_studio.js").read_text(encoding="utf-8")
    frames = (WEB_JS / "frame_editor.js").read_text(encoding="utf-8")

    assert "name.textContent = `${step.name || 'Step'}:`" in pixel
    assert "caption.textContent = String(label" in pixel
    assert '<span>${label}</span>' not in pixel
    assert "image.alt = `Frame ${index + 1}`" in frames
    assert 'tile.innerHTML = `<img src="${frame.url' not in frames
