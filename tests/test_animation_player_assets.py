from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
WEB = APP / "web"


def test_animation_player_assets_are_loaded():
    index = (WEB / "index.html").read_text(encoding="utf-8")

    assert "animation_player.css" in index
    assert "'animation_player'" in index
    assert 'id="view-animation_player"' in index
    assert 'data-view="animation_player"' in index
    assert "js/animation_player.js" in index


def test_animation_player_component_has_expected_controls():
    html = (WEB / "components" / "animation_player.html").read_text(encoding="utf-8")

    for marker in [
        'id="animationSpriteSelect"',
        'id="animationCanvas"',
        'id="animationPlayBtn"',
        'id="animationFrameScrubber"',
        'id="animationHitFrameLegend"',
        'id="animationBackgroundSelect"',
        'value="custom"',
        'id="animationCustomBackgroundInput"',
        'id="animationOnionSlider"',
        'id="animationExportWebmBtn"',
        'id="animationExportStatus"',
    ]:
        assert marker in html


def test_animation_player_js_uses_sprite_preview_api_and_canvas_timing():
    js = (WEB / "js" / "animation_player.js").read_text(encoding="utf-8")
    globals_js = (WEB / "js" / "globals.js").read_text(encoding="utf-8")

    assert "/api/sprite/preview?path=" in js
    assert "requestAnimationFrame(tick)" in js
    assert "drawImage(state.sheet" in js
    assert "captureStream" in js
    assert "MediaRecorder.isTypeSupported" in js
    assert "video/webm;codecs=vp9" in js
    assert "WebM recording is not supported by this browser" in js
    assert "ClipboardItem" in js
    assert "downloadCanvasPng" in js
    assert "Clipboard unavailable; downloaded current frame as PNG" in js
    assert "Recording WebM preview" in js
    assert "backgroundImageUrl" in js
    assert "applyBackgroundSelection" in js
    assert "function hitFrameLabel" in js
    assert "dataset.hitFrame" in js
    css = (WEB / "animation_player.css").read_text(encoding="utf-8")
    assert "bg-custom" in css
    assert ".animation-tick.hit-frame" in css
    assert "refreshAnimationPlayerSprites" in globals_js
