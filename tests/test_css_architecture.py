import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def _style_imports() -> list[str]:
    styles = (WEB / "styles.css").read_text(encoding="utf-8")
    return re.findall(r'@import url\("([^"]+)"\);', styles)


def _entrypoint_stylesheets() -> list[str]:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    hrefs = re.findall(r'<link rel="stylesheet" href="([^"]+)"', html)
    return [href.split("?", 1)[0] for href in hrefs]


def test_css_architecture_manifest_matches_stylesheet_import_order():
    manifest = json.loads((WEB / "css" / "css_architecture.json").read_text(encoding="utf-8"))
    expected = [
        file
        for layer in manifest["cascade_order"]
        for file in layer["files"]
    ]

    assert manifest["schema"] == "spriteforge.css_architecture.v1"
    assert _style_imports() == expected
    assert manifest["target_structure"] == [
        "base.css",
        "layout.css",
        "components.css",
        "views/*.css",
        "accessibility.css",
        "overrides/*.css",
    ]


def test_css_architecture_tracks_entrypoint_stylesheets():
    manifest = json.loads((WEB / "css" / "css_architecture.json").read_text(encoding="utf-8"))

    assert manifest["entrypoint_links"] == _entrypoint_stylesheets()
    assert "css/topbar_compact.css" in manifest["entrypoint_links"]
    assert "css/wizard.css" in manifest["entrypoint_links"]
    assert "palette_harmonizer.css" in manifest["entrypoint_links"]


def test_css_architecture_tracks_every_css_file():
    manifest = json.loads((WEB / "css" / "css_architecture.json").read_text(encoding="utf-8"))
    cascade = {
        file
        for layer in manifest["cascade_order"]
        for file in layer["files"]
    }
    tracked = set(manifest["entrypoint_links"]) | cascade
    actual = {path.name for path in WEB.glob("*.css")}
    actual |= {f"css/{path.name}" for path in (WEB / "css").glob("*.css")}

    assert actual - tracked == set()


def test_css_architecture_keeps_fit_overrides_last():
    imports = _style_imports()

    assert imports[0] == "css/base_variables.css"
    assert imports[1] == "css/layout_rail.css"
    assert imports[-2:] == ["css/app_compact_fit.css", "css/app_resizers.css"]


def test_design_system_exposes_skeleton_loading_primitives():
    variables = (WEB / "css" / "base_variables.css").read_text(encoding="utf-8")
    components = (WEB / "css" / "components.css").read_text(encoding="utf-8")

    assert "--space-4" in variables
    assert "--space-12" in variables
    assert "--space-16" in variables
    assert "--font-ui" in variables
    assert "--skeleton-base" in variables
    assert ".skeleton-stack" in components
    assert ".skeleton-card" in components
    assert "@keyframes skeleton-sheen" in components


def test_css_architecture_tracks_known_debt_hotspots():
    manifest = json.loads((WEB / "css" / "css_architecture.json").read_text(encoding="utf-8"))
    debt = {item["id"]: item for item in manifest["debt_register"]}

    assert {"compact-fit-overrides", "view-fragment-pairs", "component-modal-overlap"} <= set(debt)
    assert "css/app_compact_fit.css" in debt["compact-fit-overrides"]["files"]
    assert "css/topbar_compact.css" in debt["compact-fit-overrides"]["files"]
    assert "visual regression" in debt["view-fragment-pairs"]["migration"]
