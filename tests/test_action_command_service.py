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
    assert "risk_level" in first
    assert "category" in first
    assert "mutates_state" in first

    ids = {command["id"] for command in commands}
    assert {"open_cloud_hub", "open_animation_player", "open_frame_editor", "open_packs_exports"} <= ids
    assert {"export_animation_webm", "pick_compare_winner", "open_qa_advisor", "preview_cloud_sprite_plan"} <= ids
    by_id = {command["id"]: command for command in commands}
    assert by_id["run_qa"]["view"] == "quality"
    assert by_id["run_qa"]["shortcut"] == "Ctrl+Q"
    assert by_id["run_qa"]["risk_level"] == "low"
    assert by_id["build_release"]["shortcut"] == "Ctrl+E"
    assert by_id["pick_compare_winner"]["endpoint"] == "/api/experiments/pick-winner"
    assert by_id["preview_cloud_sprite_plan"]["view"] == "cloud_hub"
    assert by_id["retry_jobs"]["risk_level"] == "high"
    assert by_id["retry_jobs"]["confirmation_message"]

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
    assert "requires user confirmation" in data["message"]

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
    assert data_qa["action"]["view"] == "quality"

    response_winner = client.post(
        "/api/commands/execute",
        data=json.dumps({"id": "pick_compare_winner"}),
        content_type="application/json"
    )
    data_winner = json.loads(response_winner.data.decode("utf-8"))
    assert response_winner.status_code == 200
    assert data_winner["ok"] is True
    assert data_winner["action"]["view"] == "compare_player"
