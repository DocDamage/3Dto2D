import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "app" / "web"


def read(relative: str) -> str:
    return (WEB / relative).read_text(encoding="utf-8")


def css_at_rule_blocks(source: str, opening_pattern: str):
    """Yield balanced CSS at-rule bodies without depending on whitespace."""
    for match in re.finditer(opening_pattern, source):
        opening_brace = source.find("{", match.end())
        assert opening_brace >= 0, f"Missing block for {match.group(0)!r}"
        depth = 0
        for index in range(opening_brace, len(source)):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    yield source[opening_brace + 1:index]
                    break
        else:
            raise AssertionError(f"Unclosed block for {match.group(0)!r}")


def css_rule_body(source: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>[^{{}}]*)\}}", source, re.DOTALL)
    assert match, f"Missing CSS rule for {selector!r}"
    return match.group("body")


def test_playful_console_assets_are_registered_in_runtime_architecture():
    index = read("index.html")
    loader = read("js/script_loader.js")
    js_manifest = read("js/js_architecture.json")
    css_manifest = read("css/css_architecture.json")

    assert 'css/playful_console.css?v=console-product-polish-v12' in index
    assert 'js/playful_console.js?v=console-product-polish-v12' in index
    assert 'js/playful_console.js?v=console-product-polish-v12' in loader
    assert 'js/playful_console.js?v=console-product-polish-v12' in js_manifest
    assert 'css/playful_console.css' in css_manifest


def test_simple_creation_flow_is_visual_and_keeps_professional_escape_hatch():
    script = read("js/playful_console.js")
    styles = read("css/playful_console.css")

    assert "Who are we bringing to life?" in script
    assert "Choose a visual direction" in script
    assert "Pick the first moves" in script
    assert "Bring my character to life" in script
    assert 'id="simpleOpenPro"' in script
    assert "byId('proToolsToggle')?.click()" in script
    assert 'data-simple-quality="fast"' in script
    assert "styleField.value = CREATE_STYLES[initialStyle]" in script
    assert "#generateForm > :not(.consumer-create-flow)" in styles


def test_home_hero_offers_immediate_create_and_demo_actions():
    script = read("js/playful_console.js")

    for marker in (
        "actions.id = 'forgeHeroActions'",
        'id="forgeHeroStart"',
        "Start creating",
        'id="forgeHeroDemo"',
        "Try a demo",
    ):
        assert marker in script
    assert "heroCopy.insertBefore(actions, projectState || null)" in script
    assert "window.openWizard?.('single')" in script
    assert "SAFE_VIEWS.has('play_workbench')" in script
    assert "window.showView?.('play_workbench')" in script


def test_console_menu_tones_and_core_surfaces_support_spatial_navigation():
    script = read("js/playful_console.js")
    tones_match = re.search(
        r"const\s+MENU_TONES\s*=\s*Object\.freeze\s*\(\s*\{(?P<body>.*?)\}\s*\)",
        script,
        re.DOTALL,
    )
    assert tones_match, "MENU_TONES should remain a discoverable navigation palette"
    tones = tones_match.group("body")
    for view, tone in {
        "guide": "blue",
        "dashboard": "sun",
        "generate": "coral",
        "aaa_studio": "grape",
        "quality": "mint",
        "release": "blue",
        "setup": "neutral",
    }.items():
        assert re.search(rf"\b{view}\s*:\s*['\"]{tone}['\"]", tones)

    assert "nav.dataset.spatialNav = ''" in script
    assert "button.dataset.forgeTone = MENU_TONES[button.dataset.view] || 'neutral'" in script
    assert "surface.dataset.spatialNav = ''" in script
    for surface in (
        "home-action-grid",
        "forge-style-grid",
        "forge-move-grid",
        "forge-quality-grid",
        "forge-review-actions",
        "forge-export-targets",
    ):
        assert surface in script
    for generated_surface in (
        "forge-style-grid",
        "forge-move-grid",
        "forge-quality-grid",
        "forge-review-actions",
        "forge-export-targets",
    ):
        assert re.search(
            rf'class="[^"]*\b{generated_surface}\b[^"]*"\s+data-spatial-nav',
            script,
        )


def test_console_menu_includes_visual_control_hints():
    script = read("js/playful_console.js")
    styles = read("css/playful_console.css")

    assert "hints.id = 'forgeControlHints'" in script
    assert "hints.setAttribute('aria-label', 'Menu controls')" in script
    assert "<kbd>↑↓</kbd> Move" in script
    assert "<kbd>Enter</kbd> Choose" in script
    assert "footer.appendChild(hints)" in script
    assert re.search(r"\.forge-control-hints\s*\{[^{}]*display\s*:\s*flex", styles, re.DOTALL)
    assert ".forge-control-hints kbd" in styles


