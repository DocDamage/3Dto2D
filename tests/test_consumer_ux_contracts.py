import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "app" / "web"


PRIMARY_SIMPLE_VIEWS = [
    "guide",
    "dashboard",
    "generate",
    "aaa_studio",
    "quality",
    "release",
]
FRIENDLY_VIEW_LABELS = {
    "guide": "Home",
    "dashboard": "Projects",
    "generate": "Create",
    "aaa_studio": "Studio",
    "quality": "Review",
    "release": "Export",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _opening_tag(source: str, tag: str, element_id: str) -> str:
    match = re.search(
        rf"<{tag}\b[^>]*\bid=[\"']{re.escape(element_id)}[\"'][^>]*>",
        source,
        re.IGNORECASE,
    )
    assert match, f"Missing <{tag}> with id={element_id!r}"
    return match.group(0)


def _css_rules(source: str):
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", source, re.DOTALL):
        yield match.group(1).strip(), match.group(2).strip()


def test_consumer_shell_has_skip_target_and_mobile_navigation_relationships():
    index = _read(WEB / "index.html")

    assert re.search(
        r"<a\b[^>]*\bclass=[\"'][^\"']*\bskip-link\b[^\"']*[\"'][^>]*\bhref=[\"']#mainContent[\"']",
        index,
        re.IGNORECASE,
    )
    main = _opening_tag(index, "main", "mainContent")
    assert re.search(r"\btabindex=[\"']-1[\"']", main, re.IGNORECASE)

    primary_navigation = re.search(
        r"<(?:nav|aside)\b[^>]*\bid=[\"']primaryNavigation[\"'][^>]*>",
        index,
        re.IGNORECASE,
    )
    assert primary_navigation, "Primary navigation needs a stable landmark id"
    assert 'aria-label="Primary navigation"' in index

    toggle = _opening_tag(index, "button", "mobileRailToggle")
    assert re.search(r"\baria-controls=[\"']primaryNavigation[\"']", toggle, re.IGNORECASE)
    assert re.search(r"\baria-expanded=[\"']false[\"']", toggle, re.IGNORECASE)


def test_consumer_styles_and_script_are_registered_in_every_runtime_manifest():
    consumer_css = sorted(path for path in WEB.rglob("*.css") if "consumer" in path.stem.lower())
    consumer_js = sorted(path for path in (WEB / "js").glob("*.js") if "consumer" in path.stem.lower())
    assert len(consumer_css) == 1, "Keep the consumer experience in one discoverable CSS module"
    assert len(consumer_js) == 1, "Keep the consumer experience in one discoverable JS module"

    css_ref = consumer_css[0].relative_to(WEB).as_posix()
    js_ref = consumer_js[0].relative_to(WEB).as_posix()
    index = _read(WEB / "index.html")
    styles = _read(WEB / "styles.css")
    css_manifest = _read(WEB / "css" / "css_architecture.json")
    script_loader = _read(WEB / "js" / "script_loader.js")
    js_manifest = _read(WEB / "js" / "js_architecture.json")

    assert css_ref in index or css_ref in styles
    assert css_ref in css_manifest
    assert js_ref in index
    assert js_ref in script_loader
    assert js_ref in js_manifest


def test_simple_mode_has_six_friendly_primary_destinations():
    index = _read(WEB / "index.html")
    consumer_js_files = sorted(path for path in (WEB / "js").glob("*.js") if "consumer" in path.stem.lower())
    assert consumer_js_files, "Missing consumer navigation module"
    consumer_js = _read(consumer_js_files[0])

    primary_match = re.search(
        r"(?:CONSUMER_PRIMARY_VIEWS|PRIMARY_SIMPLE_VIEWS)\s*=\s*(?:Object\.freeze\s*\(\s*)?\[(.*?)\]",
        consumer_js,
        re.DOTALL,
    )
    assert primary_match, "Declare the simple-mode destinations as a testable ordered list"
    declared_views = re.findall(r"[\"']([a-z][a-z0-9_]*)[\"']", primary_match.group(1))
    assert declared_views == PRIMARY_SIMPLE_VIEWS

    for view, label in FRIENDLY_VIEW_LABELS.items():
        mapping = rf"(?:[\"']{re.escape(view)}[\"']|\b{re.escape(view)})\s*:\s*[\"']{re.escape(label)}[\"']"
        assert re.search(mapping, consumer_js), f"Missing friendly runtime label {view!r} -> {label!r}"

        nav = re.search(
            rf"<button\b[^>]*\bdata-view=[\"']{re.escape(view)}[\"'][^>]*>",
            index,
            re.IGNORECASE,
        )
        assert nav, f"Missing navigation route for {view}"
        assert "mode-detail" not in nav.group(0)
        assert "mode-expert" not in nav.group(0)

    assert "consumer-primary" in consumer_js
    assert "nav-label" in consumer_js


def test_sidebar_collapse_control_announces_its_current_action():
    index = _read(WEB / "index.html")
    ux_js = _read(WEB / "js" / "ux_enhancements.js")

    assert '<aside class="rail" id="appRail">' in index
    assert 'aria-controls="appRail"' in index
    assert 'aria-expanded="true"' in index
    assert "const syncCollapseToggle = collapsed =>" in ux_js
    assert "collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'" in ux_js
    assert "collapseToggle.setAttribute('aria-label', label)" in ux_js
    assert "collapseToggle.setAttribute('aria-expanded', String(!collapsed))" in ux_js
    assert "syncCollapseToggle(collapsedNow)" in ux_js


def test_raw_wan_sprite_names_are_presented_as_friendly_creation_dates():
    consumer_js = _read(WEB / "js" / "consumer_experience.js")
    playful_js = _read(WEB / "js" / "playful_console.js")

    assert "function friendlyCreationName(value)" in consumer_js
    assert "raw.match(/^wan_sprite_" in consumer_js
    assert "(?=_|$)" in consumer_js
    assert "created.toLocaleDateString" in consumer_js
    assert "created.toLocaleTimeString" in consumer_js
    assert "return `Character · ${dateLabel}, ${timeLabel}`" in consumer_js
    assert "window.friendlyCreationName = friendlyCreationName" in consumer_js
    assert "const displayName = friendlyCreationName(item.name)" in consumer_js
    assert "window.friendlyCreationName?.(latest.name)" in playful_js


def test_health_summary_is_a_progressive_disclosure_with_friendly_copy():
    index = _read(WEB / "index.html")
    consumer_js_files = sorted(path for path in (WEB / "js").glob("*.js") if "consumer" in path.stem.lower())
    assert consumer_js_files, "Missing consumer health-summary behavior"
    consumer_js = _read(consumer_js_files[0])

    toggle = _opening_tag(index, "button", "healthSummaryToggle")
    assert re.search(r"\baria-controls=[\"']healthSummaryPanel[\"']", toggle, re.IGNORECASE)
    assert re.search(r"\baria-expanded=[\"']false[\"']", toggle, re.IGNORECASE)
    assert "System ready" in index

    panel = re.search(
        r"<[^>]+\bid=[\"']healthSummaryPanel[\"'][^>]*>",
        index,
        re.IGNORECASE,
    )
    assert panel, "Missing health summary disclosure panel"
    assert re.search(r"\bhidden(?:\s|>|=)", panel.group(0), re.IGNORECASE)

    assert "healthSummaryToggle" in consumer_js
    assert "healthSummaryPanel" in consumer_js
    assert "aria-expanded" in consumer_js
    assert "status.disk?.ok" in consumer_js
    assert ">= 25" in consumer_js
    for friendly_label in ("Generation engine", "AI models", "Graphics", "Storage"):
        assert friendly_label in index or friendly_label in consumer_js


def test_guide_workflows_are_semantic_button_cards_with_core_copy():
    guide = _read(WEB / "components" / "guide.html")
    consumer_js_files = sorted(path for path in (WEB / "js").glob("*.js") if "consumer" in path.stem.lower())
    assert consumer_js_files, "Missing consumer workflow bindings"
    consumer_js = _read(consumer_js_files[0])

    for copy in (
        "What would you like to make?",
        "Create a character",
        "Animate existing art",
        "Turn a video into sprites",
    ):
        assert copy in guide

    for workflow in ("single", "pack", "convert"):
        button = re.search(
            rf"<button\b[^>]*\bdata-workflow=[\"']{workflow}[\"'][^>]*>",
            guide,
            re.IGNORECASE,
        )
        assert button, f"Workflow {workflow!r} must be a native button card"
        assert re.search(r"\btype=[\"']button[\"']", button.group(0), re.IGNORECASE)
        assert "home-action-card" in button.group(0)

    assert not re.search(r"<div\b[^>]*\bworkflow-card\b[^>]*\bonclick=", guide, re.IGNORECASE)
    assert "data-workflow" in consumer_js
    assert "openWizard" in consumer_js


def test_mobile_navigation_restores_and_traps_focus_and_closes_on_escape():
    mobile_js = _read(WEB / "js" / "mobile_nav.js")

    assert "document.activeElement" in mobile_js
    assert ".focus()" in mobile_js
    assert re.search(r"event\.key\s*(?:===|!==)\s*[\"']Tab[\"']", mobile_js)
    assert "event.shiftKey" in mobile_js
    assert "event.key === 'Escape'" in mobile_js or 'event.key === "Escape"' in mobile_js
    assert "aria-expanded" in mobile_js
    assert "aria-hidden" in mobile_js
    assert "mobileRailToggle" in mobile_js
    assert "button:not([disabled])" in mobile_js


def test_aaa_studio_keeps_core_creation_visible_and_hides_advanced_panels_in_simple_mode():
    accessibility = _read(WEB / "css" / "accessibility.css")
    consumer_css_files = sorted(path for path in WEB.rglob("*.css") if "consumer" in path.stem.lower())
    assert consumer_css_files, "Missing consumer progressive-disclosure styles"
    css = accessibility + "\n" + _read(consumer_css_files[0])
    simple_rules = [
        (selectors, body)
        for selectors, body in _css_rules(css)
        if "body.mode-simple" in selectors
    ]

    for advanced_selector in (".aaa-inspector-panel", ".aaa-tabs"):
        matching = [body for selectors, body in simple_rules if advanced_selector in selectors]
        assert matching, f"Simple mode must address {advanced_selector}"
        assert any(re.search(r"display\s*:\s*none\b", body) for body in matching)

    asset_rules = [body for selectors, body in simple_rules if ".aaa-assets-panel" in selectors]
    assert not any(re.search(r"display\s*:\s*none\b", body) for body in asset_rules), (
        "The document/asset panel is required for first-time creation and selection"
    )

    simple_tools = [body for selectors, body in simple_rules if ".aaa-simple-tools" in selectors]
    assert simple_tools, "Simple mode needs a compact, obvious AAA tool strip"
    assert any(
        re.search(r"display\s*:\s*(?:block|flex|grid|inline-flex|inline-grid)\b", body)
        for body in simple_tools
    )
