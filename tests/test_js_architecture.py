import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def _loader_scripts() -> list[str]:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert "function spriteForgeScriptList()" in html
    assert "const scripts = spriteForgeScriptList();" in html
    match = re.search(r"function spriteForgeScriptList\(\) \{\s*return \[(.*?)\];\s*\}", html, re.S)
    assert match, "index.html must define the sequential script loader list behind spriteForgeScriptList()"
    return re.findall(r"'([^']+)'", match.group(1))


def test_js_architecture_manifest_matches_loader_order():
    manifest = json.loads((WEB / "js" / "js_architecture.json").read_text(encoding="utf-8"))
    expected = [
        file
        for layer in manifest["script_order"]
        for file in layer["files"]
    ]

    assert manifest["schema"] == "spriteforge.js_architecture.v1"
    assert manifest["migration_target"] == "es-modules-no-bundler"
    assert _loader_scripts() == expected


def test_js_architecture_keeps_bootstrap_last():
    scripts = _loader_scripts()

    assert scripts[0].startswith("js/globals.js")
    assert scripts[-2].startswith("js/ux_enhancements.js")
    assert scripts[-1].startswith("js/app_main.js")


def test_js_architecture_blocks_known_health_global_regression():
    dashboard = (WEB / "js" / "app_dashboard.js").read_text(encoding="utf-8")
    status = (WEB / "js" / "app_status.js").read_text(encoding="utf-8")

    assert "function updateHealthDots" in dashboard
    assert "function updateHealthProgress" in status
    assert "function updateHealthBar" not in dashboard
    assert "function updateHealthBar" not in status


def test_js_architecture_avoids_duplicate_top_level_function_names():
    allowed_duplicates = {
        "formatDuration": {"app_dashboard.js"},
    }
    seen: dict[str, set[str]] = {}
    for path in sorted((WEB / "js").glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for name in re.findall(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", text, re.M):
            seen.setdefault(name, set()).add(path.name)

    duplicates = {
        name: files
        for name, files in seen.items()
        if len(files) > 1 and files != allowed_duplicates.get(name, set())
    }

    assert duplicates == {}
