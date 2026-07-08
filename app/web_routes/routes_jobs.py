from flask import Blueprint, request, jsonify, Response
import time
import json
import shutil
from pathlib import Path

from services.job_service import JobService
from services.comfy_service import ComfyService
from services.model_service import ModelService
from services.generation_intelligence import estimate_job_eta, preflight_generation, safer_retry_payload, rerun_similar_payload, update_job_timing
from services.lora_training_service import register_external_lora_checkpoint
from web_helpers import (
    ROOT, OUTPUT, LOGS, PYTHON,
    build_action_command, _project_meta_from_query, _project_workspace,
    _resolve_queue_path, _queue_job_progress, _queue_progress,
    _get_failed_reason, _ab_run_create, _ab_run_list, _list_queues,
    _list_packs, _list_releases, _list_quality_reports, _list_references,
    _project_asset_counts, _project_workspace, _experiment_rows
)
from services.lora_training_progress_service import summarize_lora_training_progress

routes_jobs = Blueprint("routes_jobs", __name__)

ARCHETYPE_PROVENANCE_SCHEMA = "spriteforge.archetype_generation_provenance.v1"
ALL_DIRECTIONS = ["front", "front_right", "right", "back_right", "back", "back_left", "left", "front_left"]
LORA_CHECKPOINT_SUFFIXES = {".safetensors", ".pt", ".ckpt"}


def _csv_values(value, default=None):
    items = [item.strip() for item in str(value or "").split(",") if item.strip()]
    return items or list(default or [])


def _expand_directions(value, default=None):
    directions = _csv_values(value, default or ["right"])
    if any(direction.lower() == "all" for direction in directions):
        return list(ALL_DIRECTIONS)
    return directions


def _resolve_workspace_path(value, label="path"):
    raw = Path(str(value or "").strip())
    if not str(raw):
        raise ValueError(f"{label} is required")
    path = raw if raw.is_absolute() else ROOT / raw
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the SpriteForge workspace.") from exc
    return resolved


