from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def test_dashboard_activity_feed_assets_are_wired():
    html = (APP / "web" / "components" / "dashboard.html").read_text(encoding="utf-8")
    js = (APP / "web" / "js" / "app_dashboard.js").read_text(encoding="utf-8")
    css = (APP / "web" / "css" / "components.css").read_text(encoding="utf-8")

    assert 'id="dashboardActivityFeed"' in html
    assert 'id="refreshDashboardEvents"' in html
    assert "refreshDashboardActivityFeed" in js
    assert "/api/progress/events?after=" in js
    assert "new EventSource('/api/progress/stream')" in js
    assert "dashboardActivityFallbackTimer" in js
    assert "dashboardActivitySource.onerror" in js
    assert "setInterval(refreshDashboardActivityFeed, 5000)" in js
    assert "startDashboardActivityFeed" in js
    assert "renderDashboardActivitySkeleton" in js
    assert "skeleton-card" in js
    assert "dashboardEventSummary" in js
    assert ".dashboard-activity-feed" in css
    assert ".dashboard-activity-event" in css


def test_dashboard_hero_stats_assets_are_wired():
    html = (APP / "web" / "components" / "dashboard.html").read_text(encoding="utf-8")
    js = (APP / "web" / "js" / "app_dashboard.js").read_text(encoding="utf-8")
    css = (APP / "web" / "css" / "components.css").read_text(encoding="utf-8")

    assert 'class="dashboard-hero-stats"' in html
    assert 'id="dashboardStatSprites"' in html
    assert 'id="dashboardStatQa"' in html
    assert 'id="dashboardStatProject"' in html
    assert 'id="dashboardStatDisk"' in html
    assert "function renderDashboardHeroStats" in js
    assert "renderDashboardHeroStats(s)" in js
    assert "qa_score" in js
    assert ".dashboard-stat-card" in css
