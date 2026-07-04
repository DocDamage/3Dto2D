from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def test_frame_editor_assets_are_loaded():
    index = (WEB / "index.html").read_text(encoding="utf-8")

    assert "frame_editor.css" in index
    assert "'frame_editor'" in index
    assert 'id="view-frame_editor"' in index
    assert 'data-view="frame_editor"' in index
    assert "js/frame_editor.js" in index


def test_frame_editor_component_and_js_wire_repack_endpoint():
    html = (WEB / "components" / "frame_editor.html").read_text(encoding="utf-8")
    js = (WEB / "js" / "frame_editor.js").read_text(encoding="utf-8")

    for marker in [
        'id="frameEditorSpriteSelect"',
        'id="frameEditorDropZone"',
        'id="frameEditorRepackBtn"',
        'id="frameEditorDuration"',
        'id="frameEditorDurationHint"',
        'id="frameEditorMoveLeftBtn"',
        'id="frameEditorMoveRightBtn"',
    ]:
        assert marker in html
    assert "/api/repack-sheet" in js
    assert "dragstart" in js
    assert "source_index" in js
    assert "duration_ms" in js
    assert "selectedIndices" in js
    assert "shiftKey" in js
    assert "selectedTimelineIndices" in js
    assert "function moveSelected" in js
    assert "frameEditorMoveLeftBtn" in js
    assert "frameEditorMoveRightBtn" in js
    assert "frame-editor-duration-badge" in js
    assert "selected.forEach(index" in js
    assert "Applies to ${selected.length} selected frames" in js
    assert "retimed" in js
    css = (WEB / "frame_editor.css").read_text(encoding="utf-8")
    assert ".frame-editor-duration-badge" in css
    assert ".frame-editor-tile.retimed" in css
    assert ".frame-editor-duration-hint" in css
    assert "Shift-click multi" in html
