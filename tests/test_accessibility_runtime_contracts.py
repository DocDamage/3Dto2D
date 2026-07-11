from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def test_topbar_controls_and_announcements_have_accessible_names():
    index = (WEB / "index.html").read_text(encoding="utf-8")
    generate = (WEB / "components" / "generate.html").read_text(encoding="utf-8")

    assert 'class="status-row" role="status" aria-live="polite"' in index
    assert 'id="projectNameInput" placeholder="New project name" aria-label="New project name"' in index
    assert 'id="toast" class="toast" role="status" aria-live="polite"' in index
    assert 'id="advisorQuality" aria-label="Recommendation quality"' in generate


def test_mobile_layout_stacks_project_controls_and_uses_touch_targets():
    mobile = (WEB / "mobile_nav.css").read_text(encoding="utf-8")
    topbar = (WEB / "css" / "topbar_compact.css").read_text(encoding="utf-8")
    accessibility = (WEB / "css" / "accessibility.css").read_text(encoding="utf-8")

    assert ".project-strip" in mobile and "grid-template-columns: 1fr" in mobile
    assert "flex-wrap: wrap !important" in topbar
    assert "min-height: 44px" in accessibility
