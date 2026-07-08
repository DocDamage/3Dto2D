from __future__ import annotations

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


def test_pixel_normalize_rejects_workspace_escape(client):
    response = client.post("/api/pixel-assets/normalize", json={"path": "../outside.png"})

    assert response.status_code == 403
    data = response.get_json()
    assert data["ok"] is False
    assert data["code"] == "path_escape"


def test_pixel_normalize_rejects_non_image_paths(client):
    response = client.post("/api/pixel-assets/normalize", json={"path": "README.md"})

    assert response.status_code == 400
    data = response.get_json()
    assert data["ok"] is False
    assert data["code"] == "unsupported_image"
