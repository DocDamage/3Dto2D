from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def test_shortcut_cheat_sheet_modal_is_present():
    html = (WEB / "index.html").read_text(encoding="utf-8")

    assert 'id="shortcutCheatSheet"' in html
    assert 'id="shortcutCheatSheetTitle"' in html
    assert "Shortcut cheat sheet" in html
    assert "data-shortcut-help-close" in html
    assert "<kbd>Ctrl</kbd><kbd>E</kbd>" in html
    assert "<kbd>Ctrl</kbd><kbd>Q</kbd>" in html


def test_keyboard_shortcuts_cover_phase_24_requirements():
    js = (WEB / "js" / "keyboard_shortcuts.js").read_text(encoding="utf-8")

    assert "Alt+ArrowLeft" in js
    assert "key >= '1' && key <= '9'" in js
    assert "function primaryShortcutViews" in js
    assert "$$('.rail nav .nav')" in js
    assert "runExportShortcut" in js
    assert "ctrlKey || event.metaKey) && key === 'e'" in js
    assert "ctrlKey || event.metaKey) && key === 'q'" in js
    assert "key === '?' || (event.shiftKey && key === '/')" in js
    assert "toggleShortcutHelp" in js
    assert "#animationPlayBtn" in js
    assert "#animationFrameScrubber" in js
    assert "[data-quality=\"godot\"]" in js
    assert "view === 'release' && submitForm('#releaseForm')" in js
    assert "['quality', 'animation_player'].includes(activeViewName())" in js
    assert "window.SpriteForgeShortcuts" in js


def test_shortcut_cheat_sheet_styles_are_present():
    css = (WEB / "css" / "components_recipes_modal.css").read_text(encoding="utf-8")

    assert ".shortcut-cheat-sheet" in css
    assert ".shortcut-cheat-sheet-card" in css
    assert ".shortcut-cheat-sheet-grid kbd" in css
    assert "backdrop-filter: blur" in css
