import json
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


def test_lora_progress_ui_assets_are_wired():
    html = (APP / "web" / "components" / "training.html").read_text(encoding="utf-8")
    js = (APP / "web" / "js" / "app_forms.js").read_text(encoding="utf-8")

    assert "loraLossChart" in html
    assert "refreshLoraProgress" in js
    assert "/api/lora/progress" in js
