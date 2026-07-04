from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def test_command_palette_renders_shortcut_metadata():
    js = (WEB / "js" / "command_palette.js").read_text(encoding="utf-8")

    assert "cmd.shortcut" in js
    assert "shortcutTag.textContent = cmd.shortcut" in js
    assert "cmd-meta-tag" in js
    assert "cmd.endpoint" in js
    assert "haystack.includes" in js
