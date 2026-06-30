from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def test_editor_history_module_loaded_before_editor():
    index = (APP / "web" / "index.html").read_text(encoding="utf-8")

    history_pos = index.index("/web/js/editor_history.js")
    editor_pos = index.index("/web/js/editor.js")
    assert history_pos < editor_pos


def test_editor_history_is_bounded_and_reset_on_sprite_load():
    history = (APP / "web" / "js" / "editor_history.js").read_text(encoding="utf-8")
    editor = (APP / "web" / "js" / "editor.js").read_text(encoding="utf-8")

    assert "const MAX_HISTORY = 40" in history
    assert "if (undoStack.length > MAX_HISTORY) undoStack.shift()" in history
    assert "function wrapSpriteLoad()" in history
    assert "reset();" in history
    assert "SpriteForgeEditorHistory" in editor
    assert "let undoStack" not in editor
