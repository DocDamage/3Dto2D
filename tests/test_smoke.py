"""Smoke tests for SpriteForge Studio v12.

These tests focus on integration-level sanity checks that don't require
ComfyUI, GPU, or any generated outputs to exist.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
PYTHON = str(APP / ".venv" / "Scripts" / "python.exe") if (APP / ".venv" / "Scripts" / "python.exe").exists() else sys.executable

sys.path.insert(0, str(APP))


# ---------------------------------------------------------------------------
# Web UI smoke
# ---------------------------------------------------------------------------

def test_web_smoke():
    """spriteforge_web.py --smoke should exit 0 when web assets are present."""
    result = subprocess.run(
        [PYTHON, str(APP / "spriteforge_web.py"), "--smoke"],
        capture_output=True,
        text=True,
        cwd=str(APP),
    )
    assert result.returncode == 0, (
        f"Web smoke failed (exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
    )
    assert "passed" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Compare smoke
# ---------------------------------------------------------------------------

def test_compare_smoke(tmp_path):
    """compare_dirs() on two minimal fake sprite dirs writes a report."""
    from spriteforge_compare import compare_dirs

    def _make_sprite_dir(name: str, color: tuple) -> Path:
        d = tmp_path / name
        frames_dir = d / "frames"
        frames_dir.mkdir(parents=True)
        img = Image.new("RGBA", (64, 64), color + (255,))
        img.save(frames_dir / "frame_000.png")
        img.save(frames_dir / "frame_001.png")
        # sheet.json
        sheet = Image.new("RGBA", (128, 64), (0, 0, 0, 0))
        sheet.paste(img, (0, 0))
        sheet.paste(img, (64, 0))
        sheet.save(d / "sheet.png")
        (d / "sheet.json").write_text(json.dumps({
            "frame_width": 64, "frame_height": 64,
            "frame_count": 2, "columns": 2, "rows": 1,
            "fps": 12, "image": "sheet.png",
        }), encoding="utf-8")
        return d

    a = _make_sprite_dir("sprite_a", (255, 0, 0))
    b = _make_sprite_dir("sprite_b", (0, 255, 0))
    out = tmp_path / "compare_out"

    data = compare_dirs(a, b, out)

    assert (out / "compare_report.json").exists()
    assert (out / "compare_report.html").exists()
    assert data["compared_frames"] == 2
    assert data["mean_diff"] > 0


# ---------------------------------------------------------------------------
# Export validate smoke
# ---------------------------------------------------------------------------

def test_export_validate_smoke(tmp_path):
    """validate_export() passes for a well-formed sprite directory."""
    from spriteforge_engine_export import validate_export

    sprite_dir = tmp_path / "test_sprite"
    sprite_dir.mkdir()

    img = Image.new("RGBA", (128, 64), (100, 200, 100, 255))
    img.save(sprite_dir / "sheet.png")
    (sprite_dir / "sheet.json").write_text(json.dumps({
        "frame_width": 64, "frame_height": 64,
        "frame_count": 2, "columns": 2, "rows": 1,
        "fps": 12, "image": "sheet.png",
    }), encoding="utf-8")

    ok = validate_export(sprite_dir)
    assert ok, "validate_export should return True for a valid sprite dir"


def test_export_validate_bad_dimensions(tmp_path):
    """validate_export() fails when pixel dimensions don't match metadata."""
    from spriteforge_engine_export import validate_export

    sprite_dir = tmp_path / "bad_sprite"
    sprite_dir.mkdir()

    # Image is 64×64 but metadata says it should be 128×64
    img = Image.new("RGBA", (64, 64), (100, 200, 100, 255))
    img.save(sprite_dir / "sheet.png")
    (sprite_dir / "sheet.json").write_text(json.dumps({
        "frame_width": 64, "frame_height": 64,
        "frame_count": 2, "columns": 2, "rows": 1,
        "fps": 12, "image": "sheet.png",
    }), encoding="utf-8")

    ok = validate_export(sprite_dir)
    assert not ok, "validate_export should return False when dimensions are wrong"


# ---------------------------------------------------------------------------
# Experiment service smoke
# ---------------------------------------------------------------------------

def test_experiment_service(tmp_path, monkeypatch):
    """ExperimentService round-trips a record correctly."""
    from services import experiment_service as es_mod

    # Redirect storage path to tmp_path
    test_path = tmp_path / "experiments" / "experiment_history.json"
    monkeypatch.setattr(es_mod, "EXPERIMENT_PATH", test_path)

    from services.experiment_service import ExperimentService

    run_id = ExperimentService.append_run(
        prompt="test hero walk",
        model_tier="wan21_safe",
        profile="debug",
        sprite_action="walk",
        direction="right",
    )
    assert run_id

    rec = ExperimentService.get_run(run_id)
    assert rec is not None
    assert rec["prompt"] == "test hero walk"
    assert rec["sprite_action"] == "walk"

    history = ExperimentService.get_history()
    assert len(history) == 1

    ok = ExperimentService.update_note(run_id, "great result!")
    assert ok
    rec2 = ExperimentService.get_run(run_id)
    assert rec2["notes"] == "great result!"


# ---------------------------------------------------------------------------
# Advisor service smoke
# ---------------------------------------------------------------------------

def test_advisor_service():
    """AdvisorService.advise() returns all required keys."""
    from services.advisor_service import advise

    for quality in ("fast", "balanced", "quality"):
        rec = advise(quality)
        for key in ("tier", "profile", "cell_size", "fps", "frame_count", "steps", "rationale", "warnings"):
            assert key in rec, f"Missing key {key!r} in {quality!r} recommendation"
        assert isinstance(rec["frame_count"], int)
        assert rec["frame_count"] % 2 == 1, "frame_count should be odd"
        assert isinstance(rec["warnings"], list)


# ---------------------------------------------------------------------------
# Queue listing smoke
# ---------------------------------------------------------------------------

def test_queue_listing_helper(tmp_path, monkeypatch):
    """_list_queues() correctly parses a synthetic queue file."""
    import spriteforge_web as web_mod
    monkeypatch.setattr(web_mod, "OUTPUT", tmp_path)

    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    q = {
        "schema": "spriteforge_queue_v12",
        "name": "test_hero",
        "created_at": "2026-06-01T12:00:00",
        "jobs": [
            {"id": "001_idle_right", "action": "idle", "direction": "right", "status": "done"},
            {"id": "002_walk_right", "action": "walk", "direction": "right", "status": "pending"},
            {"id": "003_run_right", "action": "run", "direction": "right", "status": "failed"},
        ]
    }
    (jobs_dir / "test_hero_20260601_120000_queue.json").write_text(json.dumps(q), encoding="utf-8")

    queues = web_mod._list_queues()
    assert len(queues) == 1
    assert queues[0]["name"] == "test_hero"
    assert queues[0]["total"] == 3
    assert queues[0]["counts"]["done"] == 1
    assert queues[0]["counts"]["failed"] == 1