def _latest_lora_checkpoint(run_dir):
    candidates = [
        path for path in run_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in LORA_CHECKPOINT_SUFFIXES
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _truthy(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _job_status_payload(job, running: bool):
    if not job:
        return {"running": False, "title": "Idle", "progress": 0.0, "exit_code": None, "logs": [], "started_at": None, "finished_at": None}
    job_status = dict(job)
    job_status["running"] = running
    return update_job_timing(job_status)


def _archetype_generation_provenance(payload: dict) -> dict | None:
    archetype_id = str(payload.get("archetype_id") or "").strip()
    archetype_name = str(payload.get("archetype_name") or "").strip()
    if not archetype_id and not archetype_name:
        return None
    tags = [
        tag.strip()
        for tag in str(payload.get("archetype_tags") or "").split(",")
        if tag.strip()
    ]
    customized_raw = str(payload.get("archetype_customized") or "").strip().lower()
    return {
        "schema": ARCHETYPE_PROVENANCE_SCHEMA,
        "id": archetype_id,
        "name": archetype_name,
        "tags": tags,
        "palette_hint": str(payload.get("archetype_palette_hint") or "").strip(),
        "customized": customized_raw in {"1", "true", "yes", "on"},
        "source": "generate_view_visual_card",
    }


@routes_jobs.route("/api/job", methods=["GET"])
def get_job():
    active_job = JobService.get_active_job()
    if active_job:
        job_status = _job_status_payload(active_job, True)
    else:
        history = JobService.get_history()
        if history:
            job_status = _job_status_payload(history[0], False)
        else:
            job_status = _job_status_payload(None, False)
    return jsonify(job_status)

@routes_jobs.route("/api/job/history", methods=["GET"])
def get_job_history():
    return jsonify({"history": JobService.get_history()})

@routes_jobs.route("/api/job/detail", methods=["GET"])
def get_job_detail():
    job_id = request.args.get("id", "")
    if not job_id:
        return jsonify({"error": "Missing job id"}), 400
    job = JobService.get_job(job_id)
    if not job:
        active = JobService.get_active_job()
        if active and active.get("id") == job_id:
            job = active
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    job_dict = update_job_timing(dict(job))
    log_file = ROOT / job_dict.get("log_file", f"logs/web_job_{job_id}.log")
    if log_file.exists():
        try:
            job_dict["full_logs"] = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            job_dict["full_logs"] = job_dict.get("logs", [])
    else:
        job_dict["full_logs"] = job_dict.get("logs", [])
    return jsonify(job_dict)

@routes_jobs.route("/api/queues", methods=["GET"])
def get_queues():
    project_meta = _project_meta_from_query(request.args.to_dict(flat=False))
    return jsonify({"queues": _list_queues(project_meta), "project_workspace": _project_workspace(project_meta)})

@routes_jobs.route("/api/queues/detail", methods=["GET"])
def get_queue_detail():
    qpath_str = request.args.get("path", "")
    if not qpath_str:
        return jsonify({"error": "path required"}), 400
    try:
        qpath = _resolve_queue_path(qpath_str)
        data = json.loads(qpath.read_text(encoding="utf-8"))
        counts = {}
        for job in data.get("jobs", []):
            status = job.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
            job["progress"] = _queue_job_progress(job)
            if job.get("status") == "failed":
                job["failed_reason"] = _get_failed_reason(job.get("log"))
        data["progress"] = _queue_progress(counts, len(data.get("jobs", [])))
        return jsonify(data)
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 403
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@routes_jobs.route("/api/status/stream", methods=["GET"])
def status_stream():
    def event_stream():
        heartbeat_interval = 15
        last_heartbeat = 0
        try:
            while True:
                try:
                    active_job = JobService.get_active_job()
                    if active_job:
                        job_status = _job_status_payload(active_job, True)
                    else:
                        history = JobService.get_history()
                        if history:
                            job_status = _job_status_payload(history[0], False)
                        else:
                            job_status = _job_status_payload(None, False)
                    
                    data = {
                        "comfy_running": ComfyService.is_running(),
                        "comfy_url": ComfyService.get_url(),
                        "gpu": ComfyService.get_gpu_info(),
                        "job": job_status,
                        "time": time.strftime("%H:%M:%S")
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                    
                    now = time.time()
                    if now - last_heartbeat > heartbeat_interval:
                        yield ": heartbeat\n\n"
                        last_heartbeat = now
                    
                    time.sleep(0.5)
                except GeneratorExit:
                    break
                except Exception as exc:
                    import logging
                    logging.getLogger("routes_jobs").debug("Status SSE stream loop encountered exception: %s", exc, exc_info=True)
                    time.sleep(1)
        except GeneratorExit:
            pass
            
    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )

@routes_jobs.route("/api/run", methods=["POST"])
def run_action():
    payload = request.json or {}
    force = bool(payload.get("force", False))
    action = payload.get("action", "generate_sprite")
    
    # Disk Budget Guard check
    estimated_gb = 1.0
    if action in {"generate_sprite", "animate_existing_sprite"}:
        act_list = _csv_values(payload.get("default_actions") or payload.get("actions") or payload.get("sprite_action"), [payload.get("sprite_action") or "idle"])
        dir_list = _expand_directions(payload.get("default_directions") or payload.get("directions") or payload.get("direction"), [payload.get("direction") or "right"])
        if action == "animate_existing_sprite":
            act_list = _csv_values(payload.get("existing_sprite_actions") or payload.get("default_actions") or payload.get("actions") or payload.get("sprite_action"), ["idle"])
            dir_list = _expand_directions(payload.get("existing_sprite_directions") or payload.get("default_directions") or payload.get("directions") or payload.get("direction"), ["right"])
        num_jobs = max(1, len(act_list) * len(dir_list))
        estimated_gb = 0.2 if action == "animate_existing_sprite" else num_jobs * 0.8
        
    try:
        total, used, free = shutil.disk_usage(ROOT)
        free_gb = free / (1024**3)
    except Exception:
        free_gb = 100.0
    
    if not force and (free_gb - estimated_gb < 5.0):
        return jsonify({
            "ok": False,
            "warning": "low_disk",
            "free_gb": round(free_gb, 2),
            "estimated_gb": round(estimated_gb, 2),
            "message": f"Disk warning: Task requires ~{estimated_gb:.1f} GB. Free space is {free_gb:.1f} GB, which may drop below the 5.0 GB safety threshold."
        })

    try:
        title, cmd = build_action_command(payload)
        metadata = {
            key: payload.get(key)
            for key in [
                "project_name", "project_path", "project_root", "tier", "mode", "profile",
                "sprite_action", "direction", "seed", "preview", "style_image", "source_sprite",
                "existing_sprite_name", "existing_sprite_actions", "existing_sprite_directions",
                "dataset_dir", "model_family", "trainer", "base_model", "trainer_dir",
                "resolution", "max_train_steps", "learning_rate", "network_dim", "repeats",
                "max_samples_per_source", "include_all",
                "pack_mode", "segment_parts", "lora_name", "interpolation_engine"
            ]
            if payload.get(key) is not None
        }
        archetype_provenance = _archetype_generation_provenance(payload)
        if archetype_provenance:
            metadata["archetype"] = archetype_provenance
            metadata["archetype_id"] = archetype_provenance["id"]
            metadata["archetype_name"] = archetype_provenance["name"]
        if action == "generate_sprite":
            metadata["eta"] = estimate_job_eta(metadata)
            metadata["preflight"] = preflight_generation(
                payload,
                models=ModelService.get_summary(),
                gpu=ComfyService.get_gpu_info(),
                disk=ModelService.get_disk_summary(),
                comfy_running=ComfyService.is_running(),
            )
        ok, job_id_or_err = JobService.start_job(title, cmd, metadata=metadata)
        if ok:
            active = JobService.get_job(job_id_or_err)
            return jsonify({"ok": True, "message": "Job started.", "job": active})
        else:
            return jsonify({"ok": False, "message": job_id_or_err, "job": None}), 409
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc), "job": None}), 500

