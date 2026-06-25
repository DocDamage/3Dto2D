import json
import os
import subprocess
import threading
import time
import uuid
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = ROOT / "output" / "jobs" / "job_history.json"
LOGS_DIR = ROOT / "logs"
MAX_JOB_HISTORY = 500

class JobService:
    _lock = threading.RLock()
    _current_proc: Optional[subprocess.Popen] = None
    _active_job: Optional[Dict[str, Any]] = None

    @staticmethod
    def _load_history() -> List[Dict[str, Any]]:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        if HISTORY_PATH.exists():
            try:
                return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    @staticmethod
    def _save_history(history: List[Dict[str, Any]]) -> None:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            HISTORY_PATH.write_text(json.dumps(history[:MAX_JOB_HISTORY], indent=2), encoding="utf-8")
        except Exception:
            pass

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
            except Exception:
                pass
        else:
            try:
                import signal
                # Kill the entire process group
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception:
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception:
                    pass

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
                    
                    JobService._active_job["phase"] = "cancelled"
                    JobService._active_job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    JobService._active_job["exit_code"] = -1
                    JobService._active_job["logs"].append(f"[{time.strftime('%H:%M:%S')}] Job cancelled by user (process tree killed).")
                    
                    # Update in history
                    history = JobService._load_history()
                    for idx, j in enumerate(history):
                        if j.get("id") == job_id:
                            history[idx] = JobService._active_job
                            break
                    JobService._save_history(history)
                    return True
            return False

    @staticmethod
    def start_job(title: str, cmd: List[str]) -> Tuple[bool, str]:
        with JobService._lock:
            active = JobService.get_active_job()
            if active and active.get("phase") == "running":
                return False, "A job is already running."

            job_id = str(uuid.uuid4())
            job = {
                "id": job_id,
                "title": title,
                "command": cmd,
                "phase": "running",
                "progress": 0.0,
                "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "finished_at": None,
                "exit_code": None,
                "pid": None,
                "logs": [],
                "log_file": f"logs/web_job_{job_id}.log"
            }
            JobService._active_job = job
            
            # Save to history list
            history = JobService._load_history()
            history.insert(0, job)
            JobService._save_history(history)

        def worker():
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            log_path = LOGS_DIR / f"web_job_{job_id}.log"
            
            def append_log(line: str):
                with JobService._lock:
                    stamp = time.strftime("%H:%M:%S")
                    formatted = f"[{stamp}] {line}"
                    job["logs"].append(formatted)
                    # Limit log length in memory
                    if len(job["logs"]) > 2000:
                        del job["logs"][:-2000]

            append_log(f"▶ Job Started: {title}")
            append_log(f"$ {' '.join(cmd)}")
            
            exit_code = 1
            import re
            progress_pat1 = re.compile(r'(\d+)%\s*\|')
            progress_pat2 = re.compile(r'(?:[Ss]tep|[Ss]teps|[Kk]sampler|progress)?[:\s]*(\d+)\s*/\s*(\d+)', re.IGNORECASE)
            progress_pat3 = re.compile(r'(?:[Pp]rompt\s+)?progress[:\s]*(\d+)%', re.IGNORECASE)

            try:
                with log_path.open("w", encoding="utf-8", errors="replace") as fp:
                    preexec = None
                    if os.name != "nt":
                        preexec = os.setsid

                    proc = subprocess.Popen(
                        cmd,
                        cwd=str(ROOT),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        errors="replace",
                        preexec_fn=preexec
                    )
                    
                    with JobService._lock:
                        JobService._current_proc = proc
                        job["pid"] = proc.pid
                        # Update PID in history immediately
                        hist = JobService._load_history()
                        for idx, j in enumerate(hist):
                            if j.get("id") == job_id:
                                hist[idx] = job
                                break
                        JobService._save_history(hist)

                    assert proc.stdout is not None
                    for line in proc.stdout:
                        line = line.rstrip("\n")
                        fp.write(line + "\n")
                        fp.flush()
                        append_log(line)
                        
                        # Progress parsing
                        m3 = progress_pat3.search(line)
                        if m3:
                            try:
                                with JobService._lock:
                                    job["progress"] = float(m3.group(1))
                            except Exception:
                                pass
                        else:
                            m1 = progress_pat1.search(line)
                            if m1:
                                try:
                                    with JobService._lock:
                                        job["progress"] = float(m1.group(1))
                                except Exception:
                                    pass
                            else:
                                m2 = progress_pat2.search(line)
                                if m2:
                                    try:
                                        curr = int(m2.group(1))
                                        tot = int(m2.group(2))
                                        if tot > 0:
                                            with JobService._lock:
                                                job["progress"] = round((curr / tot) * 100.0, 1)
                                    except Exception:
                                        pass

                    exit_code = proc.wait()
            except Exception as e:
                append_log(f"EXECUTION ERROR: {e}")
            finally:
                with JobService._lock:
                    JobService._current_proc = None
                    # If cancelled, don't overwrite cancelled status
                    if job["phase"] == "running":
                        job["phase"] = "completed" if exit_code == 0 else "failed"
                        job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        job["exit_code"] = exit_code
                        job["progress"] = 100.0 if exit_code == 0 else job["progress"]
                    
                    append_log(f"■ Job finished with exit code {exit_code}")
                    
                    # Update in history file
                    hist = JobService._load_history()
                    for idx, j in enumerate(hist):
                        if j.get("id") == job_id:
                            hist[idx] = job
                            break
                    JobService._save_history(hist)
                    JobService._active_job = None

                    # Record experiment history for generation jobs
                    if exit_code == 0 and any("generate-sprite" in str(c) or "generate_sprite" in str(c) for c in cmd):
                        try:
                            from services.experiment_service import ExperimentService as _ES
                            import re as _re

                            def _arg(flag: str, default: str = "") -> str:
                                try:
                                    idx2 = list(cmd).index(flag)
                                    return str(cmd[idx2 + 1]) if idx2 + 1 < len(cmd) else default
                                except ValueError:
                                    return default

                            # Find newest output sprite folder created since this job started
                            sprite_folder = ""
                            started_ts = job.get("started_at", "")
                            try:
                                from pathlib import Path as _Path
                                import time as _time
                                out_root = ROOT / "output"
                                candidate = max(
                                    (p for p in out_root.rglob("sheet.json")
                                     if p.stat().st_mtime > (_time.mktime(_time.strptime(started_ts, "%Y-%m-%d %H:%M:%S")) if started_ts else 0)),
                                    key=lambda p: p.stat().st_mtime,
                                    default=None,
                                )
                                if candidate:
                                    sprite_folder = str(candidate.parent.relative_to(ROOT)).replace("\\", "/")
                            except Exception:
                                pass

                            seed_str = _arg("--seed")
                            _ES.append_run(
                                job_id=job_id,
                                prompt=_arg("--prompt"),
                                negative=_arg("--negative"),
                                seed=int(seed_str) if seed_str.lstrip("-").isdigit() else None,
                                model_tier=_arg("--tier"),
                                profile=_arg("--profile"),
                                sprite_action=_arg("--action"),
                                direction=_arg("--direction"),
                                sprite_folder=sprite_folder,
                            )
                        except Exception:
                            pass  # Never break normal flow

        threading.Thread(target=worker, daemon=True).start()
        return True, job_id

    @staticmethod
    def recover_interrupted_jobs() -> None:
        with JobService._lock:
            history = JobService._load_history()
            updated = False
            for job in history:
                if job.get("phase") == "running":
                    job["phase"] = "failed"
                    job["exit_code"] = -99
                    job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    job["logs"].append(f"[{time.strftime('%H:%M:%S')}] Server restarted. Job marked as interrupted/failed.")
                    updated = True
            if updated:
                JobService._save_history(history)

    @staticmethod
    def clear_history() -> None:
        with JobService._lock:
            JobService._save_history([])

# Automatically recover any interrupted jobs on load
JobService.recover_interrupted_jobs()
