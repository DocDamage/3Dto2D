from flask import Blueprint, request, jsonify
import json
import time
import shutil
import datetime as dt
from pathlib import Path

from services.config_service import ConfigService
from services.comfy_service import ComfyService
from services.model_service import ModelService
from services.experiment_service import ExperimentService
from services.seed_gallery_service import build_seed_gallery
from services.marketplace_service import marketplace_gallery
from services.project_service import ProjectService
from services.advisor_service import advise as advisor_advise
from services.generation_intelligence import (
    cleanup_suggestions, explain_model_profile, preflight_generation,
    mark_review_decision, rerun_similar_payload
)
from web_helpers import (
    ROOT, UPLOADS, OUTPUT, LOGS, ALLOWED_SUBDIRS, VIDEO_SUFFIXES, IMAGE_SUFFIXES,
    _project_meta_from_query, _project_workspace, _experiment_rows,
    _comfy_output_root, next_step_status, sprite_outputs,
    _ab_run_list, _ab_run_create, open_local_path, rel, _is_relative_to,
    _resolve_sprite_output_dir
)

routes_misc = Blueprint("routes_misc", __name__)

@routes_misc.route("/api/status", methods=["GET"])
def get_status():
    project_meta = _project_meta_from_query(request.args.to_dict(flat=False))
    
    from services.job_service import JobService
    active_job = JobService.get_active_job()
    if active_job:
        job_status = dict(active_job)
        job_status["running"] = True
    else:
        history = JobService.get_history()
        if history:
            job_status = dict(history[0])
            job_status["running"] = False
        else:
            job_status = {"running": False, "title": "Idle", "progress": 0.0, "exit_code": None, "logs": [], "started_at": None, "finished_at": None}
            
    from spriteforge_utils import PYTHON
    return jsonify({
        "version": "v12 Final Polish",
        "root": str(ROOT),
        "python": PYTHON,
        "comfy_url": ComfyService.get_url(),
        "comfy_running": ComfyService.is_running(),
        "gpu": ComfyService.get_gpu_info(),
        "models": ModelService.get_summary(),
        "disk": ModelService.get_disk_summary(),
        "cleanup_suggestions": cleanup_suggestions(ROOT)[:8],
        "next_step": next_step_status(),
        "outputs": sprite_outputs(24, project_meta),
        "project_workspace": _project_workspace(project_meta),
        "job": job_status,
        "time": time.strftime("%H:%M:%S")
    })

@routes_misc.route("/api/config", methods=["GET"])
def get_config():
    return jsonify(ConfigService.get_config())

@routes_misc.route("/api/cleanup/scan", methods=["GET"])
def scan_cleanup():
    files = []
    comfy_out = _comfy_output_root()
    if comfy_out.exists():
        for f in comfy_out.rglob("*"):
            if f.is_file() and f.suffix.lower() in {".mp4", ".webm", ".png", ".jpg", ".webp", ".gif"}:
                files.append({
                    "path": rel(f),
                    "size": f.stat().st_size,
                    "mtime": f.stat().st_mtime,
                    "category": "ComfyUI Render Outputs",
                    "id": str(f.relative_to(ROOT)).replace("\\", "/")
                })
    if UPLOADS.exists():
        for f in UPLOADS.rglob("*"):
            if f.is_file() and f.suffix.lower() in VIDEO_SUFFIXES | IMAGE_SUFFIXES:
                files.append({
                    "path": rel(f),
                    "size": f.stat().st_size,
                    "mtime": f.stat().st_mtime,
                    "category": "Uploaded Reference Videos",
                    "id": str(f.relative_to(ROOT)).replace("\\", "/")
                })
    if OUTPUT.exists():
        for folder in OUTPUT.iterdir():
            if folder.is_dir() and folder.name not in {"jobs", "packs", "sprite_compare", "temp"}:
                if not (folder / "sheet.json").exists():
                    total_size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
                    files.append({
                        "path": rel(folder),
                        "size": total_size,
                        "mtime": folder.stat().st_mtime,
                        "category": "Failed / Incomplete Outputs",
                        "id": str(folder.relative_to(ROOT)).replace("\\", "/")
                    })
    if LOGS.exists():
        for f in LOGS.glob("*.log"):
            if f.name != "web_server.log" and f.is_file():
                files.append({
                    "path": rel(f),
                    "size": f.stat().st_size,
                    "mtime": f.stat().st_mtime,
                    "category": "Old Task Logs",
                    "id": str(f.relative_to(ROOT)).replace("\\", "/")
                })
    return jsonify({"files": files})

