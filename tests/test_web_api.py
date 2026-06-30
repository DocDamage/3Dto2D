"""Integration tests for the Flask Web API layer using Flask test client.

This suite exercises routes, config updates, diagnostics, and SSE streaming headers.
"""
import json
import os
import shutil
import sys
from pathlib import Path
import pytest
from PIL import Image

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


def test_prompt_builder_options(client):
    response = client.get("/api/prompt_builder/options")
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert "walk" in data["actions"]
    assert "heroic" in data["body_styles"]


def test_prompt_builder_builds_structured_prompt(client):
    payload = {
        "character_type": "clockwork knight",
        "body_style": "heavy",
        "outfit": "brass armor with blue cloth",
        "action": "walk",
        "direction": "right",
        "camera": "side",
        "art_style": "pixel",
        "negative_extra": "oversized weapon"
    }
    response = client.post(
        "/api/prompt_builder/build",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    prompt = data["prompt"]
    assert data["ok"] is True
    assert "clockwork knight" in prompt["positive"]
    assert "clean walk cycle loop" in prompt["positive"]
    assert "pixel-art inspired" in prompt["positive"]
    assert "brass armor" in prompt["generated_character"]
    assert "side-view locked camera" in prompt["generated_style"]
    assert "oversized weapon" in prompt["negative"]


def test_seed_gallery_api_groups_seed_records(client, tmp_path, monkeypatch):
    from services import experiment_service as es_mod
    from services.experiment_service import ExperimentService

    monkeypatch.setattr(es_mod, "EXPERIMENT_PATH", tmp_path / "experiments" / "history.json")
    project = "test_integration_project"
    ExperimentService.append_run(seed=42, sprite_action="walk", direction="right", qa_score=75.0, project_name=project)
    ExperimentService.append_run(seed=42, sprite_action="idle", direction="front", qa_score=88.0, project_name=project)
    ExperimentService.append_run(seed=-1, sprite_action="run", project_name=project)
    ExperimentService.append_run(seed=7, sprite_action="attack_light", qa_score=20.0, project_name=project)

    response = client.get("/api/seeds/gallery")
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))

    assert [item["seed"] for item in data["seeds"]] == [42, 7]
    assert data["seeds"][0]["uses"] == 2
    assert data["seeds"][0]["best_score"] == 88.0
    assert data["seeds"][0]["examples"][0]["action"] in {"walk", "idle"}


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


def test_frame_status_api_updates_sprite_metadata(client, tmp_path, monkeypatch):
    import web_helpers as web_mod

    sprite_dir = tmp_path / "output" / "hero"
    sprite_dir.mkdir(parents=True)
    (sprite_dir / "sheet.json").write_text(json.dumps({
        "frame_count": 1,
        "frames": [{"index": 0}]
    }), encoding="utf-8")
    monkeypatch.setattr(web_mod, "OUTPUT", tmp_path / "output")
    monkeypatch.setattr(web_mod, "ROOT", tmp_path)

    response = client.post(
        "/api/sprite/frame/status",
        data=json.dumps({"path": "output/hero", "frame_index": 0, "status": "approved"}),
        content_type="application/json"
    )
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["summary"]["counts"]["approved"] == 1
    meta = json.loads((sprite_dir / "sheet.json").read_text(encoding="utf-8"))
    assert meta["frames"][0]["review_status"] == "approved"


def test_palette_harmonize_api_creates_report(client, tmp_path, monkeypatch):
    import web_helpers as web_mod

    output = tmp_path / "output"
    idle = output / "hero_idle"
    walk = output / "hero_walk"
    idle.mkdir(parents=True)
    walk.mkdir(parents=True)
    for folder, color in [(idle, (210, 60, 60, 255)), (walk, (60, 90, 210, 255))]:
        (folder / "sheet.json").write_text(json.dumps({"image": "sheet.png"}), encoding="utf-8")
        Image.new("RGBA", (3, 3), color).save(folder / "sheet.png")
    monkeypatch.setattr(web_mod, "OUTPUT", output)
    monkeypatch.setattr(web_mod, "ROOT", tmp_path)

    response = client.post(
        "/api/sprites/palette_harmonize",
        data=json.dumps({"sprites": ["output/hero_idle", "output/hero_walk"], "colors": 4}),
        content_type="application/json"
    )

    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert len(data["sprites"]) == 2
    assert (output / "_palette_harmonization" / "palette_harmonization.json").exists()
    assert (idle / "sheet_harmonized.png").exists()


