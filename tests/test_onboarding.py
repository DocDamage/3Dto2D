import json
import pytest
import sys
import shutil
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

def test_onboarding_sample_creates_sample_project(client, monkeypatch, tmp_path):
    # Mock PROJECTS to point to a temp directory so we don't dirty the user workspace
    import services.onboarding_service as os_mod
    monkeypatch.setattr(os_mod, "PROJECTS", tmp_path / "projects")

    # Create fake examples folder
    fake_examples = tmp_path / "examples" / "prebuilt_demo_sprite"
    fake_examples.mkdir(parents=True)
    (fake_examples / "sheet.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(os_mod, "ROOT", tmp_path)

    response = client.post("/api/onboarding/sample")
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert data["project"] == "SampleProject"

    # Verify files created
    p_meta = tmp_path / "projects" / "SampleProject" / "spriteforge_project.json"
    assert p_meta.exists()
    p_sprite = tmp_path / "projects" / "SampleProject" / "sprites" / "prebuilt_demo_sprite" / "sheet.json"
    assert p_sprite.exists()

def test_onboarding_wizard_returns_guided_payload(client):
    response = client.post(
        "/api/onboarding/wizard",
        data=json.dumps({
            "archetype": "goblin",
            "action": "walk",
            "direction": "left",
            "name": "gobby"
        }),
        content_type="application/json"
    )
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True

    payload = data["payload"]
    assert payload["name"] == "gobby"
    assert "goblin" in payload["prompt"]
    assert "walk" in payload["prompt"]
    assert payload["direction"] == "left"
    assert payload["profile"] == "debug"  # Safe default
