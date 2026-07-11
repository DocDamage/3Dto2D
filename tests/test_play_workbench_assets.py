from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def test_play_workbench_assets_are_wired_into_the_app_shell():
    index = (WEB / "index.html").read_text(encoding="utf-8")
    component_loader = (WEB / "js" / "component_loader.js").read_text(encoding="utf-8")
    script_loader = (WEB / "js" / "script_loader.js").read_text(encoding="utf-8")
    ux = (WEB / "js" / "ux_enhancements.js").read_text(encoding="utf-8")

    assert "play_workbench.css" in index
    assert '"play_workbench"' in index
    assert "'play_workbench'" in component_loader
    assert "js/play_workbench.js" in script_loader
    assert 'data-view="play_workbench"' in index
    assert 'id="view-play_workbench"' in index
    assert "play_workbench: 'Play Workbench'" in ux
    assert "'tasks', 'play_workbench', 'animation_player'" in ux


def test_play_workbench_component_exposes_playable_accessible_controls():
    html = (WEB / "components" / "play_workbench.html").read_text(encoding="utf-8")

    for marker in [
        'id="playWorkbenchSpriteSelect"',
        'id="playWorkbenchCanvas"',
        'role="application"',
        'tabindex="0"',
        'data-workbench-clip="idle"',
        'data-workbench-clip="walk"',
        'data-workbench-clip="attack"',
        'id="playWorkbenchGamepadToggle"',
        'aria-live="polite"',
        "WASD",
    ]:
        assert marker in html


def test_play_workbench_uses_latest_demo_and_missing_asset_fallbacks():
    js = (WEB / "js" / "play_workbench.js").read_text(encoding="utf-8")
    css = (WEB / "play_workbench.css").read_text(encoding="utf-8")

    for marker in [
        "/api/outputs",
        "/api/sprite/preview?path=",
        "output/demo_sprite_no_gpu",
        "preferredPath",
        "window.loadPlayWorkbenchDemo",
        "buildClipMap",
        "loadImage",
        "image.onerror",
        "useSafeFallback",
        "drawFallbackSprite",
        "context.drawImage",
        "requestAnimationFrame(frameLoop)",
        "navigator.getGamepads",
        "gamepadconnected",
        "ArrowLeft",
        "KeyW",
        "Space",
    ]:
        assert marker in js

    assert "image-rendering: pixelated" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
