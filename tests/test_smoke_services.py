"""Smoke tests for SpriteForge backend services."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"

sys.path.insert(0, str(APP))


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


def test_job_service_records_qa_result(tmp_path, monkeypatch):
    """Completed qa-report jobs annotate the matching experiment record."""
    import services.experiment_service as es_mod
    import services.job_service as js_mod
    from services.experiment_service import ExperimentService
    from services.job_service import JobService

    monkeypatch.setattr(es_mod, "EXPERIMENT_PATH", tmp_path / "experiments" / "history.json")
    monkeypatch.setattr(js_mod, "ROOT", tmp_path)

    sprite_dir = tmp_path / "output" / "hero_idle"
    report_dir = sprite_dir / "qa"
    report_dir.mkdir(parents=True)
    (report_dir / "qa_report.json").write_text(json.dumps({
        "metrics": {"frame_count": 2},
        "issues": [],
    }), encoding="utf-8")

    run_id = ExperimentService.append_run(sprite_folder="output/hero_idle")

    updated = JobService._record_qa_result([
        sys.executable,
        "spriteforge_unified.py",
        "qa-report",
        "--input",
        "output/hero_idle",
    ])

    assert updated is True
    rec = ExperimentService.get_run(run_id)
    assert rec["qa_passed"] is True
    assert rec["qa_score"] == 100.0


def test_job_service_records_warning_qa_result_as_not_passed(tmp_path, monkeypatch):
    """Warnings in qa_report.json mark the matching run as needing attention."""
    import services.experiment_service as es_mod
    import services.job_service as js_mod
    from services.experiment_service import ExperimentService
    from services.job_service import JobService

    monkeypatch.setattr(es_mod, "EXPERIMENT_PATH", tmp_path / "experiments" / "history.json")
    monkeypatch.setattr(js_mod, "ROOT", tmp_path)

    sprite_dir = tmp_path / "output" / "hero_walk"
    custom_report_dir = tmp_path / "project_quality" / "hero_walk"
    custom_report_dir.mkdir(parents=True)
    (custom_report_dir / "qa_report.json").write_text(json.dumps({
        "metrics": {"frame_count": 2},
        "issues": [{"level": "warn", "code": "loop_seam", "message": "Loop may pop."}],
    }), encoding="utf-8")

    run_id = ExperimentService.append_run(sprite_folder="output/hero_walk")

    updated = JobService._record_qa_result([
        sys.executable,
        "spriteforge_unified.py",
        "qa-report",
        "--input",
        str(sprite_dir),
        "--output",
        str(custom_report_dir),
    ])

    assert updated is True
    rec = ExperimentService.get_run(run_id)
    assert rec["qa_passed"] is False
    assert rec["qa_score"] == 85.0


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


def test_experiment_history_scoped_export_and_clear(tmp_path, monkeypatch):
    """Project-mode history export/clear can operate on a filtered record set."""
    from services import experiment_service as es_mod
    from services.experiment_service import ExperimentService

    test_path = tmp_path / "experiments" / "experiment_history.json"
    monkeypatch.setattr(es_mod, "EXPERIMENT_PATH", test_path)

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
    assert ExperimentService.set_starred(hero_id, True)

    hero_records = [
        rec for rec in ExperimentService.get_history(limit=10)
        if rec.get("project_name") == "hero"
    ]
    exported = ExperimentService.export_history(hero_records)
    assert exported["count"] == 1
    assert exported["records"][0]["project_name"] == "hero"

    removed = ExperimentService.clear_history(
        keep_starred=True,
        predicate=lambda rec: rec.get("project_name") == "hero",
    )
    assert removed == 0
    assert ExperimentService.get_run(hero_id) is not None
    assert ExperimentService.get_run(other_id) is not None

    assert ExperimentService.set_starred(hero_id, False)
    removed = ExperimentService.clear_history(
        keep_starred=True,
        predicate=lambda rec: rec.get("project_name") == "hero",
    )
    assert removed == 1
    assert ExperimentService.get_run(hero_id) is None
    assert ExperimentService.get_run(other_id) is not None


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


def test_queue_listing_helper(tmp_path, monkeypatch):
    """_list_queues() correctly parses a synthetic queue file."""
    import web_helpers as web_mod
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
    import web_helpers as web_mod
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


def test_open_path_service_uses_platform_openers(tmp_path, monkeypatch):
    import services.open_path_service as opener

    target = tmp_path / "report.html"
    target.write_text("ok", encoding="utf-8")
    calls = []
    monkeypatch.setattr(opener.subprocess, "Popen", lambda cmd: calls.append(cmd))

    assert opener.open_command_for_platform("darwin", target.resolve()) == ["open", str(target.resolve())]
    assert opener.open_command_for_platform("linux", target.resolve()) == ["xdg-open", str(target.resolve())]

    if opener.os.name != "nt":
        opener.open_path(target)
        assert calls[-1] in (
            ["open", str(target.resolve())],
            ["xdg-open", str(target.resolve())],
        )

