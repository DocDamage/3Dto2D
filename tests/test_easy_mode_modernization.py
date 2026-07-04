import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_easy_mode_exposes_web_studio_handoff():
    from services.easy_helpers import web_studio_url

    ui_source = (APP / "services" / "easy_ui_mixin.py").read_text(encoding="utf-8")
    actions_source = (APP / "services" / "easy_actions_mixin.py").read_text(encoding="utf-8")

    assert web_studio_url() == "http://127.0.0.1:7860"
    assert "def open_web_studio" in actions_source
    assert '"spriteforge_unified.py", "web"' in actions_source
    assert "Open Web Studio" in ui_source


def test_easy_mode_declares_keep_and_polish_option():
    ui_source = (APP / "services" / "easy_ui_mixin.py").read_text(encoding="utf-8")
    easy_source = (APP / "spriteforge_easy.py").read_text(encoding="utf-8")
    utils_source = (APP / "spriteforge_utils.py").read_text(encoding="utf-8")

    assert "tk.Tk" in easy_source
    assert "Easy Mode modernization: Option A active" in ui_source
    assert "apply_dark_theme(self)" in easy_source
    assert "def apply_dark_theme" in utils_source
    assert 'style.theme_use("clam")' in utils_source


def test_easy_mode_has_header_progress_bar_and_parser_hook():
    ui_source = (APP / "services" / "easy_ui_mixin.py").read_text(encoding="utf-8")
    helper_source = (APP / "services" / "easy_helpers.py").read_text(encoding="utf-8")

    assert "self.progress_bar = ttk.Progressbar" in ui_source
    assert "parse_progress_percent" in ui_source
    assert "def parse_progress_percent" in helper_source


def test_easy_mode_has_embedded_sprite_preview():
    ui_source = (APP / "services" / "easy_ui_mixin.py").read_text(encoding="utf-8")
    actions_source = (APP / "services" / "easy_actions_mixin.py").read_text(encoding="utf-8")
    helper_source = (APP / "services" / "easy_helpers.py").read_text(encoding="utf-8")

    assert "recent_preview_label" in ui_source
    assert "Select an output to preview" in ui_source
    assert "def load_sprite_preview" in helper_source
    assert "preview.gif" in helper_source
    assert "self.recent_preview_label.configure" in actions_source
