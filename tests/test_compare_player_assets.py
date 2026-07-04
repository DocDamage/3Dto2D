from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def test_compare_player_assets_are_loaded():
    index = (WEB / "index.html").read_text(encoding="utf-8")

    assert "compare_player.css" in index
    assert "'compare_player'" in index
    assert 'id="view-compare_player"' in index
    assert 'data-view="compare_player"' in index
    assert "js/compare_player.js" in index
    assert "refreshComparePlayerSprites" in (WEB / "js" / "globals.js").read_text(encoding="utf-8")


def test_compare_player_component_has_expected_controls():
    html = (WEB / "components" / "compare_player.html").read_text(encoding="utf-8")

    for marker in [
        'id="compareSpriteA"',
        'id="compareSpriteB"',
        'id="compareSpriteC"',
        'id="compareSpriteD"',
        'id="comparePlayBtn"',
        'id="compareFrameScrubber"',
        'id="compareDiffCanvas"',
        'id="compareDiffToggle"',
        'id="comparePickWinnerBtn"',
        'id="compareVariantGrid"',
        'id="compareMetricsBody"',
        'id="compareMetricsStatus"',
    ]:
        assert marker in html


def test_compare_player_js_uses_preview_api_sync_diff_and_winner_flow():
    js = (WEB / "js" / "compare_player.js").read_text(encoding="utf-8")
    experiments = (WEB / "js" / "experiments.js").read_text(encoding="utf-8")

    assert "/api/sprite/preview?path=" in js
    assert "requestAnimationFrame(tick)" in js
    assert "renderDiff" in js
    assert "changed pixels" in js
    assert "renderMetricsTable" in js
    assert "variantQaMetric" in js
    assert "loop_rmse" in js
    assert "selected winner" in js
    assert "compare-metrics-winner" in js
    assert "/api/experiments/pick-winner" in js
    assert "/api/experiments/star" in js
    assert "compared_sprites" in js
    assert "window.setComparePlayerSelection" in js
    assert "showView('compare_player')" in experiments
    assert "setComparePlayerSelection(selected)" in experiments


def test_compare_player_styles_are_present():
    css = (WEB / "compare_player.css").read_text(encoding="utf-8")

    assert ".compare-player-controls" in css
    assert ".compare-variant-grid" in css
    assert ".compare-diff-card" in css
    assert ".compare-metrics-table" in css
    assert ".compare-metrics-winner" in css
    assert "image-rendering: pixelated" in css
