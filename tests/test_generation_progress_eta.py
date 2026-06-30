import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from services.generation_intelligence import update_job_timing


def test_update_job_timing_adds_elapsed_and_remaining(monkeypatch):
    monkeypatch.setattr("services.generation_intelligence.time.time", lambda: 1_000.0)
    monkeypatch.setattr("services.generation_intelligence._parse_stamp", lambda value: 900.0)
    job = {
        "started_at": "2026-06-30 12:00:00",
        "progress": 25.0,
        "metadata": {"eta": {"seconds": 400, "label": "about 6m 40s"}},
    }

    update_job_timing(job)

    assert job["elapsed_seconds"] == 100
    assert job["remaining_seconds"] == 300
    assert job["eta_label"] == "about 5m 0s remaining"
    assert job["progress_percent"] == 25.0


def test_update_job_timing_handles_unknown_eta(monkeypatch):
    monkeypatch.setattr("services.generation_intelligence.time.time", lambda: 1_000.0)
    monkeypatch.setattr("services.generation_intelligence._parse_stamp", lambda value: 950.0)
    job = {"started_at": "2026-06-30 12:00:00", "progress": 40.0, "metadata": {}}

    update_job_timing(job)

    assert job["elapsed_seconds"] == 50
    assert job["remaining_seconds"] is None
    assert job["eta_label"] == "learning from this run"
