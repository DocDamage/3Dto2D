from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def test_frontend_health_helpers_use_distinct_names():
    dashboard = (APP / "web" / "js" / "app_dashboard.js").read_text(encoding="utf-8")
    status = (APP / "web" / "js" / "app_status.js").read_text(encoding="utf-8")
    main = (APP / "web" / "js" / "app_main.js").read_text(encoding="utf-8")

    assert "function updateHealthDots" in dashboard
    assert "function updateHealthProgress" in status
    assert "function updateHealthBar" not in dashboard
    assert "function updateHealthBar" not in status
    assert "updateHealthDots(s)" in main
