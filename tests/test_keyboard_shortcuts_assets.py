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


def test_notification_drawer_open_close_state_and_escape_stay_synchronized():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    notifications = (WEB / "js" / "app_notifications.js").read_text(encoding="utf-8")
    shortcuts = (WEB / "js" / "keyboard_shortcuts.js").read_text(encoding="utf-8")

    assert 'class="notification-drawer hidden"' in html
    assert 'id="notificationDrawer" role="dialog"' in html
    assert "function setNotificationDrawer(open)" in notifications
    remove_hidden = notifications.index("drawer.classList.remove('hidden')")
    add_show = notifications.index("drawer.classList.add('show')")
    assert remove_hidden < add_show
    assert "drawer.classList.remove('show')" in notifications
    assert "drawer.classList.add('hidden')" in notifications
    assert "drawer.setAttribute('aria-hidden', 'false')" in notifications
    assert "drawer.setAttribute('aria-hidden', 'true')" in notifications
    assert "trigger?.setAttribute('aria-expanded', 'true')" in notifications
    assert "trigger?.setAttribute('aria-expanded', 'false')" in notifications
    assert "setNotificationDrawer(drawer.getAttribute('aria-hidden') !== 'false')" in notifications
    assert "key === 'escape'" in shortcuts
    assert "drawer?.getAttribute('aria-hidden') === 'false'" in shortcuts
    assert "window.setNotificationDrawer(false)" in shortcuts


def test_shortcut_cheat_sheet_styles_are_present():
    css = (WEB / "css" / "components_recipes_modal.css").read_text(encoding="utf-8")

    assert ".shortcut-cheat-sheet" in css
    assert ".shortcut-cheat-sheet-card" in css
    assert ".shortcut-cheat-sheet-grid kbd" in css
    assert "backdrop-filter: blur" in css
