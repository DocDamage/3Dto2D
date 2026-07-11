from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def test_generate_prompt_preview_assets_are_wired():
    html = (APP / "web" / "components" / "generate.html").read_text(encoding="utf-8")
    js = (APP / "web" / "js" / "app_forms.js").read_text(encoding="utf-8")
    builder_js = (APP / "web" / "js" / "prompt_builder.js").read_text(encoding="utf-8")
    globals_js = (APP / "web" / "js" / "globals.js").read_text(encoding="utf-8")
    wizard_html = (APP / "web" / "components" / "wizard.html").read_text(encoding="utf-8")
    wizard_js = (APP / "web" / "js" / "wizard.js").read_text(encoding="utf-8")
    setup_html = (APP / "web" / "components" / "setup.html").read_text(encoding="utf-8")
    drag_drop = (APP / "web" / "js" / "drag_drop.js").read_text(encoding="utf-8")
    css = (APP / "web" / "css" / "components.css").read_text(encoding="utf-8")
    compact_css = (APP / "web" / "css" / "topbar_compact.css").read_text(encoding="utf-8")
    fit_css = (APP / "web" / "css" / "app_compact_fit.css").read_text(encoding="utf-8")
    index = (APP / "web" / "index.html").read_text(encoding="utf-8")

    assert 'id="generatePromptPreviewPanel"' in html
    assert 'id="generatePromptPreview"' in html
    assert 'id="generatePromptQuality"' in html
    assert 'id="btnAutoFixPrompt"' in html
    assert 'value="t_pose"' in html
    assert 'value="a_pose"' in html
    assert 'id="generateEstimate"' in html
    assert 'id="generateReferencePreview"' in html
    assert 'id="generateReferencePreviewImage"' in html
    assert "buildGeneratePromptPreview" in js
    assert "refreshGeneratePromptPreview" in js
    assert "applyGeneratePromptAutofix" in js
    assert "promptBuilderAutofix" in builder_js
    assert "AI Auto Fix" in builder_js
    assert "/api/prompt/autofix" in builder_js
    assert "preventDefault" in js
    assert "preventDefault" in builder_js
    assert "Math.max(0.1, Math.min(16, n))" in globals_js
    assert "spriteforgeSelectedSpriteDir" in (APP / "web" / "js" / "gallery.js").read_text(encoding="utf-8")
    assert 'id="wizCharacterPreset"' in wizard_html
    assert 'value="t_pose"' in wizard_html
    assert 'value="a_pose"' in wizard_html
    assert "CHARACTER_PRESETS" in wizard_js
    assert 'id="providerKeyGrid"' in setup_html
    assert "/api/cloud/image-provider-key" in js
    assert "refreshGenerateReferencePreview" in js
    assert "generateReferencePreviewUrl" in js
    assert "typeof refreshGenerateReferencePreview === 'function'" in drag_drop
    assert "Preview updates after upload" in drag_drop
    assert "aria-label" in drag_drop
    assert "/api/prompt/lint" in js
    assert "/api/prompt/autofix" in js
    assert "/api/generation/estimate?" in js
    assert "full_payload: data" in js
    assert ".prompt-preview-panel" in css
    assert ".prompt-preview-actions" in css
    assert ".provider-key-grid" in css
    assert ".generation-estimate" in css
    assert ".prompt-quality-badge.good" in css
    assert ".generate-reference-preview" in css
    assert ".generate-reference-tile img" in css
    assert 'body[data-active-view="generate"] .shell' in compact_css
    assert 'body[data-active-view="generate"] #generateForm' in compact_css
    assert "max-height: none !important" in compact_css
    assert "overflow: visible !important" in compact_css
    assert "overflow-y: auto" in fit_css
    assert "#view-logs #full-log" in fit_css
    assert "?v=prompt-autofix" in index
    assert '<button class="nav" data-view="generate">Sprite Lab</button>' in index
    assert "generate: 'Sprite Lab'" in (APP / "web" / "js" / "ux_enhancements.js").read_text(encoding="utf-8")
    assert "js/ux_enhancements.js?v=console-product-polish-v12" in index