def test_audio_cue_api_updates_preview_bundle(client, tmp_path, monkeypatch):
    import web_helpers as web_mod

    sprite_dir = tmp_path / "output" / "hero"
    sprite_dir.mkdir(parents=True)
    (sprite_dir / "sheet.json").write_text(json.dumps({
        "frame_count": 1,
        "fps": 12,
        "image": "sheet.png",
        "frame_width": 16,
        "frame_height": 16,
        "columns": 1,
        "rows": 1,
        "frames": [{"index": 0, "x": 0, "y": 0, "w": 16, "h": 16}]
    }), encoding="utf-8")
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(sprite_dir / "sheet.png")
    audio = tmp_path / "input" / "step.wav"
    audio.parent.mkdir()
    audio.write_bytes(b"RIFFfake")
    monkeypatch.setattr(web_mod, "OUTPUT", tmp_path / "output")
    monkeypatch.setattr(web_mod, "ROOT", tmp_path)

    response = client.post(
        "/api/sprite/audio_cue",
        data=json.dumps({
            "path": "output/hero",
            "frame_index": 0,
            "audio_path": "input/step.wav",
            "label": "step",
        }),
        content_type="application/json"
    )
    assert response.status_code == 200

    preview = client.get("/api/sprite/preview?path=output/hero")
    data = json.loads(preview.data.decode("utf-8"))
    cue = data["audio_cues"]["cues"][0]
    assert cue["label"] == "step"
    assert cue["audio_url"] == "/file/input/step.wav"


def test_state_machine_api_exports_manifest(client, tmp_path, monkeypatch):
    import importlib
    import web_helpers as web_mod
    routes_projects_mod = importlib.import_module("web_routes.routes_projects")

    monkeypatch.setattr(web_mod, "ROOT", tmp_path)
    monkeypatch.setattr(routes_projects_mod, "ROOT", tmp_path)

    response = client.post(
        "/api/state_machine/build",
        data=json.dumps({
            "name": "hero_controller",
            "initial_state": "idle",
            "states": [
                {"name": "idle", "sprite_path": "output/hero_idle"},
                {"name": "walk", "sprite_path": "output/hero_walk"},
            ],
            "transitions": [{"from": "idle", "to": "walk", "condition": "move"}],
        }),
        content_type="application/json"
    )

    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["manifest"]["initial_state"] == "idle"
    assert (tmp_path / "output" / "state_machines" / "hero_controller" / "state_machine.json").exists()


def test_prompt_lint_api(client):
    """POST /api/prompt/lint lint and scoring functionality."""
    # Test valid request
    response = client.post(
        "/api/prompt/lint",
        data=json.dumps({"prompt": "A beautiful warrior hero 8-bit pixel art", "negative": "blurry", "action": "idle"}),
        content_type="application/json"
    )
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert "score" in data
    assert "checks" in data

    # Test bad request (no prompt)
    response_err = client.post(
        "/api/prompt/lint",
        data=json.dumps({"prompt": ""}),
        content_type="application/json"
    )
    assert response_err.status_code == 400


def test_archetypes_api(client):
    """GET /api/archetypes lists and filters archetypes."""
    response = client.get("/api/archetypes")
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert "archetypes" in data
    assert "total" in data


def test_experiment_restore_api_clears_rejection(client, tmp_path, monkeypatch):
    from services import experiment_service as es_mod
    from services.experiment_service import ExperimentService

    monkeypatch.setattr(es_mod, "EXPERIMENT_PATH", tmp_path / "experiments" / "history.json")
    run_id = ExperimentService.append_run(prompt="hero idle")

    reject_response = client.post(
        "/api/experiments/review",
        data=json.dumps({"id": run_id, "decision": "reject"}),
        content_type="application/json",
    )
    assert reject_response.status_code == 200
    assert ExperimentService.get_run(run_id)["review_status"] == "rejected"

    restore_response = client.post(
        "/api/experiments/restore",
        data=json.dumps({"id": run_id}),
        content_type="application/json",
    )
    assert restore_response.status_code == 200
    data = json.loads(restore_response.data.decode("utf-8"))
    assert data["ok"] is True
    assert data["experiment"]["review_status"] == "reviewed"
    assert "reviewed_at" not in ExperimentService.get_run(run_id)