@routes_misc.route("/api/advisor", methods=["GET"])
def get_advisor():
    quality = request.args.get("quality", "balanced")
    try:
        return jsonify(advisor_advise(quality))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@routes_misc.route("/api/model/explain", methods=["GET"])
def get_model_explanation():
    tier = request.args.get("tier", "")
    profile = request.args.get("profile", "")
    return jsonify(explain_model_profile(tier, profile))

@routes_misc.route("/api/preflight/generation", methods=["GET"])
def get_preflight_generation():
    payload = {k: v[0] for k, v in request.args.to_dict(flat=False).items() if v}
    return jsonify(preflight_generation(
        payload,
        models=ModelService.get_summary(),
        gpu=ComfyService.get_gpu_info(),
        disk=ModelService.get_disk_summary(),
        comfy_running=ComfyService.is_running(),
    ))

@routes_misc.route("/api/experiments", methods=["GET"])
def get_experiments():
    project_meta = _project_meta_from_query(request.args.to_dict(flat=False))
    return jsonify({
        "experiments": _experiment_rows(project_meta),
        "project_workspace": _project_workspace(project_meta)
    })

@routes_misc.route("/api/seeds/gallery", methods=["GET"])
def get_seed_gallery():
    project_meta = _project_meta_from_query(request.args.to_dict(flat=False))
    try:
        limit = int(request.args.get("limit", "24"))
    except ValueError:
        limit = 24
    return jsonify({
        "seeds": build_seed_gallery(_experiment_rows(project_meta), root=ROOT, rel_path=rel, limit=limit),
        "project_workspace": _project_workspace(project_meta),
    })

@routes_misc.route("/api/marketplace/gallery", methods=["GET"])
def get_marketplace_gallery():
    return jsonify({"ok": True, **marketplace_gallery(ROOT)})

@routes_misc.route("/api/experiments/export", methods=["GET"])
def get_experiments_export():
    project_meta = _project_meta_from_query(request.args.to_dict(flat=False))
    data = ExperimentService.export_history(_experiment_rows(project_meta))
    payload = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Return response with download headers
    from flask import make_response
    response = make_response(payload)
    response.headers["Content-Disposition"] = f"attachment; filename=spriteforge_experiment_history_{stamp}.json"
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

@routes_misc.route("/api/planning", methods=["GET"])
def get_planning_assets():
    project_meta = _project_meta_from_query(request.args.to_dict(flat=False))
    from web_helpers import _list_planning_assets
    return jsonify({**_list_planning_assets(project_meta), "project_workspace": _project_workspace(project_meta)})

@routes_misc.route("/api/cleanup/purge", methods=["POST"])
def purge_cleanup_files():
    body = request.json or {}
    file_ids = body.get("ids") or []
    if not isinstance(file_ids, list) or not file_ids:
        return jsonify({"ok": False, "message": "ids list required"}), 400
    count = 0
    reclaimed_bytes = 0
    for fid in file_ids:
        fid_str = str(fid).strip()
        if not fid_str:
            continue
        path_target = (ROOT / fid_str).resolve()
        if not _is_relative_to(path_target, ROOT):
            continue
        comfy_out = _comfy_output_root()
        is_safe = (
            _is_relative_to(path_target, OUTPUT) or
            _is_relative_to(path_target, LOGS) or
            _is_relative_to(path_target, UPLOADS) or
            (comfy_out.exists() and _is_relative_to(path_target, comfy_out))
        )
        if not is_safe:
            continue
        if path_target.exists():
            try:
                if path_target.is_file():
                    sz = path_target.stat().st_size
                    path_target.unlink()
                    reclaimed_bytes += sz
                    count += 1
                elif path_target.is_dir():
                    sz = sum(f.stat().st_size for f in path_target.rglob("*") if f.is_file())
                    shutil.rmtree(path_target)
                    reclaimed_bytes += sz
                    count += 1
            except Exception:
                pass
    reclaimed_mb = round(reclaimed_bytes / (1024 * 1024), 2)
    return jsonify({"ok": True, "count": count, "reclaimed_mb": reclaimed_mb})

