from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def test_dashboard_exposes_architecture_status_card():
    dashboard = (WEB / "components" / "dashboard.html").read_text(encoding="utf-8")
    app_dashboard = (WEB / "js" / "app_dashboard.js").read_text(encoding="utf-8")

    assert 'id="architectureStatusCard"' in dashboard
    assert 'id="architectureStatusBadge"' in dashboard
    assert 'id="architectureStatusList"' in dashboard
    assert "function renderArchitectureStatus" in app_dashboard
    assert "renderArchitectureStatus(s.architecture, s)" in app_dashboard
    assert "function cacheFreshnessText" in app_dashboard
    assert "GPU status" in app_dashboard
    assert "Model status" in app_dashboard
    assert "Disk status" in app_dashboard
    assert "_cache" in app_dashboard
    assert "function notifyDashboardCompletionEvents" in app_dashboard
    assert "Notification.requestPermission()" in app_dashboard
    assert "new Notification(title" in app_dashboard
    assert "Job runner boundary" in app_dashboard
    assert "Status performance caches" in app_dashboard
    assert "Design system tokens" in app_dashboard
    assert "Core pipeline power-ups" in app_dashboard
    assert "Keyboard-first UX" in app_dashboard
    assert "Dashboard & Generate UX" in app_dashboard
    assert "Sprite route hardening" in app_dashboard
    assert "Test suite fixtures" in app_dashboard
    assert "Easy Mode modernization" in app_dashboard
    assert "Plugin SDK readiness" in app_dashboard
    assert "Cloud Hub dispatch" in app_dashboard
    assert "Cloud image generation" in app_dashboard
    assert "QA Advisor learning" in app_dashboard
    assert "Tilemap exports" in app_dashboard
    assert "Skeletal exports" in app_dashboard
    assert "Archetype cards" in app_dashboard
    assert "LoRA training UX" in app_dashboard
    assert "Scene compositor" in app_dashboard
    assert "N-way compare player" in app_dashboard
    assert "Palette pipeline" in app_dashboard
    assert "Animated exports" in app_dashboard
    assert "Roadmap phases" in app_dashboard
