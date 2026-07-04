import json
import logging
import os
import queue
import subprocess
import threading
import time
import uuid
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from services.job_artifact_service import command_sprite_folder
from services.job_output_parser import parse_job_output_line
from services.oom_recovery_service import progressive_vram_fallback
from services.websocket_service import ProgressEventHub, job_event_payload
from spriteforge_utils import ROOT, load_json, save_json

HISTORY_PATH = ROOT / "output" / "jobs" / "job_history.json"
LOGS_DIR = ROOT / "logs"
MAX_JOB_HISTORY = 500
logger = logging.getLogger(__name__)


class JobPhase:
    """Canonical job lifecycle phases used by JobRunner and JobService."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStage:
    """Canonical coarse job stages for UI/progress lifecycle events."""

    QUEUED = "queued"
    STARTING = "starting"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobRunner:
    """Runs a single job command and owns its execution state transitions."""

    MAX_VRAM_RETRIES = 4

    def __init__(self, job: Dict[str, Any], cmd: List[str]) -> None:
        self.job = job
        self.job_id = str(job.get("id") or "")
        self.cmd = list(cmd)
        self.oom_detected = False
        self.retry_queue: "queue.SimpleQueue[List[str]]" = queue.SimpleQueue()

    def start(self) -> None:
        threading.Thread(target=self.run, daemon=True).start()

    def run(self) -> None:
        while True:
            exit_code = self._run_once()
            if not self._handle_completion(exit_code):
                return
            self.cmd = self.retry_queue.get()

    def _append_log(self, line: str) -> None:
        with JobService._lock:
            stamp = time.strftime("%H:%M:%S")
            formatted = f"[{stamp}] {line}"
            self.job["logs"].append(formatted)
            if len(self.job["logs"]) > 2000:
                del self.job["logs"][:-2000]
        ProgressEventHub.publish("job.log", {**job_event_payload(self.job), "line": formatted})

    def _set_reported_progress(self, inner_pct: float) -> None:
        stage = str(self.job.get("stage") or "")
        if stage in {"wan_sampling", "queued_comfy", JobStage.STARTING} or any("generate-sprite" in str(c) for c in self.cmd):
            whole = 18.0 + (max(0.0, min(100.0, inner_pct)) * 0.42)
        else:
            whole = inner_pct
        with JobService._lock:
            self.job["progress"] = max(float(self.job.get("progress") or 0.0), min(99.0, float(whole)))
            self.job["progress_mode"] = "reported"
            payload = job_event_payload(self.job)
        ProgressEventHub.publish("job.progress", payload)

    def _set_stage(self, stage: str, label: str, detail: str, progress: Optional[float] = None, mode: str = "estimated") -> None:
        with JobService._lock:
            self.job["stage"] = stage
            self.job["stage_label"] = label
            self.job["stage_detail"] = detail
            self.job["progress_mode"] = mode
            if progress is not None:
                self.job["progress"] = max(float(self.job.get("progress") or 0.0), min(99.0, float(progress)))
            payload = job_event_payload(self.job)
        ProgressEventHub.publish("job.stage", payload)

    def _sync_history(self) -> None:
        history = JobService._load_history()
        for idx, row in enumerate(history):
            if row.get("id") == self.job_id:
                history[idx] = self.job
                break
        JobService._save_history(history)

    def _run_once(self) -> int:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOGS_DIR / f"web_job_{self.job_id}.log"
        self.oom_detected = False
        exit_code = 1

        self._append_log(f"▶ Job Started: {self.job.get('title')}")
        self._append_log(f"$ {' '.join(self.cmd)}")
        self._set_stage(JobStage.STARTING, "Starting", "Launching command process.", 2)

        try:
            with log_path.open("w", encoding="utf-8", errors="replace") as fp:
                preexec = os.setsid if os.name != "nt" else None
                proc = subprocess.Popen(
                    self.cmd,
                    cwd=str(ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    errors="replace",
                    preexec_fn=preexec,
                )
                with JobService._lock:
                    JobService._current_proc = proc
                    self.job["pid"] = proc.pid
                    self._sync_history()

                assert proc.stdout is not None
                for line in proc.stdout:
                    self._handle_output_line(line.rstrip("\n"), fp)
                exit_code = proc.wait()
        except Exception as exc:
            logger.exception("Job %s execution failed before process completion.", self.job_id)
            self._append_log(f"EXECUTION ERROR: {exc}")
        finally:
            with JobService._lock:
                JobService._current_proc = None

        return exit_code

    def _handle_output_line(self, line: str, fp: Any) -> None:
        fp.write(line + "\n")
        fp.flush()
        self._append_log(line)
        parsed = parse_job_output_line(line)
        if parsed.stage:
            self._set_stage(parsed.stage, parsed.stage_label, parsed.stage_detail, parsed.stage_progress)

        if parsed.prompt_id:
            try:
                with JobService._lock:
                    metadata = self.job.setdefault("metadata", {})
                    if not metadata.get("comfy_prompt_id"):
                        metadata["comfy_prompt_id"] = parsed.prompt_id
                        from services.comfy_service import ComfyService
                        threading.Thread(target=ComfyService.watch_websocket, args=(self.job, JobService._lock), daemon=True).start()
            except Exception as exc:
                logger.warning("Could not attach ComfyUI websocket watcher to job %s: %s", self.job_id, exc)

        if parsed.source_video:
            with JobService._lock:
                self.job.setdefault("metadata", {})["output_video"] = parsed.source_video

        if parsed.sprite_output:
            raw_sprite = parsed.sprite_output
            try:
                p = Path(raw_sprite)
                sprite_rel = str(p.resolve().relative_to(ROOT.resolve())).replace("\\", "/") if p.is_absolute() else raw_sprite.replace("\\", "/")
            except Exception as exc:
                logger.debug("Could not normalize sprite output path %s: %s", raw_sprite, exc)
                sprite_rel = raw_sprite.replace("\\", "/")
            with JobService._lock:
                self.job.setdefault("metadata", {})["sprite_folder"] = sprite_rel

        if parsed.oom_detected:
            self.oom_detected = True

        if parsed.progress_percent is not None:
            self._set_reported_progress(parsed.progress_percent)

    def _handle_completion(self, exit_code: int) -> bool:
        with JobService._lock:
            if self.job["phase"] != JobPhase.RUNNING:
                self._sync_history()
                ProgressEventHub.publish("job.complete", job_event_payload(self.job))
                JobService._active_job = None
                return False

            if self._prepare_vram_retry(exit_code):
                return True

            self.job["phase"] = JobPhase.COMPLETED if exit_code == 0 else JobPhase.FAILED
            self.job["stage"] = JobStage.COMPLETE if exit_code == 0 else JobStage.FAILED
            self.job["stage_label"] = "Passed" if exit_code == 0 else "Failed"
            self.job["stage_detail"] = "Task completed successfully." if exit_code == 0 else f"Task failed with exit code {exit_code}."
            self.job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self.job["exit_code"] = exit_code
            self.job["progress"] = 100.0 if exit_code == 0 else max(float(self.job.get("progress") or 0.0), 100.0)

            self._attach_success_artifacts(exit_code)
            self._append_log(f"■ Job finished with exit code {exit_code}")
            self._sync_history()
            JobService._notify_async("complete", dict(self.job))
            ProgressEventHub.publish("job.complete", job_event_payload(self.job))
            JobService._active_job = None

        self._record_followup_data(exit_code)
        return False

    def _prepare_vram_retry(self, exit_code: int) -> bool:
        retry_count = int(self.job.setdefault("metadata", {}).setdefault("vram_retry_count", 0))
        if exit_code == 0 or not self.oom_detected or retry_count >= self.MAX_VRAM_RETRIES:
            return False

        retry_count += 1
        self.job["metadata"]["vram_retry_count"] = retry_count
        fallback = progressive_vram_fallback(self.cmd, retry_count)
        self.retry_queue.put(fallback.command)
        self.job["command"] = fallback.command
        self.job["metadata"]["vram_fallback"] = fallback.label
        self._append_log(f"CUDA Out of Memory detected. Retrying with {fallback.label} (Attempt {retry_count}/4).")
        self._append_log(fallback.detail)
        self._append_log(f"New Command: {' '.join(fallback.command)}")
        self.job["stage"] = JobStage.QUEUED
        self.job["stage_label"] = "Retrying (VRAM Fallback)"
        self.job["stage_detail"] = f"{fallback.detail} Attempt {retry_count}/4."
        self.job["progress"] = 0.0
        self._sync_history()
        return True

    def _attach_success_artifacts(self, exit_code: int) -> None:
        sprite_folder = command_sprite_folder(ROOT, self.cmd, str(self.job.get("started_at") or "")) if exit_code == 0 else ""
        if not sprite_folder:
            return
        self.job.setdefault("metadata", {})["sprite_folder"] = sprite_folder
        if not any("generate-sprite" in str(c) or "generate_sprite" in str(c) for c in self.cmd):
            return
        try:
            from services.generation_intelligence import build_visual_report, summarize_qa_gates

            sprite_abs = (ROOT / sprite_folder).resolve()
            visual = build_visual_report(sprite_abs)
            self.job["metadata"]["visual_report"] = visual
            qa_data: Dict[str, Any] = {}
            for report_rel in ["qa/qa_report.json", "qa_report.json", "quality_report.json"]:
                p = sprite_abs / report_rel
                if p.exists():
                    qa_data = json.loads(p.read_text(encoding="utf-8"))
                    break
            self.job["metadata"]["qa_gate"] = summarize_qa_gates(qa_data) if qa_data else {
                "status": "warning",
                "reasons": ["QA report was not found after generation."],
                "score": None,
                "issue_count": 0,
            }
        except Exception as exc:
            self.job["metadata"]["visual_report_error"] = str(exc)
            logger.warning("Could not build visual report for job %s: %s", self.job_id, exc)

    def _record_followup_data(self, exit_code: int) -> None:
        if exit_code == 0 and any("generate-sprite" in str(c) or "generate_sprite" in str(c) for c in self.cmd):
            try:
                from services.experiment_service import ExperimentService as _ES

                def _arg(flag: str, default: str = "") -> str:
                    try:
                        idx2 = list(self.cmd).index(flag)
                        return str(self.cmd[idx2 + 1]) if idx2 + 1 < len(self.cmd) else default
                    except ValueError:
                        return default

                sprite_folder = command_sprite_folder(ROOT, self.cmd, str(self.job.get("started_at") or ""))
                output_video = str(self.job.get("metadata", {}).get("output_video", ""))
                seed_str = _arg("--seed")
                _ES.append_run(
                    job_id=self.job_id,
                    prompt=_arg("--prompt"),
                    negative=_arg("--negative"),
                    seed=int(seed_str) if seed_str.lstrip("-").isdigit() else None,
                    model_tier=_arg("--tier"),
                    profile=_arg("--profile"),
                    sprite_action=_arg("--action"),
                    direction=_arg("--direction"),
                    output_video=output_video,
                    sprite_folder=sprite_folder,
                    project_name=str(self.job.get("metadata", {}).get("project_name", "")),
                    project_path=str(self.job.get("metadata", {}).get("project_path", "")),
                    project_root=str(self.job.get("metadata", {}).get("project_root", "")),
                )
            except Exception as exc:
                logger.warning("Could not record generation experiment for job %s: %s", self.job_id, exc)

        if exit_code == 0 and any("qa-report" in str(c) for c in self.cmd):
            try:
                JobService._record_qa_result(self.cmd)
            except Exception as exc:
                logger.warning("Could not record QA result for job %s: %s", self.job_id, exc)


class JobService:
    _lock = threading.RLock()
    _current_proc: Optional[subprocess.Popen] = None
    _active_job: Optional[Dict[str, Any]] = None

    @staticmethod
    def adjust_cmd_for_vram_fallback(cmd: List[str]) -> List[str]:
        return progressive_vram_fallback(cmd, attempt=1).command

    @staticmethod
    def _load_history() -> List[Dict[str, Any]]:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        history = load_json(HISTORY_PATH, [])
        if isinstance(history, list):
            return history
        logger.warning("Job history was not a list in %s; ignoring corrupt payload.", HISTORY_PATH)
        return []

    @staticmethod
    def _save_history(history: List[Dict[str, Any]]) -> None:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        save_json(HISTORY_PATH, history[:MAX_JOB_HISTORY])

    @staticmethod
    def get_history() -> List[Dict[str, Any]]:
        with JobService._lock:
            return JobService._load_history()

    @staticmethod
    def get_job(job_id: str) -> Optional[Dict[str, Any]]:
        with JobService._lock:
            for job in JobService._load_history():
                if job.get("id") == job_id:
                    return job
            return None

    @staticmethod
    def get_active_job() -> Optional[Dict[str, Any]]:
        with JobService._lock:
            return JobService._active_job

    @staticmethod
    def _kill_process_tree(pid: int) -> None:
        if os.name == "nt":
            try:
                # Force kill process and all child processes recursively
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=5)
            except Exception as exc:
                logger.warning("Could not kill Windows process tree for pid %s: %s", pid, exc)
        else:
            try:
                import signal
                # Kill the entire process group
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception as exc:
                logger.warning("Could not kill process group for pid %s: %s", pid, exc)
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception as exc:
                    logger.warning("Could not kill process %s: %s", pid, exc)

    @staticmethod
    def _notify_async(kind: str, job: Dict[str, Any]) -> None:
        def runner() -> None:
            try:
                from services.notification_service import notify_on_job_complete, notify_on_job_start
                if kind == "start":
                    notify_on_job_start(job)
                else:
                    notify_on_job_complete(job)
            except Exception as exc:
                logger.warning("Notification dispatch failed for job %s: %s", job.get("id"), exc)
        threading.Thread(target=runner, daemon=True).start()

    @staticmethod
    def cancel_job(job_id: str) -> bool:
        with JobService._lock:
            if JobService._active_job and JobService._active_job.get("id") == job_id:
                if JobService._current_proc and JobService._current_proc.poll() is None:
                    pid = JobService._active_job.get("pid")
                    if pid:
                        JobService._kill_process_tree(pid)
                    else:
                        JobService._current_proc.terminate()
                    
                    JobService._active_job["phase"] = JobPhase.CANCELLED
                    JobService._active_job["stage"] = JobStage.CANCELLED
                    JobService._active_job["stage_label"] = "Cancelled"
                    JobService._active_job["stage_detail"] = "Task was cancelled by the user."
                    JobService._active_job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    JobService._active_job["exit_code"] = -1
                    JobService._active_job["progress"] = 100.0
                    JobService._active_job["logs"].append(f"[{time.strftime('%H:%M:%S')}] Job cancelled by user (process tree killed).")
                    
                    # Update in history
                    history = JobService._load_history()
                    for idx, j in enumerate(history):
                        if j.get("id") == job_id:
                            history[idx] = JobService._active_job
                            break
                    JobService._save_history(history)
                    cancelled_job = dict(JobService._active_job)
                    JobService._notify_async("complete", cancelled_job)
                    ProgressEventHub.publish("job.complete", job_event_payload(cancelled_job))
                    JobService._active_job = None
                    return True
            return False

    @staticmethod
    def start_job(title: str, cmd: List[str], metadata: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        with JobService._lock:
            active = JobService.get_active_job()
            if active and active.get("phase") == JobPhase.RUNNING:
                return False, "A job is already running."

            job_id = str(uuid.uuid4())
            job = {
                "id": job_id,
                "title": title,
                "command": cmd,
                "phase": JobPhase.RUNNING,
                "stage": JobStage.QUEUED,
                "stage_label": "Queued",
                "stage_detail": "Waiting for the worker to start.",
                "progress": 0.0,
                "progress_mode": "estimated",
                "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "finished_at": None,
                "exit_code": None,
                "pid": None,
                "logs": [],
                "log_file": f"logs/web_job_{job_id}.log",
                "metadata": metadata or {},
            }
            JobService._active_job = job
            
            # Save to history list
            history = JobService._load_history()
            history.insert(0, job)
            JobService._save_history(history)
            JobService._notify_async("start", dict(job))
            ProgressEventHub.publish("job.queued", job_event_payload(job))

        JobRunner(job, cmd).start()
        return True, job_id

    @staticmethod
    def _record_qa_result(cmd: List[str]) -> bool:
        """Attach a completed QA report to the newest matching experiment run."""
        def _arg(flag: str, default: str = "") -> str:
            try:
                idx = list(cmd).index(flag)
                return str(cmd[idx + 1]) if idx + 1 < len(cmd) else default
            except ValueError:
                return default

        sprite_arg = _arg("--input")
        if not sprite_arg:
            return False
        sprite_path = Path(sprite_arg)
        sprite_dir = sprite_path.resolve() if sprite_path.is_absolute() else (ROOT / sprite_path).resolve()
        try:
            sprite_folder = str(sprite_dir.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            sprite_folder = str(sprite_dir).replace("\\", "/")

        output_arg = _arg("--output")
        report_dir = Path(output_arg).resolve() if output_arg else sprite_dir / "qa"
        report_path = report_dir / "qa_report.json"
        if not report_path.exists():
            report_path = report_dir / "quality_report.json"
        if not report_path.exists():
            return False

        report = json.loads(report_path.read_text(encoding="utf-8"))
        issues = report.get("issues") or []
        blocking = [
            issue for issue in issues
            if str(issue.get("level", "")).lower() in {"error", "warn", "warning"}
        ]
        qa_passed = not blocking
        qa_score = report.get("score")
        if qa_score is None:
            errors = sum(1 for issue in issues if str(issue.get("level", "")).lower() == "error")
            warnings = sum(1 for issue in issues if str(issue.get("level", "")).lower() in {"warn", "warning"})
            qa_score = max(0.0, 100.0 - (errors * 35.0) - (warnings * 15.0))
        try:
            qa_score = float(qa_score)
        except (TypeError, ValueError):
            qa_score = None

        from services.experiment_service import ExperimentService
        return ExperimentService.update_qa_for_sprite(sprite_folder, qa_score, qa_passed)

    @staticmethod
    def recover_interrupted_jobs() -> None:
        with JobService._lock:
            history = JobService._load_history()
            updated = False
            for job in history:
                if job.get("phase") == JobPhase.RUNNING:
                    job["phase"] = JobPhase.FAILED
                    job["stage"] = JobStage.FAILED
                    job["stage_label"] = "Interrupted"
                    job["stage_detail"] = "Server restarted while this job was running."
                    job["exit_code"] = -99
                    job["progress"] = max(float(job.get("progress") or 0.0), 100.0)
                    job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    job["logs"].append(f"[{time.strftime('%H:%M:%S')}] Server restarted. Job marked as interrupted/failed.")
                    ProgressEventHub.publish("job.complete", job_event_payload(job))
                    updated = True
            if updated:
                JobService._save_history(history)

    @staticmethod
    def clear_history() -> None:
        with JobService._lock:
            JobService._save_history([])

# Automatically recover any interrupted jobs on load
JobService.recover_interrupted_jobs()
