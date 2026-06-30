"""Integration tests for the Flask Web API layer using Flask test client.

This suite exercises routes, config updates, diagnostics, and SSE streaming headers.
"""
import json
import os
import shutil
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from spriteforge_web import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def active_project(client):
    """Creates a temporary project to ensure active project endpoints work."""
    response = client.post(
        "/api/projects/create",
        data=json.dumps({"name": "test_integration_project"}),
        content_type="application/json"
    )
    yield
    # Cleanup temporary project created by ProjectService.
    project_dir = APP / "projects" / "test_integration_project"
    if project_dir.exists():
        try:
            shutil.rmtree(project_dir)
        except OSError:
            pass


def test_index_page(client):
    """GET / should serve index.html successfully."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"<!doctype html>" in response.data.lower()
    assert b"spriteforge" in response.data.lower()


def test_get_project_config(client):
    """GET /api/project/config should return JSON configuration with quality gates."""
    response = client.get("/api/project/config")
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert "quality_gates" in data
    assert "max_foot_drift" in data["quality_gates"]


def test_post_project_config(client):
    """POST /api/project/config updates config parameters."""
    payload = {
        "quality_gates": {
            "max_foot_drift": 4.5,
            "max_flicker": 2.2,
            "loop_seam_threshold": 12.0
        }
    }
    response = client.post(
        "/api/project/config",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True


def test_list_presets(client):
    """GET /api/presets returns loaded presets."""
    response = client.get("/api/presets")
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert "presets" in data


def test_status_diagnostics(client):
    """GET /api/status should return system diagnostic information."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert "cleanup_suggestions" in data
    assert "disk" in data


def test_qa_batch_summary(client):
    """GET /api/qa/batch_summary lists quality metrics of project folders."""
    response = client.get("/api/qa/batch_summary")
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert "summary" in data


def test_sse_stream_headers(client):
    """GET /api/status/stream should return EventStream headers for real-time logs."""
    response = client.get("/api/status/stream")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["Content-Type"]



def test_invalid_rollback(client):
    """POST /api/sprite/version/rollback with empty parameters should fail gracefully."""
    response = client.post(
        "/api/sprite/version/rollback",
        data=json.dumps({"path": "", "version_id": ""}),
        content_type="application/json"
    )
    assert response.status_code == 400
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is False
    assert "required" in data["message"].lower()
