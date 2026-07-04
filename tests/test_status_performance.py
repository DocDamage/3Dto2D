import sys
import inspect
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_comfy_running_status_uses_short_ttl_cache(monkeypatch):
    from services.comfy_service import ComfyService

    calls = {"count": 0}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(_url, timeout):
        calls["count"] += 1
        return FakeResponse()

    ComfyService.reset_caches()
    monkeypatch.setattr("services.comfy_service.urllib.request.urlopen", fake_urlopen)

    assert ComfyService.is_running(timeout=0.1) is True
    assert ComfyService.is_running(timeout=0.1) is True
    assert calls["count"] == 1

    assert ComfyService.is_running(timeout=0.1, force_refresh=True) is True
    assert calls["count"] == 2


def test_gpu_and_model_status_expose_cache_controls():
    from services.comfy_service import ComfyService
    from services.model_service import ModelService

    assert "force_refresh" in inspect.signature(ComfyService.is_running).parameters
    assert "force_refresh" in inspect.signature(ComfyService.get_gpu_info).parameters
    assert "force_refresh" in inspect.signature(ModelService.get_summary).parameters
    assert "force_refresh" in inspect.signature(ModelService.get_disk_summary).parameters
    assert callable(ComfyService.reset_caches)
    assert callable(ModelService.reset_caches)
