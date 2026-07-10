from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "app" / "web"


def read(relative: str) -> str:
    return (WEB / relative).read_text(encoding="utf-8")


def test_playful_console_assets_are_registered_in_runtime_architecture():
    index = read("index.html")
    loader = read("js/script_loader.js")
    js_manifest = read("js/js_architecture.json")
    css_manifest = read("css/css_architecture.json")

    assert 'css/playful_console.css?v=forge-guide-workshop' in index
    assert 'js/playful_console.js?v=forge-guide-workshop' in index
    assert 'js/playful_console.js?v=forge-guide-workshop' in loader
    assert 'js/playful_console.js?v=forge-guide-workshop' in js_manifest
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
