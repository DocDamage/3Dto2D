import json
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from spriteforge_web import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_startup_self_test_api_returns_structured_results(client):
    response = client.get("/api/selftest")
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))

    assert "ok" in data
    assert "checks" in data
    checks = data["checks"]

    # Assert structural checkpoints are all present
    assert "python" in checks
    assert "ffmpeg" in checks
    assert "pillow" in checks
    assert "comfyui" in checks
    assert "writable" in checks
    assert "models" in checks
    assert "disk" in checks
    assert "gpu" in checks

    # Check validation format
    assert "ok" in checks["python"]
    assert "details" in checks["python"]
