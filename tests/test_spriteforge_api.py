import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add app directory to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from spriteforge_web import app

@pytest.fixture
def flask_client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_path_safety(tmp_path, monkeypatch, flask_client):
    import web_helpers as web_mod
    monkeypatch.setattr(web_mod, "ROOT", tmp_path)
    monkeypatch.setattr(web_mod, "WEB", tmp_path / "web")

    (tmp_path / "web").mkdir(parents=True, exist_ok=True)

    # 1. Allowed paths
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True)
    allowed_file = output_dir / "sheet.png"
    allowed_file.touch()
    
    response = flask_client.get("/file/output/sheet.png")
    assert response.status_code != 403
    
    # 2. Path outside workspace (traversal)
    response = flask_client.get("/file/../../etc/passwd")
    assert response.status_code == 403

    # 3. Disallowed system path (e.g. .venv)
    response = flask_client.get("/file/.venv/pyvenv.cfg")
    assert response.status_code == 403

def test_upload_limits(flask_client):
    # 1. Exceeds 100MB
    large_data = b"x" * (101 * 1024 * 1024)
    import io
    response = flask_client.post(
        "/api/upload",
        data={"file": (io.BytesIO(large_data), "large.png")},
        content_type="multipart/form-data"
    )
    assert response.status_code in (413, 400)

def test_upload_routes_to_active_project_references(tmp_path, monkeypatch, flask_client):
    import web_helpers as web_mod
    monkeypatch.setattr(web_mod, "ROOT", tmp_path)
    monkeypatch.setattr(web_mod, "UPLOADS", tmp_path / "input")
    
    project_meta = {
        "project_name": "hero",
        "project_path": "projects/hero/spriteforge_project.json",
        "project_root": "projects/hero",
    }
    monkeypatch.setattr(
        web_mod.ProjectService,
        "metadata_for_path",
        staticmethod(lambda value: project_meta if value == "projects/hero/spriteforge_project.json" else None),
    )
    
    import io
    response = flask_client.post(
        "/api/upload",
        data={
            "active_project": "projects/hero/spriteforge_project.json",
            "file": (io.BytesIO(b"fake png bytes"), "hero ref.png")
        },
        content_type="multipart/form-data"
    )
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert data["relative"] == "projects/hero/references/hero_ref.png"
    assert (tmp_path / "projects" / "hero" / "references" / "hero_ref.png").read_bytes() == b"fake png bytes"

def test_experiment_clear_api_scopes_to_project(tmp_path, monkeypatch, flask_client):
    import services.experiment_service as es_mod
    import web_helpers as web_mod
    from services.experiment_service import ExperimentService

    monkeypatch.setattr(es_mod, "EXPERIMENT_PATH", tmp_path / "experiments" / "history.json")

    hero_id = ExperimentService.append_run(
        prompt="hero",
        project_name="hero",
        project_path="projects/hero/spriteforge_project.json",
        project_root="projects/hero",
    )
    other_id = ExperimentService.append_run(
        prompt="other",
        project_name="other",
        project_path="projects/other/spriteforge_project.json",
        project_root="projects/other",
    )
    monkeypatch.setattr(
        web_mod.ProjectService,
        "metadata_for_path",
        staticmethod(lambda value: {
            "project_name": "hero",
            "project_path": "projects/hero/spriteforge_project.json",
            "project_root": "projects/hero",
        } if value else None),
    )

    response = flask_client.get("/api/experiments/clear?project=projects%2Fhero%2Fspriteforge_project.json")
    if response.status_code == 405: # if it was a POST route originally
        response = flask_client.post(
            "/api/experiments/clear?project=projects%2Fhero%2Fspriteforge_project.json",
            data=json.dumps({"keep_starred": True}),
            content_type="application/json"
        )
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["removed"] == 1
    assert ExperimentService.get_run(hero_id) is None
    assert ExperimentService.get_run(other_id) is not None
