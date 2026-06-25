"""Smoke tests for SpriteForge Studio v12.

These tests focus on integration-level sanity checks that don't require
ComfyUI, GPU, or any generated outputs to exist.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
GOLDEN_DEMO = APP / "examples" / "prebuilt_demo_sprite"
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


def test_golden_demo_sprite_metadata():
    """The checked-in demo sprite remains a valid known-good fixture."""
    meta = json.loads((GOLDEN_DEMO / "sheet.json").read_text(encoding="utf-8"))
    sheet = Image.open(GOLDEN_DEMO / meta["image"])
    frames = sorted((GOLDEN_DEMO / "frames_processed").glob("frame_*.png"))

    assert sheet.size == (
        meta["frame_width"] * meta["columns"],
        meta["frame_height"] * meta["rows"],
    )
    assert meta["animation"] == "demo_idle"
    assert meta["frame_count"] == 16
    assert len(meta["frames"]) == meta["frame_count"]
    assert len(frames) == meta["frame_count"]
    assert 1 <= meta["fps"] <= 60
    assert (GOLDEN_DEMO / "preview.gif").exists()
    assert (GOLDEN_DEMO / "report.html").exists()

    for frame in meta["frames"]:
        assert frame["w"] == meta["frame_width"]
        assert frame["h"] == meta["frame_height"]
        assert 0 <= frame["x"] < sheet.width
        assert 0 <= frame["y"] < sheet.height
        assert frame["x"] + frame["w"] <= sheet.width
        assert frame["y"] + frame["h"] <= sheet.height


def test_golden_demo_quality_and_compare(tmp_path):
    """Golden fixture produces bounded QC metrics and a compare report."""
    from spriteforge_compare import compare_dirs
    from spriteforge_quality import quality_report

    sprite_a = tmp_path / "demo_a"
    sprite_b = tmp_path / "demo_b"
    shutil.copytree(GOLDEN_DEMO, sprite_a)
    shutil.copytree(GOLDEN_DEMO, sprite_b)

    quality = quality_report(sprite_a, tmp_path / "quality", None)
    assert 0 <= float(quality["score"]) <= 100
    assert quality["grade"] in {"A", "B", "C", "D"}
    assert (tmp_path / "quality" / "quality_report.json").exists()
    assert (tmp_path / "quality" / "quality_report.html").exists()

    compare = compare_dirs(sprite_a, sprite_b, tmp_path / "compare")
    assert compare["compared_frames"] == 16
    assert compare["mean_diff"] == 0
    assert (tmp_path / "compare" / "compare_report.json").exists()
    assert (tmp_path / "compare" / "compare_report.html").exists()


def test_golden_demo_release_zip_contents(tmp_path):
    """Release packaging includes the expected files for the golden fixture."""
    from spriteforge_final import build_parser

    sprite_dir = tmp_path / "prebuilt_demo_sprite"
    shutil.copytree(GOLDEN_DEMO, sprite_dir)
    out_dir = tmp_path / "demo_release"

    parser = build_parser()
    args = parser.parse_args([
        "release",
        "--name",
        "golden_demo",
        "--sprite-dir",
        str(sprite_dir),
        "--output",
        str(out_dir),
        "--zip",
    ])

    mock_preflight = {
        "generated_at": "2026-06-25T12:00:00",
        "checks": {
            "python": {"ok": True, "value": "python"},
            "git": {"ok": True, "value": "git"},
            "nvidia": {"ok": True, "raw": "GeForce RTX", "label": "GeForce RTX"},
            "disk": {"ok": True, "free_gb": 100, "total_gb": 500},
            "comfy_dir": {"ok": True, "value": "comfy_dir"},
            "comfy_output": {"ok": True, "value": "comfy_output"},
            "comfy_running": {"ok": False, "value": "comfy_url"},
            "outputs": {"ok": True, "count": 1},
            "next_step": {"step": "None", "reason": "none"},
        },
        "sprites": [],
    }
    with patch("spriteforge_final.preflight_data", return_value=mock_preflight):
        args.func(args)

    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "sprites" / "prebuilt_demo_sprite" / "sheet.json").exists()
    assert (out_dir / "sprites" / "prebuilt_demo_sprite" / "sheet.png").exists()

    zip_file_path = out_dir.with_suffix(".zip")
    assert zip_file_path.exists()
    with zipfile.ZipFile(zip_file_path, "r") as zf:
        names = set(zf.namelist())
    assert "demo_release/manifest.json" in names
    assert "demo_release/sprites/prebuilt_demo_sprite/sheet.json" in names
    assert "demo_release/sprites/prebuilt_demo_sprite/sheet.png" in names


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
        project_name="hero",
        project_path="projects/hero/spriteforge_project.json",
        project_root="projects/hero",
    )
    assert run_id

    rec = ExperimentService.get_run(run_id)
    assert rec is not None
    assert rec["prompt"] == "test hero walk"
    assert rec["sprite_action"] == "walk"
    assert rec["project_name"] == "hero"
    assert rec["project_path"] == "projects/hero/spriteforge_project.json"

    history = ExperimentService.get_history()
    assert len(history) == 1

    ok = ExperimentService.update_note(run_id, "great result!")
    assert ok
    rec2 = ExperimentService.get_run(run_id)
    assert rec2["notes"] == "great result!"

    assert ExperimentService.set_starred(run_id, True)
    exported = ExperimentService.export_history()
    assert exported["schema"] == "spriteforge_experiment_history_v1"
    assert exported["count"] == 1
    assert exported["records"][0]["starred"] is True

    removed = ExperimentService.clear_history(keep_starred=True)
    assert removed == 0
    assert len(ExperimentService.get_history()) == 1

    removed = ExperimentService.clear_history(keep_starred=False)
    assert removed == 1
    assert ExperimentService.get_history() == []


def test_experiment_history_retention(tmp_path, monkeypatch):
    """Experiment history is capped so local JSON does not grow forever."""
    from services import experiment_service as es_mod
    from services.experiment_service import ExperimentService

    test_path = tmp_path / "experiments" / "experiment_history.json"
    monkeypatch.setattr(es_mod, "EXPERIMENT_PATH", test_path)
    monkeypatch.setattr(es_mod, "MAX_EXPERIMENT_HISTORY", 3)

    for i in range(5):
        ExperimentService.append_run(prompt=f"run {i}")

    history = ExperimentService.get_history(limit=10)
    assert len(history) == 3
    assert [rec["prompt"] for rec in history] == ["run 4", "run 3", "run 2"]


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


def test_queue_listing_project_filter(tmp_path, monkeypatch):
    import spriteforge_web as web_mod
    monkeypatch.setattr(web_mod, "OUTPUT", tmp_path)

    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    project_queue = {
        "schema": "spriteforge_queue_v12",
        "name": "hero",
        "project_name": "hero",
        "project_path": "projects/hero/spriteforge_project.json",
        "project_root": "projects/hero",
        "created_at": "2026-06-01T12:00:00",
        "jobs": [{"id": "001_idle_right", "status": "pending"}],
    }
    other_queue = {
        "schema": "spriteforge_queue_v12",
        "name": "other",
        "created_at": "2026-06-01T12:00:00",
        "jobs": [{"id": "001_idle_right", "status": "pending"}],
    }
    (jobs_dir / "hero_queue.json").write_text(json.dumps(project_queue), encoding="utf-8")
    (jobs_dir / "other_queue.json").write_text(json.dumps(other_queue), encoding="utf-8")

    queues = web_mod._list_queues({
        "project_name": "hero",
        "project_path": "projects/hero/spriteforge_project.json",
        "project_root": "projects/hero",
    })

    assert [q["name"] for q in queues] == ["hero"]