@routes_jobs.route("/api/cancel", methods=["POST"])
def cancel_job():
    active = JobService.get_active_job()
    ok = False
    if active:
        ok = JobService.cancel_job(active["id"])
    return jsonify({"ok": ok})

@routes_jobs.route("/api/job/retry", methods=["POST"])
def retry_job():
    body = request.json or {}
    job_id = str(body.get("id") or "").strip()
    if not job_id:
        return jsonify({"ok": False, "message": "job id required"}), 400
    job = JobService.get_job(job_id)
    if not job:
        return jsonify({"ok": False, "message": "Job not found in history"}), 404
    title = job.get("title") or "Retry Job"
    cmd = job.get("command")
    metadata = job.get("metadata") or {}
    if not cmd:
        return jsonify({"ok": False, "message": "Job command not found"}), 400
    ok, job_id_or_err = JobService.start_job(title, cmd, metadata=metadata)
    if ok:
        active = JobService.get_job(job_id_or_err)
        return jsonify({"ok": True, "message": "Job retried.", "job": active})
    else:
        return jsonify({"ok": False, "message": job_id_or_err, "job": None}), 409

@routes_jobs.route("/api/job/retry_safe", methods=["POST"])
def retry_safe_job():
    body = request.json or {}
    job_id = str(body.get("id") or "").strip()
    job = JobService.get_job(job_id) if job_id else None
    if not job:
        return jsonify({"ok": False, "message": "Job not found in history"}), 404
    logs = "\n".join(job.get("logs") or [])
    original_payload = dict(job.get("metadata") or {})
    original_payload["action"] = "generate_sprite" if any(str(c) in {"generate-sprite", "generate-batch"} for c in job.get("command") or []) else original_payload.get("action", "")
    retry_payload = safer_retry_payload(logs, original_payload)
    if retry_payload.get("action") == "launch_comfy":
        ok = ComfyService.launch()
        return jsonify({"ok": ok, "message": "ComfyUI launch requested.", "payload": retry_payload})
    title, cmd = build_action_command(retry_payload)
    ok, job_id_or_err = JobService.start_job(title, cmd, metadata=retry_payload)
    active = JobService.get_job(job_id_or_err) if ok else None
    return jsonify({"ok": ok, "message": "Safer retry started." if ok else job_id_or_err, "job": active, "payload": retry_payload}), (200 if ok else 409)

