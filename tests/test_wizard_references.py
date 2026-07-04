import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_wizard_component_allows_character_and_style_references():
    html = (APP / "web" / "components" / "wizard.html").read_text(encoding="utf-8")

    assert 'name="wiz_reference_image"' in html
    assert 'name="wiz_style_image"' in html
    assert 'id="wizReferenceImage"' in html
    assert 'id="wizStyleImage"' in html
    assert 'id="wizSummaryReferences"' in html
    assert "Character reference image" in html
    assert "Style reference image" in html


def test_wizard_js_forwards_references_to_generation_payload():
    js = (APP / "web" / "js" / "wizard.js").read_text(encoding="utf-8")
    submit = (APP / "web" / "js" / "wizard_submit.js").read_text(encoding="utf-8")
    templates = (APP / "web" / "js" / "wizard_templates.js").read_text(encoding="utf-8")
    ui = (APP / "web" / "js" / "wizard_ui.js").read_text(encoding="utf-8")

    assert 'form.querySelector(\'[name="wiz_reference_image"]\')' in js
    assert 'form.querySelector(\'[name="wiz_style_image"]\')' in js
    assert "reference_image: context.referenceImage" in submit
    assert "style_image: context.styleImage" in submit
    assert "Reference Image:" in templates
    assert "wizSummaryReferences" in ui


def test_wizard_state_persists_reference_fields():
    js = (APP / "web" / "js" / "wizard.js").read_text(encoding="utf-8")

    assert "referenceImage" in js
    assert "styleImage" in js
    assert "state.referenceImage" in js
    assert "state.styleImage" in js


def test_wizard_installs_reference_upload_drop_targets_after_load():
    js = (APP / "web" / "js" / "wizard.js").read_text(encoding="utf-8")
    drag_js = (APP / "web" / "js" / "drag_drop.js").read_text(encoding="utf-8")

    assert "window.installWizardDrops?.()" in js
    assert "wizardReferenceDropTarget" in drag_js
    assert "wizardStyleDropTarget" in drag_js
    assert "Choose image" in drag_js
    assert "or drag and drop here" in drag_js


def test_wizard_cache_buster_updated_for_references():
    html = (APP / "web" / "index.html").read_text(encoding="utf-8")
    js = (APP / "web" / "js" / "wizard.js").read_text(encoding="utf-8")

    assert "js/wizard.js?v=wizard-reference-upload-buttons" in html
    assert "css/wizard.css?v=wizard-reference-upload-buttons" in html
    assert "components/wizard.html?v=wizard-reference-upload-buttons" in js
