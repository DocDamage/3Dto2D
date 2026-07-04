import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def test_rate_limit_helper_blocks_after_threshold():
    from services.rate_limit_service import check_rate_limit, reset_rate_limits
    from spriteforge_web import app

    reset_rate_limits()
    app.config["TESTING"] = True
    with app.test_request_context("/api/test", environ_base={"REMOTE_ADDR": "1.2.3.4"}):
        assert check_rate_limit("unit", limit=2, window_seconds=60)[0] is True
        assert check_rate_limit("unit", limit=2, window_seconds=60)[0] is True
        ok, remaining, retry_after = check_rate_limit("unit", limit=2, window_seconds=60)

    assert ok is False
    assert remaining == 0
    assert retry_after > 0


def test_sprite_save_metadata_route_is_rate_limited(tmp_path, monkeypatch):
    from services import rate_limit_service as rl
    import web_helpers as web_mod
    from spriteforge_web import app

    sprite_dir = tmp_path / "output" / "hero"
    sprite_dir.mkdir(parents=True)
    (sprite_dir / "sheet.json").write_text(json.dumps({"frame_count": 1}), encoding="utf-8")
    monkeypatch.setattr(web_mod, "ROOT", tmp_path)
    monkeypatch.setattr(web_mod, "OUTPUT", tmp_path / "output")
    rl.reset_rate_limits()
    monkeypatch.setattr(rl, "check_rate_limit", lambda scope, limit=30, window_seconds=60: (False, 0, 12.5))

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.post(
            "/api/sprite/save_metadata",
            data=json.dumps({"path": "output/hero", "metadata": {"frame_count": 2}}),
            content_type="application/json",
        )

    assert response.status_code == 429
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is False
    assert "Too many requests" in data["message"]
    assert response.headers["Retry-After"]


def test_rate_limiter_does_not_block_safe_get_routes(monkeypatch):
    from services import rate_limit_service as rl
    from spriteforge_web import app

    monkeypatch.setattr(rl, "check_rate_limit", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("GET should bypass limiter")))

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/outputs")

    assert response.status_code == 200


def test_destructive_sprite_routes_are_annotated():
    routes = (APP / "web_routes" / "routes_sprites.py").read_text(encoding="utf-8")

    for marker in [
        'route_rate_limited("sprite_version_rollback"',
        'route_rate_limited("sprite_save_metadata"',
        'route_rate_limited("sprite_edit_frames"',
        'route_rate_limited("sprite_repack_sheet"',
        'route_rate_limited("sprite_frame_status"',
        'route_rate_limited("sprite_palette_harmonize"',
        'route_rate_limited("sprite_audio_cue_write"',
        'route_rate_limited("sprite_frame_save"',
    ]:
        assert marker in routes
