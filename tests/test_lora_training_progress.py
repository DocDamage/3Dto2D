import json
import importlib
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_lora_training_progress_reads_losses_samples_and_checkpoints(tmp_path):
    from services.lora_training_progress_service import summarize_lora_training_progress

    run = tmp_path / "output" / "training_runs" / "demo"
    (run / "samples").mkdir(parents=True)
    (run / "training_run.json").write_text(json.dumps({"name": "demo", "max_train_steps": 100}), encoding="utf-8")
    (run / "loss.csv").write_text("step,loss\n10,0.8\n25,0.5\n", encoding="utf-8")
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(run / "samples" / "sample_0025.png")
    (run / "demo.safetensors").write_bytes(b"checkpoint")

    summary = summarize_lora_training_progress("output/training_runs/demo", root=tmp_path)

    assert summary["ok"] is True
    assert summary["current_step"] == 25
    assert summary["last_loss"] == 0.5
    assert summary["progress"] == 25.0
    assert summary["samples"][0]["url"] == "/file/output/training_runs/demo/samples/sample_0025.png"
    assert summary["checkpoints"][0]["name"] == "demo.safetensors"


def test_lora_progress_includes_ckpt_checkpoints(tmp_path):
    from services.lora_training_progress_service import summarize_lora_training_progress

    run = tmp_path / "output" / "training_runs" / "demo"
    run.mkdir(parents=True)
    (run / "demo.ckpt").write_bytes(b"checkpoint")

    summary = summarize_lora_training_progress("output/training_runs/demo", root=tmp_path)

    assert summary["checkpoints"][0]["name"] == "demo.ckpt"


def test_lora_checkpoint_registration_endpoint_registers_latest_checkpoint(tmp_path, monkeypatch):
    from flask import Flask
    routes_jobs = importlib.import_module("web_routes.routes_jobs")

    dataset = tmp_path / "datasets" / "tiles"
    dataset.mkdir(parents=True)
    (dataset / "manifest.json").write_text(json.dumps({
        "dataset_kind": "tileset",
        "source_dir": "CuteSCKR_uncut",
        "sample_count": 12,
        "trigger": "cutesckr_tiles",
    }), encoding="utf-8")
    run = tmp_path / "output" / "training_runs" / "demo"
    run.mkdir(parents=True)
    (run / "training_run.json").write_text(json.dumps({
        "name": "demo",
        "trainer": "kohya",
        "base_model": "sdxl",
        "dataset_dir": str(dataset),
        "max_train_steps": 20,
        "sample_count": 12,
        "trigger": "cutesckr_tiles",
    }), encoding="utf-8")
    (run / "old.safetensors").write_bytes(b"old")
    latest = run / "latest.safetensors"
    latest.write_bytes(b"latest")

    monkeypatch.setattr(routes_jobs, "ROOT", tmp_path)
    app = Flask(__name__)
    app.register_blueprint(routes_jobs.routes_jobs)

    response = app.test_client().post("/api/lora/register-checkpoint", json={
        "run_path": "output/training_runs/demo",
        "registry_path": str(tmp_path / "trained_loras.json"),
    })
    data = response.get_json()

    assert response.status_code == 200
    assert data["ok"] is True
    assert data["filename"] == latest.name
    assert data["role"] == "tile_style"


def test_lora_progress_ui_assets_are_wired():
    html = (APP / "web" / "components" / "training.html").read_text(encoding="utf-8")
    js = (APP / "web" / "js" / "app_forms.js").read_text(encoding="utf-8")

    assert "loraLossChart" in html
    assert "registerLoraCheckpoint" in html
    assert "refreshLoraProgress" in js
    assert "/api/lora/progress" in js
    assert "/api/lora/register-checkpoint" in js
