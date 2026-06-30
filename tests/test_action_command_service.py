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

def test_command_discovery_returns_expected_fields(client):
    response = client.get("/api/commands/list")
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))

    assert data["ok"] is True
    assert "commands" in data
    commands = data["commands"]
    assert len(commands) > 0

    first = commands[0]
    assert "id" in first
    assert "label" in first
    assert "description" in first
    assert "view" in first
    assert "enabled" in first

def test_command_execution_requires_confirmation_correctly(client):
    # Retry jobs requires confirmation
    response = client.post(
        "/api/commands/execute",
        data=json.dumps({"id": "retry_jobs"}),
        content_type="application/json"
    )
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert data["requires_confirmation"] is True

    # Run QA does not require confirmation
    response_qa = client.post(
        "/api/commands/execute",
        data=json.dumps({"id": "run_qa"}),
        content_type="application/json"
    )
    assert response_qa.status_code == 200
    data_qa = json.loads(response_qa.data.decode("utf-8"))
    assert data_qa["ok"] is True
    assert data_qa["requires_confirmation"] is False
    assert data_qa["action"]["id"] == "run_qa"
