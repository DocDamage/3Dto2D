import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def _evaluate_preflight(status):
    if not shutil.which("node"):
        pytest.skip("Node.js is required for the JavaScript wizard contract test")
    script = """
global.window = {};
const fs = require('fs');
eval(fs.readFileSync('app/web/js/wizard_submit.js', 'utf8'));
const status = JSON.parse(process.argv[1]);
const goals = ['single', 'pack', 'convert', 'release'];
const results = Object.fromEntries(goals.map(goal => [
  goal,
  window.SpriteForgeWizardSubmit.evaluateWizardPreflight(status, goal)
]));
process.stdout.write(JSON.stringify(results));
"""
    completed = subprocess.run(
        ["node", "-e", script, json.dumps(status)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


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

    assert expected.index("js/wizard_templates.js") < expected.index("js/wizard.js?v=wizard-product-ready-v12")
    assert expected.index("js/wizard_state.js") < expected.index("js/wizard.js?v=wizard-product-ready-v12")
    assert expected.index("js/wizard_submit.js?v=wizard-product-ready-v12") < expected.index("js/wizard.js?v=wizard-product-ready-v12")
    assert expected.index("js/wizard_ui.js?v=wizard-product-ready-v12") < expected.index("js/wizard.js?v=wizard-product-ready-v12")
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


def test_wizard_preflight_requirements_follow_the_selected_goal():
    results = _evaluate_preflight({
        "comfy_running": False,
        "models": {"ok": False},
        "disk": {"free_gb": 20},
        "job": {"running": False},
    })

    for goal in ("single", "pack"):
        assert results[goal]["ok"] is False
        assert results[goal]["required"]["models"] is True
        assert results[goal]["required"]["comfy"] is False
        assert any("art-tool setup" in reason for reason in results[goal]["reasons"])
        assert any("start automatically" in notice for notice in results[goal]["notices"])

    for goal in ("convert", "release"):
        assert results[goal]["ok"] is True
        assert results[goal]["applicable"]["models"] is False
        assert results[goal]["applicable"]["comfy"] is False
        assert results[goal]["reasons"] == []
        assert results[goal]["notices"] == []


def test_wizard_preflight_allows_generation_to_auto_start_the_engine():
    results = _evaluate_preflight({
        "comfy_running": False,
        "models": {"ok": True},
        "disk": {"free_gb": 20},
        "job": {"running": False},
    })

    for goal in ("single", "pack"):
        assert results[goal]["ok"] is True
        assert results[goal]["reasons"] == []
        assert any("start automatically" in notice for notice in results[goal]["notices"])


def test_wizard_preflight_keeps_shared_resource_failures_blocking():
    results = _evaluate_preflight({
        "comfy_running": True,
        "models": {"ok": True},
        "disk": {"free_gb": 2},
        "job": {"running": True},
    })

    for goal in ("single", "pack", "convert", "release"):
        assert results[goal]["ok"] is False
        assert any("5 GB" in reason for reason in results[goal]["reasons"])
        assert any("already in progress" in reason for reason in results[goal]["reasons"])


def test_wizard_preflight_ui_is_accessible_and_refreshes_after_setup():
    html = (WEB / "components" / "wizard.html").read_text(encoding="utf-8")
    wizard_js = (WEB / "js" / "wizard.js").read_text(encoding="utf-8")
    ui_js = (WEB / "js" / "wizard_ui.js").read_text(encoding="utf-8")

    assert 'id="wizPreflightError" role="status" aria-live="polite" aria-atomic="true"' in html
    assert "evaluateWizardPreflight(statusData, goal)" in wizard_js
    assert "runPreflightCheck({ refresh: true })" in wizard_js
    assert "renderPreflightNotice" in ui_js
    assert "renderPreflightRepair(errBox, result.notices.join" not in ui_js
