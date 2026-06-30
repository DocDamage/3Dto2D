import json
import os
import subprocess
import threading
import time
import uuid
import sys
import urllib.parse
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
    def adjust_cmd_for_vram_fallback(cmd: List[str]) -> List[str]:
        new_cmd = list(cmd)
        
        # 1. Downgrade tier from wan22_5b to wan21_safe
        for idx, arg in enumerate(new_cmd):
            if arg == "--tier" and idx + 1 < len(new_cmd):
                if new_cmd[idx + 1] == "wan22_5b":
                    new_cmd[idx + 1] = "wan21_safe"
                    break
                    
        # 2. Downgrade profile to sprite_fast
        for idx, arg in enumerate(new_cmd):
            if arg == "--profile" and idx + 1 < len(new_cmd):
                if new_cmd[idx + 1] in {"quality_local", "wan22_5b_3060_best", "wan22_5b_local"}:
                    new_cmd[idx + 1] = "sprite_fast"
                    break
                    
        # 3. Scale down resolutions/cell-size
        for idx, arg in enumerate(new_cmd):
            if arg == "--cell-size" and idx + 1 < len(new_cmd):
                size_str = new_cmd[idx + 1]
                try:
                    w, h = map(int, size_str.lower().split("x"))
                    new_w = max(128, w // 2)
                    new_h = max(128, h // 2)
                    new_cmd[idx + 1] = f"{new_w}x{new_h}"
                except Exception:
                    pass
                    
        for idx, arg in enumerate(new_cmd):
            if arg == "--resolutions" and idx + 1 < len(new_cmd):
                res_str = new_cmd[idx + 1]
                try:
                    res_parts = res_str.split(",")
                    new_res_parts = []
                    for p in res_parts:
                        w, h = map(int, p.lower().split("x"))
                        new_res_parts.append(f"{max(128, w // 2)}x{max(128, h // 2)}")
                    new_cmd[idx + 1] = ",".join(new_res_parts)
                except Exception:
                    pass
                    
        return new_cmd

    @staticmethod
    def _watch_comfy_websocket(job: Dict[str, Any]) -> None:
        """Bridge ComfyUI websocket progress into the active job when available."""
        prompt_id = str((job.get("metadata") or {}).get("comfy_prompt_id") or "")
        if not prompt_id:
            return
        try:
            import websocket  # type: ignore
            from services.comfy_service import ComfyService
            from services.generation_intelligence import apply_comfy_ws_message
        except Exception:
            with JobService._lock:
                job.setdefault("logs", []).append(f"[{time.strftime('%H:%M:%S')}] ComfyUI websocket bridge unavailable; install websocket-client for exact WAN progress.")
            return

        url = ComfyService.get_url()
        parsed = urllib.parse.urlparse(url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        client_id = str(job.get("id") or uuid.uuid4())
        ws_url = f"{scheme}://{parsed.netloc}/ws?clientId={urllib.parse.quote(client_id)}"
        try:
            ws = websocket.create_connection(ws_url, timeout=3)
            with JobService._lock:
                job["progress_mode"] = "comfy_ws"
                job.setdefault("metadata", {})["comfy_ws_bridge"] = "connected"
            while True:
                with JobService._lock:
                    if job.get("phase") != "running":
                        break
                raw = ws.recv()
                try:
                    message = json.loads(raw)
                except Exception:
                    continue
                with JobService._lock:
                    apply_comfy_ws_message(job, message)
                    done = job.get("stage") in {"complete", "failed", "cancelled"}
                if done:
                    break
        except Exception as exc:
            with JobService._lock:
                job.setdefault("metadata", {})["comfy_ws_bridge"] = "error"
                job.setdefault("logs", []).append(f"[{time.strftime('%H:%M:%S')}] ComfyUI websocket bridge stopped: {exc}")
        finally:
            try:
                ws.close()  # type: ignore[name-defined]
            except Exception:
                pass

    @staticmethod
    def _load_history() -> List[Dict[str, Any]]:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        if HISTORY_PATH.exists():
            try:
                return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            except Exception as e:
                import sys
                print(f"Error loading job history: {e}", file=sys.stderr)
        return []

    @staticmethod
    def _save_history(history: List[Dict[str, Any]]) -> None:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            HISTORY_PATH.write_text(json.dumps(history[:MAX_JOB_HISTORY], indent=2), encoding="utf-8")
        except Exception as e:
            import sys
            print(f"Error saving job history: {e}", file=sys.stderr)

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
                    JobService._active_job["stage"] = "cancelled"
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
                    return True
            return False

    @staticmethod
    def start_job(title: str, cmd: List[str], metadata: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
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
                "stage": "queued",
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

        def worker():
            nonlocal cmd
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

            def set_reported_progress(inner_pct: float) -> None:
                stage = str(job.get("stage") or "")
                if stage in {"wan_sampling", "queued_comfy", "starting"} or any("generate-sprite" in str(c) for c in cmd):
                    whole = 18.0 + (max(0.0, min(100.0, inner_pct)) * 0.42)
                else:
                    whole = inner_pct
                with JobService._lock:
                    job["progress"] = max(float(job.get("progress") or 0.0), min(99.0, float(whole)))
                    job["progress_mode"] = "reported"

            def set_stage(stage: str, label: str, detail: str, progress: Optional[float] = None, mode: str = "estimated") -> None:
                with JobService._lock:
                    job["stage"] = stage
                    job["stage_label"] = label
                    job["stage_detail"] = detail
                    job["progress_mode"] = mode
                    if progress is not None:
                        job["progress"] = max(float(job.get("progress") or 0.0), min(99.0, float(progress)))

            def infer_stage_from_line(line_text: str) -> None:
                text = line_text.lower()
                if "queued comfyui prompt" in text or "prompt id:" in text:
                    set_stage("queued_comfy", "Queued in ComfyUI", "Prompt accepted by ComfyUI.", 12)
                    try:
                        prompt_match = re.search(r"prompt id[:\s]+([0-9a-fA-F-]+)", line_text, re.IGNORECASE)
                        if prompt_match:
                            with JobService._lock:
                                metadata = job.setdefault("metadata", {})
                                if not metadata.get("comfy_prompt_id"):
                                    metadata["comfy_prompt_id"] = prompt_match.group(1)
                                    threading.Thread(target=JobService._watch_comfy_websocket, args=(job,), daemon=True).start()
                    except Exception:
                        pass
                elif "waiting for exact comfyui prompt history output" in text:
                    set_stage("wan_sampling", "Generating video", "ComfyUI is running the WAN workflow.", 18)
                elif "resolved output" in text or "history output" in text or "chosen output" in text:
                    set_stage("resolve_output", "Resolving output", "Finding the exact video produced by this prompt.", 62)
                elif "converting" in text and ("video" in text or "spritesheet" in text):
                    set_stage("convert_video", "Converting video", "Extracting frames and preparing the sprite sheet.", 72)
                elif "sprite output" in text or "sheet:" in text or "preview:" in text or "metadata:" in text:
                    set_stage("pack_sprite", "Packing sprite", "Writing sheet, preview, and metadata.", 88)
                elif "quality" in text or "qa report" in text:
                    set_stage("qa", "Quality check", "Running quality analysis and writing the report.", 92)
                elif "download" in text:
                    set_stage("download", "Downloading", "Downloading or checking model files.", 35)
                elif "install" in text:
                    set_stage("install", "Installing", "Installing or updating dependencies.", 35)
                elif "error:" in text or "traceback" in text or "returned non-zero" in text:
                    set_stage("error", "Error detected", line_text[-180:], None)

            set_stage("starting", "Starting", "Launching command process.", 2)

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

                    oom_detected = False
                    assert proc.stdout is not None
                    for line in proc.stdout:
                        line = line.rstrip("\n")
                        fp.write(line + "\n")
                        fp.flush()
                        append_log(line)
                        infer_stage_from_line(line)
                        
                        if "cuda out of memory" in line.lower() or "outofmemoryerror" in line.lower():
                            oom_detected = True
                        
                        # Progress parsing
                        m3 = progress_pat3.search(line)
                        if m3:
                            try:
                                set_reported_progress(float(m3.group(1)))
                            except Exception:
                                pass
                        else:
                            m1 = progress_pat1.search(line)
                            if m1:
                                try:
                                    set_reported_progress(float(m1.group(1)))
                                except Exception:
                                    pass
                            else:
                                m2 = progress_pat2.search(line)
                                if m2:
                                    try:
                                        curr = int(m2.group(1))
                                        tot = int(m2.group(2))
                                        if tot > 0:
                                            set_reported_progress(round((curr / tot) * 100.0, 1))
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
                        if exit_code != 0 and oom_detected and job.setdefault("metadata", {}).setdefault("vram_retry_count", 0) < 2:
                            retry_count = job["metadata"]["vram_retry_count"] + 1
                            job["metadata"]["vram_retry_count"] = retry_count
                            
                            new_cmd = JobService.adjust_cmd_for_vram_fallback(cmd)
                            cmd = new_cmd
                            job["command"] = new_cmd
                            
                            append_log(f"⚠️ CUDA Out of Memory detected. Retrying with lower VRAM profile (Attempt {retry_count}/2)...")
                            append_log(f"New Command: {' '.join(new_cmd)}")
                            
                            job["stage"] = "queued"
                            job["stage_label"] = "Retrying (VRAM Fallback)"
                            job["stage_detail"] = f"Retrying with lower VRAM profile (Attempt {retry_count})."
                            job["progress"] = 0.0
                            
                            # Update in history
                            history = JobService._load_history()
                            for idx, j in enumerate(history):
                                if j.get("id") == job_id:
                                    history[idx] = job
                                    break
                            JobService._save_history(history)
                            
                            # Restart worker thread
                            threading.Thread(target=worker, daemon=True).start()
                            return

                        job["phase"] = "completed" if exit_code == 0 else "failed"
                        job["stage"] = "complete" if exit_code == 0 else "failed"
                        job["stage_label"] = "Passed" if exit_code == 0 else "Failed"
                        job["stage_detail"] = "Task completed successfully." if exit_code == 0 else f"Task failed with exit code {exit_code}."
                        job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        job["exit_code"] = exit_code
                        job["progress"] = 100.0 if exit_code == 0 else max(float(job.get("progress") or 0.0), 100.0)
                    
                    # Determine output sprite folder
                    sprite_folder = ""
                    if exit_code == 0:
                        try:
                            for idx, val in enumerate(cmd):
                                if val in {"--output", "--sprite-dir"}:
                                    out_val = cmd[idx + 1]
                                    p_out = Path(out_val)
                                    if p_out.is_absolute():
                                        sprite_folder = str(p_out.relative_to(ROOT)).replace("\\", "/")
                                    else:
                                        sprite_folder = str(out_val).replace("\\", "/")
                                    break
                        except Exception:
                            pass
                        
                        if not sprite_folder and any(x in str(c) for x in ("generate-sprite", "generate_sprite") for c in cmd):
                            started_ts = job.get("started_at", "")
                            try:
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
                    if sprite_folder:
                        job["metadata"]["sprite_folder"] = sprite_folder
                        if any("generate-sprite" in str(c) or "generate_sprite" in str(c) for c in cmd):
                            try:
                                from services.generation_intelligence import build_visual_report, summarize_qa_gates

                                sprite_abs = (ROOT / sprite_folder).resolve()
                                visual = build_visual_report(sprite_abs)
                                job["metadata"]["visual_report"] = visual
                                qa_data: Dict[str, Any] = {}
                                for report_rel in ["qa/qa_report.json", "qa_report.json", "quality_report.json"]:
                                    p = sprite_abs / report_rel
                                    if p.exists():
                                        qa_data = json.loads(p.read_text(encoding="utf-8"))
                                        break
                                job["metadata"]["qa_gate"] = summarize_qa_gates(qa_data) if qa_data else {
                                    "status": "warning",
                                    "reasons": ["QA report was not found after generation."],
                                    "score": None,
                                    "issue_count": 0,
                                }
                            except Exception as exc:
                                job["metadata"]["visual_report_error"] = str(exc)

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
                                project_name=str(job.get("metadata", {}).get("project_name", "")),
                                project_path=str(job.get("metadata", {}).get("project_path", "")),
                                project_root=str(job.get("metadata", {}).get("project_root", "")),
                            )
                        except Exception:
                            pass  # Never break normal flow

                    if exit_code == 0 and any("qa-report" in str(c) for c in cmd):
                        try:
                            JobService._record_qa_result(cmd)
                        except Exception:
                            pass  # Never break normal flow

        threading.Thread(target=worker, daemon=True).start()
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