@routes_jobs.route("/api/lora/progress", methods=["GET"])
def get_lora_progress():
    run_path = str(request.args.get("path") or "").strip()
    if not run_path:
        return jsonify({"ok": False, "message": "path is required"}), 400
    try:
        return jsonify(summarize_lora_training_progress(run_path, root=ROOT))
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_jobs.route("/api/lora/register-checkpoint", methods=["POST"])
def register_lora_checkpoint():
    body = request.json or {}
    run_path = str(body.get("run_path") or body.get("path") or "").strip()
    checkpoint_path = str(body.get("checkpoint_path") or body.get("checkpoint") or "").strip()
    try:
        if checkpoint_path:
            checkpoint = _resolve_workspace_path(checkpoint_path, "checkpoint_path")
            run_dir = _resolve_workspace_path(run_path, "run_path") if run_path else checkpoint.parent
        else:
            run_dir = _resolve_workspace_path(run_path, "run_path")
            if not run_dir.is_dir():
                return jsonify({"ok": False, "message": f"Run folder not found: {run_path}"}), 404
            checkpoint = _latest_lora_checkpoint(run_dir)
            if not checkpoint:
                return jsonify({"ok": False, "message": "No LoRA checkpoint found in that run yet."}), 409
        if checkpoint.suffix.lower() not in LORA_CHECKPOINT_SUFFIXES:
            return jsonify({"ok": False, "message": "Checkpoint must be .safetensors, .pt, or .ckpt."}), 400
        result = register_external_lora_checkpoint(
            checkpoint_path=checkpoint,
            run_dir=run_dir,
            role=str(body.get("role") or "").strip(),
            label=str(body.get("label") or "").strip(),
            notes=str(body.get("notes") or "").strip(),
            make_default=_truthy(body.get("make_default"), True),
            registry_path=body.get("registry_path") or None,
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 404
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_jobs.route("/api/launch_comfy", methods=["POST"])
def launch_comfy():
    ok = ComfyService.launch()
    return jsonify({"ok": ok, "message": "ComfyUI launch requested." if ok else "Launch failed."})

@routes_jobs.route("/api/queues/reorder", methods=["POST"])
def reorder_queue():
    body = request.json or {}
    qpath_str = str(body.get("path") or "").strip()
    job_id = str(body.get("job_id") or "").strip()
    direction = str(body.get("direction") or "").strip()
    if not qpath_str or not job_id or not direction:
        return jsonify({"ok": False, "message": "path, job_id, and direction are required."}), 400
    try:
        qpath = _resolve_queue_path(qpath_str)
        data = json.loads(qpath.read_text(encoding="utf-8"))
        jobs = data.get("jobs", [])
        
        idx = -1
        for i, j in enumerate(jobs):
            if j.get("id") == job_id:
                idx = i
                break
        if idx == -1:
            return jsonify({"ok": False, "message": f"Job {job_id} not found in queue."}), 404
        
        if direction == "up" and idx > 0:
            jobs[idx], jobs[idx-1] = jobs[idx-1], jobs[idx]
        elif direction == "down" and idx < len(jobs) - 1:
            jobs[idx], jobs[idx+1] = jobs[idx+1], jobs[idx]
        else:
            return jsonify({"ok": False, "message": "Invalid movement direction or boundary reached."}), 400
        
        from spriteforge_utils import save_json
        save_json(qpath, data)
        return jsonify({"ok": True, "queue": data})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_jobs.route("/api/queues/duplicate", methods=["POST"])
def duplicate_queue_job():
    body = request.json or {}
    qpath_str = str(body.get("path") or "").strip()
    job_id = str(body.get("job_id") or "").strip()
    if not qpath_str or not job_id:
        return jsonify({"ok": False, "message": "path and job_id are required."}), 400
    try:
        qpath = _resolve_queue_path(qpath_str)
        data = json.loads(qpath.read_text(encoding="utf-8"))
        jobs = data.get("jobs", [])
        
        target_job = None
        for j in jobs:
            if j.get("id") == job_id:
                target_job = j
                break
        if not target_job:
            return jsonify({"ok": False, "message": f"Job {job_id} not found."}), 404
            
        import copy
        import uuid
        new_job = copy.deepcopy(target_job)
        new_job["id"] = f"job_{uuid.uuid4()}"
        new_job["status"] = "pending"
        new_job["progress"] = 0.0
        new_job["log"] = None
        
        idx = jobs.index(target_job)
        jobs.insert(idx + 1, new_job)
        
        from spriteforge_utils import save_json
        save_json(qpath, data)
        return jsonify({"ok": True, "queue": data})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_jobs.route("/api/queues/delete", methods=["POST"])
def delete_queue_job():
    body = request.json or {}
    qpath_str = str(body.get("path") or "").strip()
    job_id = str(body.get("job_id") or "").strip()
    if not qpath_str or not job_id:
        return jsonify({"ok": False, "message": "path and job_id are required."}), 400
    try:
        qpath = _resolve_queue_path(qpath_str)
        data = json.loads(qpath.read_text(encoding="utf-8"))
        jobs = data.get("jobs", [])
        
        target_job = None
        for j in jobs:
            if j.get("id") == job_id:
                target_job = j
                break
        if not target_job:
            return jsonify({"ok": False, "message": f"Job {job_id} not found."}), 404
            
        jobs.remove(target_job)
        from spriteforge_utils import save_json
        save_json(qpath, data)
        return jsonify({"ok": True, "queue": data})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_jobs.route("/api/queues/cancel_queue", methods=["POST"])
def cancel_queue():
    body = request.json or {}
    qpath_str = str(body.get("path") or "").strip()
    if not qpath_str:
        return jsonify({"ok": False, "message": "path is required."}), 400
    try:
        qpath = _resolve_queue_path(qpath_str)
        data = json.loads(qpath.read_text(encoding="utf-8"))
        for j in data.get("jobs", []):
            if j.get("status") in {"pending", "running"}:
                j["status"] = "cancelled"
        from spriteforge_utils import save_json
        save_json(qpath, data)
        
        # Also cancel current running active job
        active = JobService.get_active_job()
        if active:
            JobService.cancel_job(active["id"])
            
        return jsonify({"ok": True, "queue": data})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_jobs.route("/api/job/clean_completed", methods=["POST"])
def clean_completed_jobs():
    JobService.clean_completed()
    return jsonify({"ok": True, "history": JobService.get_history()})
