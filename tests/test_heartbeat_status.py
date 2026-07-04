import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def test_heartbeat_api_is_lightweight():
    from spriteforge_web import app

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/heartbeat")

    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert "comfy_running" in data
    assert "job" in data
    assert "time" in data
    assert "models" not in data
    assert "outputs" not in data
    assert "cleanup_suggestions" not in data


def test_status_api_keeps_full_diagnostics():
    from spriteforge_web import app

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/status")

    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert "models" in data
    assert "disk" in data
    assert "outputs" in data
    assert "cleanup_suggestions" in data


def test_frontend_polling_uses_heartbeat_not_full_status():
    js = (WEB / "js" / "app_main.js").read_text(encoding="utf-8")

    assert "async function refreshHeartbeat" in js
    assert "api('/api/heartbeat')" in js
    assert "setInterval(refreshHeartbeat, interval)" in js
    assert "const s = await api('/api/status' + projectQuery())" in js


def test_gpu_and_model_summaries_are_ttl_cached(monkeypatch):
    from services.comfy_service import ComfyService
    from services.model_service import ModelService

    ComfyService.reset_caches()
    ModelService.reset_caches()
    calls = {"which": 0, "tiers": 0, "disk": 0}

    monkeypatch.setattr("services.comfy_service.shutil.which", lambda _name: calls.__setitem__("which", calls["which"] + 1) or None)
    monkeypatch.setattr(ModelService, "get_tiers_status", staticmethod(lambda: calls.__setitem__("tiers", calls["tiers"] + 1) or {
        "wan21_safe": {"ok": True, "present": 1, "total": 1, "label": "Safe"}
    }))
    monkeypatch.setattr("services.model_service.shutil.disk_usage", lambda _root: calls.__setitem__("disk", calls["disk"] + 1) or (100, 40, 60))

    first_gpu = ComfyService.get_gpu_info()
    second_gpu = ComfyService.get_gpu_info()
    assert first_gpu["ok"] is False
    assert second_gpu["ok"] is False
    assert first_gpu["_cache"]["from_cache"] is False
    assert second_gpu["_cache"]["from_cache"] is True
    assert calls["which"] == 1

    first_models = ModelService.get_summary()
    second_models = ModelService.get_summary()
    assert first_models["ok"] is True
    assert second_models["ok"] is True
    assert first_models["_cache"]["from_cache"] is False
    assert second_models["_cache"]["from_cache"] is True
    assert calls["tiers"] == 1

    first_disk = ModelService.get_disk_summary()
    second_disk = ModelService.get_disk_summary()
    assert first_disk["free_gb"] == 0.0
    assert second_disk["free_gb"] == 0.0
    assert first_disk["_cache"]["from_cache"] is False
    assert second_disk["_cache"]["from_cache"] is True
    assert calls["disk"] == 1

    ComfyService.reset_caches()
    ModelService.reset_caches()
