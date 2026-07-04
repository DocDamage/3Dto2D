from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "app" / "web"


def test_quality_lab_uses_left_accordion_workbench():
    html = (WEB / "components" / "quality.html").read_text(encoding="utf-8")

    assert 'class="quality-workbench"' in html
    assert 'class="quality-left-rail"' in html
    assert 'class="quality-right-stage"' in html
    assert 'class="quality-accordion"' in html
    assert "Sprite source" in html
    assert "Inspector display" in html
    assert "Metrics and alerts" in html
    assert 'class="button-row compact-actions quality-primary-actions"' in html


def test_quality_lab_keeps_deep_tools_collapsed_by_default():
    html = (WEB / "components" / "quality.html").read_text(encoding="utf-8")

    assert "<summary>Playback and edits</summary>" in html
    assert '<details class="quality-accordion" open>\n          <summary>Playback and edits</summary>' not in html


def test_quality_lab_has_inline_live_preview_targets():
    html = (WEB / "components" / "quality.html").read_text(encoding="utf-8")

    assert 'id="qualityLivePreview"' in html
    assert 'id="qualityLiveVideoSlot"' in html
    assert 'id="qualityLiveSpriteSlot"' in html
    assert 'id="qualityLivePreviewStatus"' in html
    assert 'data-quality-panel-action="fullscreen"' in html
    assert 'data-quality-panel-action="popout"' in html


def test_quality_lab_css_bounds_page_height_and_right_column():
    css = (WEB / "css" / "inspector_ab_compare.css").read_text(encoding="utf-8")

    assert ".quality-workbench" in css
    assert "grid-template-columns: minmax(390px, 470px) minmax(0, 1fr)" in css
    assert ".quality-left-rail" in css
    assert "height: clamp(560px, calc(100vh - 170px), 760px)" in css
    assert "overflow-y: auto" in css
    assert "scrollbar-gutter: stable" in css
    assert ".quality-right-stage" in css
    assert "overflow-y: hidden" in css
    assert "grid-template-rows: minmax(0, auto) minmax(0, 1fr)" in css
    assert ".inspector-controls" in css
    assert "width: auto" in css
    assert "#qualityDropTarget" in css
    assert "min-height: 44px" in css
    assert ".quality-primary-actions" in css
    assert ".quality-left-rail .inspector-controls" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css
    assert ".quality-left-rail .palette-harmonizer" in css
    assert "height: clamp(150px, 24vh, 230px)" in css
    assert ".quality-popoutable:fullscreen" in css
    assert ".quality-panel-expanded" in css
    assert ".quality-workbench:has(.quality-panel-expanded)" in css


def test_quality_lab_shell_removes_page_scroll_and_compacts_task_strip():
    css = (WEB / "css" / "inspector_ab_compare.css").read_text(encoding="utf-8")

    assert "@media (min-width: 1081px)" in css
    assert 'body[data-active-parent-view="quality-parent"]' in css
    assert "overflow: hidden" in css
    assert 'body[data-active-parent-view="quality-parent"] .global-task-progress' in css
    assert "width: min(430px, 46vw)" in css
    assert 'body[data-active-parent-view="quality-parent"] #view-quality-parent .view-tabs' in css
    assert "margin-right: min(450px, calc(46vw + 18px))" in css


def test_quality_lab_js_wires_immediate_preview_from_sprite_input():
    js = (WEB / "js" / "qa.js").read_text(encoding="utf-8")

    assert "initQualityLivePreview" in js
    assert "refreshQualityLivePreview" in js
    assert "qualitySpriteDir" in js
    assert "addEventListener('input'" in js
    assert "/api/sprite/preview?path=" in js
    assert "initQualityPanelActions" in js
    assert "openQualityPanelPopout" in js
    assert "requestFullscreen" in js
    assert "quality-panel-expanded" in js


def test_palette_harmonizer_injects_as_collapsed_quality_accordion():
    js = (WEB / "js" / "palette_harmonizer.js").read_text(encoding="utf-8")

    assert "card quality-control-panel palette-harmonizer" in js
    assert '<details class="quality-accordion">' in js
    assert "<summary>Palette harmonizer</summary>" in js
    assert "Run palette harmonizer" in js


def test_frame_review_injects_as_collapsed_quality_accordion():
    js = (WEB / "js" / "frame_review.js").read_text(encoding="utf-8")

    assert "quality-accordion frame-review-accordion" in js
    assert "<summary>Frame approval</summary>" in js
    assert "inspectorAccordion.insertAdjacentElement('afterend', reviewAccordion)" in js