def test_compact_height_hero_hides_redundant_copy_but_keeps_actions():
    styles = read("css/playful_console.css")
    compact_blocks = list(css_at_rule_blocks(
        styles,
        r"@media\s*\(\s*min-width\s*:\s*761px\s*\)\s*and\s*\(\s*max-height\s*:\s*760px\s*\)",
    ))
    hero_block = next(
        (block for block in compact_blocks if "body.mode-simple .home-hero" in block),
        None,
    )
    assert hero_block, "Missing compact-height home hero treatment"
    hidden_copy = re.search(
        r"body\.mode-simple\s+\.home-hero-copy\s*>\s*p:not\(\.home-kicker\)\s*,\s*"
        r"body\.mode-simple\s+\.home-project-state\s*\{(?P<body>[^{}]*)\}",
        hero_block,
        re.DOTALL,
    )
    assert hidden_copy
    assert re.search(r"display\s*:\s*none", hidden_copy.group("body"))
    assert not re.search(
        r"\.forge-hero-actions[^{}]*\{[^{}]*display\s*:\s*none",
        hero_block,
        re.DOTALL,
    )
    assert re.search(r"\.forge-hero-actions\s*\{[^{}]*display\s*:\s*flex", styles, re.DOTALL)


def test_late_simple_cascade_keeps_dashboard_scrollable_and_review_tabs_hidden():
    index = read("index.html")
    styles = read("css/playful_console.css")

    assert index.index("styles.css") < index.index("css/playful_console.css")
    assert index.index("css/consumer_experience.css") < index.index("css/playful_console.css")
    desktop_blocks = list(css_at_rule_blocks(
        styles,
        r"@media\s*\(\s*min-width\s*:\s*761px\s*\)",
    ))
    dashboard_block = next(
        (block for block in desktop_blocks if "#view-dashboard.view.active" in block),
        None,
    )
    assert dashboard_block, "Missing late simple-mode Dashboard containment rules"

    dashboard_view = css_rule_body(dashboard_block, "body.mode-simple #view-dashboard.view.active")
    dashboard_panels = css_rule_body(dashboard_block, "body.mode-simple #view-dashboard .dashboard-tab-panels")
    active_panel = css_rule_body(dashboard_block, "body.mode-simple #view-dashboard .dashboard-tab-panel.active")
    assert re.search(r"flex\s*:\s*1\s+1\s+auto", dashboard_view)
    assert re.search(r"min-height\s*:\s*0", dashboard_view)
    assert re.search(r"overflow\s*:\s*hidden", dashboard_view)
    assert re.search(r"flex\s*:\s*1\s+1\s+auto", dashboard_panels)
    assert re.search(r"min-height\s*:\s*0", dashboard_panels)
    assert re.search(r"overflow\s*:\s*hidden", dashboard_panels)
    assert re.search(r"height\s*:\s*100%", active_panel)
    assert re.search(r"min-height\s*:\s*0", active_panel)
    assert re.search(r"overflow-y\s*:\s*auto", active_panel)

    review_tabs = re.search(
        r"body\.mode-simple\s+#view-quality\s+\.view-tabs\s*,\s*"
        r"body\.mode-simple\s+#view-quality-parent\s*>\s*\.view-tabs\s*"
        r"\{(?P<body>[^{}]*)\}",
        styles,
        re.DOTALL,
    )
    assert review_tabs, "Simple Review must hide both child and parent tab strips"
    assert re.search(r"display\s*:\s*none\s*!important", review_tabs.group("body"))


def test_forge_dock_stays_below_modals_and_hides_while_overlays_are_open():
    script = read("js/playful_console.js")
    playful_styles = read("css/playful_console.css")
    modal_styles = read("css/components_recipes_modal.css")

    dock_rule = css_rule_body(playful_styles, ".forge-guide-dock")
    modal_rule = css_rule_body(modal_styles, ".result-modal")
    dock_z = re.search(r"z-index\s*:\s*(\d+)", dock_rule)
    modal_z = re.search(r"z-index\s*:\s*(\d+)", modal_rule)
    assert dock_z and modal_z
    assert int(dock_z.group(1)) < int(modal_z.group(1))

    assert "document.body.classList.contains('mobile-rail-open')" in script
    assert "document.querySelectorAll('[role=\"dialog\"]')" in script
    assert "!dialog.hidden" in script
    assert "dialog.getAttribute('aria-hidden') !== 'true'" in script
    assert "const shouldHide = preferenceHidden || overlayIsOpen()" in script
    assert "dock.hidden = shouldHide" in script
    assert "function installOverlayWatcher()" in script
    assert "runtime.overlayObserver = new MutationObserver" in script
    assert re.search(
        r"new\s+MutationObserver\s*\(\s*mutations\s*=>\s*\{\s*syncCompanionVisibility\(\)",
        script,
        re.DOTALL,
    )
    for watched_attribute in ("'class'", "'hidden'", "'aria-hidden'"):
        assert watched_attribute in script


