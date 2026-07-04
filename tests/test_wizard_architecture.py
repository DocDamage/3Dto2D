import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def test_wizard_architecture_manifest_tracks_split_seams():
    manifest = json.loads((WEB / "js" / "wizard_architecture.json").read_text(encoding="utf-8"))

    assert manifest["schema"] == "spriteforge.wizard_architecture.v1"
    assert manifest["current_entry"] == "js/wizard.js"
    assert len(manifest["target_split"]) == 4
    entry = (WEB / "js" / "wizard.js").read_text(encoding="utf-8")
    for seam in manifest["target_split"]:
        assert seam["file"].startswith("js/wizard_")
        owner_path = WEB / seam["file"]
        owner = owner_path.read_text(encoding="utf-8") if owner_path.exists() else ""
        for symbol in seam["owns"]:
            assert symbol in owner or symbol in entry


def test_wizard_template_and_state_seams_load_before_entry():
    manifest = json.loads((WEB / "js" / "js_architecture.json").read_text(encoding="utf-8"))
    expected = [
        file
        for layer in manifest["script_order"]
        for file in layer["files"]
    ]

    assert expected.index("js/wizard_templates.js") < expected.index("js/wizard.js?v=wizard-reference-upload-buttons")
    assert expected.index("js/wizard_state.js") < expected.index("js/wizard.js?v=wizard-reference-upload-buttons")
    assert expected.index("js/wizard_submit.js") < expected.index("js/wizard.js?v=wizard-reference-upload-buttons")
    assert expected.index("js/wizard_ui.js") < expected.index("js/wizard.js?v=wizard-reference-upload-buttons")
    templates_js = (WEB / "js" / "wizard_templates.js").read_text(encoding="utf-8")
    assert "window.SpriteForgeWizardTemplates" in templates_js
    assert "function applyTemplateDefaults" in templates_js
    assert "function buildPromptPreviewText" in templates_js
    assert "handlers.setSelectedActions" in templates_js
    assert "window.SpriteForgeWizardTemplates.applyTemplateDefaults" in (WEB / "js" / "wizard.js").read_text(encoding="utf-8")
    assert "window.SpriteForgeWizardTemplates.buildPromptPreviewText" in (WEB / "js" / "wizard.js").read_text(encoding="utf-8")
    state_js = (WEB / "js" / "wizard_state.js").read_text(encoding="utf-8")
    assert "window.SpriteForgeWizardStateConfig" in state_js
    assert "window.SpriteForgeWizardState" in state_js
    assert "saveWizardStateSnapshot" in state_js
    assert "loadWizardStateSnapshot" in state_js
    assert "clearWizardStateSnapshot" in state_js
    assert "getSelectedActions(modal)" in state_js
    assert "setSelectedDirections(modal, directions" in state_js
    assert "setSelectedPerspective(modal, perspective" in state_js
    assert "window.SpriteForgeWizardState.getSelectedActions(modal)" in (WEB / "js" / "wizard.js").read_text(encoding="utf-8")
    assert "window.SpriteForgeWizardSubmit" in (WEB / "js" / "wizard_submit.js").read_text(encoding="utf-8")
    ui_js = (WEB / "js" / "wizard_ui.js").read_text(encoding="utf-8")
    wizard_js = (WEB / "js" / "wizard.js").read_text(encoding="utf-8")
    assert "window.SpriteForgeWizardUi" in ui_js
    assert "renderWizardStep" in ui_js
    assert "renderVisualizerGrid" in ui_js
    assert "renderSummaryPage" in ui_js
    assert "renderPreflightResult" in ui_js
    assert "renderPreflightError" in ui_js
    assert "window.SpriteForgeWizardUi.renderWizardStep" in wizard_js
    assert "window.SpriteForgeWizardUi.renderVisualizerGrid" in wizard_js
    assert "window.SpriteForgeWizardUi.renderSummaryPage" in wizard_js
    assert "window.SpriteForgeWizardUi.renderPreflightResult" in wizard_js
    submit_js = (WEB / "js" / "wizard_submit.js").read_text(encoding="utf-8")
    assert "evaluateWizardPreflight" in submit_js
    assert "window.SpriteForgeWizardSubmit.evaluateWizardPreflight" in wizard_js
    assert "validateWizardStep" in submit_js
    assert "window.SpriteForgeWizardSubmit.validateWizardStep" in wizard_js


def test_wizard_architecture_preserves_global_contracts():
    manifest = json.loads((WEB / "js" / "wizard_architecture.json").read_text(encoding="utf-8"))
    js = (WEB / "js" / "wizard.js").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")

    assert "window.openWizard" in manifest["global_contracts"]
    assert "window.closeWizard" in manifest["global_contracts"]
    assert "function openWizard()" in html
    assert "function closeWizard()" in html
    assert "window.openWizard.impl = openWizard" in js
    assert "window.closeWizard.impl = closeWizard" in js