@routes_misc.route("/api/experiments/review", methods=["POST"])
def review_experiment():
    body = request.json or {}
    run_id = str(body.get("id") or "").strip()
    decision = str(body.get("decision") or "").strip()
    if not run_id or decision not in {"star", "reject", "reviewed"}:
        return jsonify({"ok": False, "message": "id and decision are required"}), 400
    rec = mark_review_decision(run_id, decision)
    return jsonify({"ok": True, "experiment": rec})

@routes_misc.route("/api/experiments/note", methods=["POST"])
def note_experiment():
    body = request.json or {}
    run_id = str(body.get("id") or "")
    notes = str(body.get("notes") or "")
    found = ExperimentService.update_note(run_id, notes)
    return jsonify({"ok": found})

@routes_misc.route("/api/experiments/star", methods=["POST"])
def star_experiment():
    body = request.json or {}
    run_id = str(body.get("id") or "")
    starred = bool(body.get("starred"))
    found = ExperimentService.set_starred(run_id, starred)
    return jsonify({"ok": found})

@routes_misc.route("/api/experiments/clear", methods=["POST"])
def clear_experiments():
    body = request.json or {}
    keep_starred = bool(body.get("keep_starred", True))
    project_meta = (
        ProjectService.metadata_for_path(str(body.get("active_project") or ""))
        or _project_meta_from_query(request.args.to_dict(flat=False))
    )
    predicate = (lambda rec: ProjectService.item_matches_project(rec, project_meta)) if project_meta else None
    removed = ExperimentService.clear_history(keep_starred=keep_starred, predicate=predicate)
    return jsonify({"ok": True, "removed": removed})

@routes_misc.route("/api/experiments/rerun_similar", methods=["POST"])
def rerun_similar():
    body = request.json or {}
    run_id = str(body.get("id") or "").strip()
    rec = ExperimentService.get_run(run_id)
    if not rec:
        return jsonify({"ok": False, "message": "Experiment not found"}), 404
    payload = rerun_similar_payload(rec)
    title, cmd = build_action_command(payload)
    from services.job_service import JobService
    ok, job_id_or_err = JobService.start_job(title, cmd, metadata=payload)
    active = JobService.get_job(job_id_or_err) if ok else None
    return jsonify({"ok": ok, "message": "Similar run started." if ok else job_id_or_err, "job": active, "payload": payload}), (200 if ok else 409)

@routes_misc.route("/api/ab_run/create", methods=["POST"])
def ab_run_create():
    body = request.json or {}
    force = bool(body.get("force", False))
    estimated_gb = 2.0
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
            "message": f"Disk warning: A/B Run requires ~2.0 GB. Free space is {free_gb:.1f} GB, which may drop below the 5.0 GB safety threshold."
        })
    res = _ab_run_create(body)
    return jsonify(res)

@routes_misc.route("/api/ab_run/list", methods=["GET"])
def ab_run_list():
    return jsonify({"ab_runs": _ab_run_list()})

@routes_misc.route("/api/compare", methods=["POST"])
def compare_sprites():
    body = request.json or {}
    a_str = str(body.get("a") or "").strip()
    body_b = str(body.get("b") or "").strip()
    if not a_str or not body_b:
        return jsonify({"ok": False, "message": "Both 'a' and 'b' paths required."}), 400
    out_dir = OUTPUT / "sprite_compare"
    try:
        a_path = _resolve_sprite_output_dir(a_str)
        b_path = _resolve_sprite_output_dir(body_b)
        from spriteforge_compare import compare_dirs
        compare_dirs(a_path, b_path, out_dir)
        report_rel = rel(out_dir / "compare_report.html")
        return jsonify({"ok": True, "report_url": "/file/" + report_rel})
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 403
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_misc.route("/api/open", methods=["POST"])
def open_folder():
    target = str(request.json.get("path") or "output")
    p = Path(target).resolve() if Path(target).is_absolute() else (ROOT / target).resolve()
    if not str(p).startswith(str(ROOT.resolve())):
        return jsonify({"ok": False, "message": "Access denied: Path is outside workspace root."}), 403
    try:
        rel_parts = p.relative_to(ROOT).parts
        if not rel_parts or rel_parts[0] not in ALLOWED_SUBDIRS:
            return jsonify({"ok": False, "message": "Access denied: Opening system folders is restricted."}), 403
    except ValueError:
        return jsonify({"ok": False, "message": "Access denied."}), 403
    if p.exists():
        open_local_path(p)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Path does not exist."}), 404
