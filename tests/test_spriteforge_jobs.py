import sys
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add app directory to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

def test_job_lifecycle(tmp_path):
    from services.job_service import JobService
    import services.job_service

    temp_history = tmp_path / "job_history.json"

    with patch("services.job_service.HISTORY_PATH", temp_history):
        # 1. Initially empty history
        assert JobService.get_history() == []

        # 2. Recovery transitions running -> failed
        running_job = {
            "id": "test-uuid-123",
            "title": "Running Job",
            "command": ["echo", "test"],
            "phase": "running",
            "progress": 50.0,
            "started_at": "2026-06-25 12:00:00",
            "finished_at": None,
            "exit_code": None,
            "pid": 1111,
            "logs": ["Starting"],
        }
        JobService._save_history([running_job])

        JobService.recover_interrupted_jobs()

        history = JobService.get_history()
        assert len(history) == 1
        assert history[0]["phase"] == "failed"
        assert history[0]["exit_code"] == -99
        assert history[0]["finished_at"] is not None

        # 3. Start a new job and cancel it
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_proc.poll.return_value = None
        mock_proc.stdout = ["progress: 50%", "step: 5/10"]
        
        import threading
        wait_event = threading.Event()
        mock_proc.wait.side_effect = lambda: (wait_event.wait(), 0)[1]

        # Reset active job
        JobService._active_job = None

        with patch("subprocess.Popen", return_value=mock_proc):
            ok, job_id = JobService.start_job(
                "New Test Job", ["echo", "hello"], metadata={"project_name": "hero"}
            )
            assert ok is True
            assert len(job_id) == 36

            # Wait briefly for worker thread to record PID
            for _ in range(20):
                active = JobService.get_active_job()
                if active and active.get("pid") is not None:
                    break
                time.sleep(0.05)

            active = JobService.get_active_job()
            assert active is not None
            assert active["pid"] == 9999
            assert active["metadata"]["project_name"] == "hero"

            with patch(
                "services.job_service.JobService._kill_process_tree"
            ) as mock_kill:
                cancelled = JobService.cancel_job(job_id)
                assert cancelled is True
                mock_kill.assert_called_once_with(9999)
                
                # Release wait event so the worker thread finishes
                wait_event.set()
                # Wait for active job to finish cleaning up
                for _ in range(20):
                    if JobService.get_active_job() is None:
                        break
                    time.sleep(0.05)

                hist = JobService.get_history()
                c_job = next(j for j in hist if j["id"] == job_id)
                assert c_job["phase"] == "cancelled"
                assert c_job["exit_code"] == -1

def test_job_history_retention(tmp_path):
    import services.job_service
    from services.job_service import JobService

    temp_history = tmp_path / "job_history.json"
    jobs = [{"id": str(i), "phase": "completed", "logs": []} for i in range(5)]

    with patch("services.job_service.HISTORY_PATH", temp_history), patch("services.job_service.MAX_JOB_HISTORY", 3):
        JobService._save_history(jobs)
        history = JobService.get_history()

    assert [job["id"] for job in history] == ["0", "1", "2"]
