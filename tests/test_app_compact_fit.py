from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "app" / "web"


def test_compact_fit_and_resizer_stylesheets_are_loaded_last():
    styles = (WEB / "styles.css").read_text(encoding="utf-8")
    index = (WEB / "index.html").read_text(encoding="utf-8")

    imports = [line for line in styles.splitlines() if line.startswith("@import")]
    assert imports[-2] == '@import url("css/app_compact_fit.css");'
    assert imports[-1] == '@import url("css/app_resizers.css");'
    assert '/web/styles.css?v=dashboard-fit-no-window-resize' in index
    assert "name === 'dashboard' ? '?v=dashboard-fit-no-window-resize'" in index
    assert '/web/js/app_dashboard.js?v=dashboard-fit-no-window-resize' in index


def test_compact_fit_locks_desktop_shell_to_viewport():
    css = (WEB / "css" / "app_compact_fit.css").read_text(encoding="utf-8")

    assert "@media (min-width: 761px)" in css
    assert "height: 100%" in css
    assert "overflow: hidden" in css
    assert "position: fixed !important" in css
    assert ".shell" in css
    assert "height: 100vh" in css
    assert "width: calc(100vw - 262px)" in css
    assert ".view.active" in css
    assert "max-height: calc(100vh - 112px)" in css


def test_compact_fit_covers_modals_wizard_tables_and_lists():
    css = (WEB / "css" / "app_compact_fit.css").read_text(encoding="utf-8")

    assert ".result-dialog" in css
    assert "max-height: calc(100vh - 16px)" in css
    assert ".wizard-body" in css
    assert "min-height: 0 !important" in css
    assert ".table-scroll" in css
    assert ".release-list" in css
    assert ".queue-list" in css
    assert "#archetypesGrid" in css
    assert "#notificationList" in css


def test_training_lab_uses_tab_panel_scroll_instead_of_clipping():
    css = (WEB / "css" / "app_compact_fit.css").read_text(encoding="utf-8")

    assert "#view-training.view.active" in css
    assert "#view-training .training-tab-panels" in css
    assert "#view-training .training-tab-panel.active" in css
    assert "overflow-y: auto" in css


def test_dashboard_uses_compact_tabs_instead_of_one_tall_stack():
    html = (WEB / "components" / "dashboard.html").read_text(encoding="utf-8")
    js = (WEB / "js" / "app_dashboard.js").read_text(encoding="utf-8")
    css = (WEB / "css" / "app_compact_fit.css").read_text(encoding="utf-8")

    assert 'data-dashboard-tab="overview"' in html
    assert 'data-dashboard-tab="activity"' in html
    assert 'data-dashboard-tab="workspace"' in html
    assert 'data-dashboard-panel="overview"' in html
    assert 'data-dashboard-panel="activity"' in html
    assert 'data-dashboard-panel="workspace"' in html
    assert "projectDashboardEmpty" in html
    assert "activateDashboardTab" in js
    assert "#view-dashboard.view.active" in css
    assert "#view-dashboard .dashboard-tab-panels" in css
    assert "#view-dashboard .dashboard-tab-panel.active" in css
    assert "#view-dashboard .dashboard-activity-grid" in css
    assert "overflow-y: auto" in css


def test_app_resizer_layer_covers_panels_and_cards_without_full_window_handles():
    css = (WEB / "css" / "app_resizers.css").read_text(encoding="utf-8")

    assert "@media (min-width: 761px)" in css
    assert "--resize-card-min-w" in css
    assert "container-type: inline-size" in css
    assert "max-block-size: calc(100vh - 16px)" in css
    assert "max-inline-size: calc(100vw - 16px)" in css
    assert "max-height: calc(100vh - 16px) !important" in css
    assert "max-width: calc(100vw - 16px) !important" in css
    assert "min-height: min(360px, calc(100vh - 24px)) !important" in css
    assert "#view-quality .quality-right-stage .inspector-card" in css
    assert "#view-training .training-tab-panel.active" in css
    assert "overflow: auto !important" in css
    assert "resize: both" in css
    assert "resize: vertical" in css
    assert "resize: none !important" in css
    assert "@container (max-width: 520px)" in css
    assert "grid-template-columns: 1fr !important" in css
    assert ".card" in css
    assert ".quality-left-rail" in css
    assert ".quality-right-stage" in css
    assert ".result-dialog" in css
    assert ".wizard-container" in css
    assert ".command-palette-dialog" in css
    assert ".notification-drawer" in css
    assert ".training-tab-panel.active" in css
    assert ".terminal" in css
    assert ".result-dialog::after" not in css
    assert ".wizard-container::after" not in css
    assert ".command-palette-dialog::after" not in css
    assert ".notification-drawer::after" not in css
    assert ".wizard-container,\n  .result-dialog {\n    resize: both" not in css
