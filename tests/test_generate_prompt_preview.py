from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def test_generate_prompt_preview_assets_are_wired():
    html = (APP / "web" / "components" / "generate.html").read_text(encoding="utf-8")
    js = (APP / "web" / "js" / "app_forms.js").read_text(encoding="utf-8")
    drag_drop = (APP / "web" / "js" / "drag_drop.js").read_text(encoding="utf-8")
    css = (APP / "web" / "css" / "components.css").read_text(encoding="utf-8")

    assert 'id="generatePromptPreviewPanel"' in html
    assert 'id="generatePromptPreview"' in html
    assert 'id="generatePromptQuality"' in html
    assert 'id="generateEstimate"' in html
    assert 'id="generateReferencePreview"' in html
    assert 'id="generateReferencePreviewImage"' in html
    assert "buildGeneratePromptPreview" in js
    assert "refreshGeneratePromptPreview" in js
    assert "refreshGenerateReferencePreview" in js
    assert "generateReferencePreviewUrl" in js
    assert "typeof refreshGenerateReferencePreview === 'function'" in drag_drop
    assert "Preview updates after upload" in drag_drop
    assert "aria-label" in drag_drop
    assert "/api/prompt/lint" in js
    assert "/api/generation/estimate?" in js
    assert "full_payload: data" in js
    assert ".prompt-preview-panel" in css
    assert ".generation-estimate" in css
    assert ".prompt-quality-badge.good" in css
    assert ".generate-reference-preview" in css
    assert ".generate-reference-tile img" in css