def test_reduced_motion_disables_the_simple_view_entrance():
    styles = read("css/playful_console.css")

    assert re.search(
        r"body\.mode-simple\s+\.shell\s*>\s*\.view\.active\s*\{[^{}]*"
        r"animation\s*:\s*forge-view-enter",
        styles,
        re.DOTALL,
    )
    reduced_blocks = list(css_at_rule_blocks(
        styles,
        r"@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)",
    ))
    assert reduced_blocks
    reduced_view_rule = re.search(
        r"body\.mode-simple\s+\.shell\s*>\s*\.view\.active\s*\{(?P<body>[^{}]*)\}",
        reduced_blocks[0],
        re.DOTALL,
    )
    assert reduced_view_rule
    assert re.search(r"animation\s*:\s*none\s*!important", reduced_view_rule.group("body"))
    assert re.search(r"transition\s*:\s*none\s*!important", reduced_view_rule.group("body"))
    assert re.search(
        r"body\.pref-reduce-motion\.mode-simple\s+\.shell\s*>\s*\.view\.active\s*"
        r"\{[^{}]*animation\s*:\s*none\s*!important",
        styles,
        re.DOTALL,
    )


def test_controller_and_keyboard_navigation_establish_fresh_focus():
    script = read("js/playful_console.js")

    assert "function focusConsoleDefault()" in script
    assert "const activeView = document.querySelector('.shell > .view.active')" in script
    for priority in (
        "[data-spatial-default]",
        "[data-simple-style][aria-pressed=\"true\"]",
        "[role=\"tab\"][aria-selected=\"true\"]",
        ".forge-review-actions .forge-primary-action",
        ".forge-export-targets [aria-pressed=\"true\"]",
        ".home-action-card.home-action-primary",
    ):
        assert priority in script
    assert "target.focus({ preventScroll: false })" in script
    assert "function consoleFocusIsIdle()" in script
    assert "return !overlayIsOpen() && (active === document.body || active === byId('mainContent'))" in script
    assert "if (!document.activeElement?.closest?.('[data-spatial-nav]')) focusConsoleDefault()" not in script
    assert "if (consoleFocusIsIdle()) focusConsoleDefault()" in script
    assert "if (repeatable && !spatialMove(name) && consoleFocusIsIdle()) focusConsoleDefault()" in script
    controller_loop = script[script.index("function syncControllerLoop()"):script.index("function bindGlobalFeedback()")]
    assert "focusConsoleDefault()" not in controller_loop
    assert "window.addEventListener('gamepadconnected'" in script


def test_companion_is_local_first_and_navigation_only():
    script = read("js/playful_console.js")

    assert "Local, project-aware help" in script
    assert "'/api/assistant/query'" in script
    assert "SAFE_VIEWS.has" in script
    assert "window.showView?.(view)" in script
    assert "window.runAction" not in script
    assert "retrieval uses approved local SpriteForge documentation" in script


def test_delight_preferences_are_opt_in_and_accessibility_aware():
    script = read("js/playful_console.js")
    styles = read("css/playful_console.css")

    assert "preference(PREFS.sound, 'off')" in script
    assert "prefers-reduced-motion: reduce" in script
    assert "prefers-reduced-motion: reduce" in styles
    assert "UI sounds" in script
    assert "Gentle haptics" in script
    assert "Controller navigation" in script
    assert "navigator.getGamepads" in script
    assert "Optional embedded language model" in script
    assert "'/api/assistant/settings'" in script
    assert "Loopback endpoint" in script
    assert "gamepadPressed" in script
    assert "!wasActive || (repeatable" in script
    assert "timeout_seconds: 12" not in script
    assert "body.mode-simple .rail nav" in styles
    assert ".forge-primary-action small { color: #071226" in styles


def test_workshop_progress_and_friendly_review_export_are_present():
    script = read("js/playful_console.js")

    for stage in ("Sketching", "Animating", "Polishing", "Packing"):
        assert stage in script
    for verdict in ("Motion", "Loop", "Silhouette"):
        assert verdict in script
    for target in ("Godot", "Unity", "Unreal", "Images", "Web"):
        assert f">{target}<" in script


def test_retro_palette_labels_use_original_descriptive_language():
    generate = read("components/generate.html")
    convert = read("components/convert.html")

    for source in (generate, convert):
        assert ">Olive 4-tone<" in source
        assert ">Classic 54-color<" in source
        assert ">Game Boy<" not in source
        assert ">NES<" not in source
