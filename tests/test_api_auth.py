import json
import sys
import pytest
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

def test_get_auth_token_returns_valid_session_token(client):
    response = client.get("/api/auth/token")
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert "token" in data
    assert len(data["token"]) == 48  # Hex token of 24 bytes

def test_api_token_protection_blocks_post_requests(client):
    # Enable token check by passing the X-Force-Token-Check header
    response = client.post(
        "/api/projects/create",
        headers={"X-Force-Token-Check": "true"},
        data=json.dumps({"name": "test_token_blocked"}),
        content_type="application/json"
    )
    assert response.status_code == 401
    data = json.loads(response.data.decode("utf-8"))
    assert "Unauthorized" in data["message"]

def test_api_token_protection_allows_valid_token(client):
    # Fetch token first
    resp_token = client.get("/api/auth/token")
    token = json.loads(resp_token.data.decode("utf-8"))["token"]

    # Send valid token in X-SF-Token header
    response = client.post(
        "/api/projects/create",
        headers={"X-Force-Token-Check": "true", "X-SF-Token": token},
        data=json.dumps({"name": "test_token_allowed"}),
        content_type="application/json"
    )
    assert response.status_code == 200
