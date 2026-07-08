from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def test_migrated_routes_use_shared_error_boundary():
    route_files = [
        APP / "web_routes" / "routes_misc.py",
        APP / "web_routes" / "routes_pixel_asset.py",
        APP / "web_routes" / "routes_projects.py",
        APP / "web_routes" / "routes_sprites.py",
        APP / "web_routes" / "routes_jobs.py",
    ]

    for path in route_files:
        source = path.read_text(encoding="utf-8")
        assert "api_exception_response" in source
        assert '{"error": str(exc)}' not in source
        assert '{"ok": False, "message": str(exc)}' not in source


def test_job_routes_only_log_sse_internal_exceptions_directly():
    source = (APP / "web_routes" / "routes_jobs.py").read_text(encoding="utf-8")
    assert 'logging.getLogger("routes_jobs").debug' in source
    assert 'return jsonify({"error": str(exc)}' not in source
    assert 'return jsonify({"ok": False, "message": str(exc)}' not in source
