from flask import Blueprint, request, jsonify, Response, stream_with_context
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
from services.marketplace_service import marketplace_gallery, import_marketplace_bundle, build_marketplace_share_manifest
from services.plugin_manager import PluginManager, PLUGIN_SDK_VERSION, KNOWN_HOOKS, plugin_sdk_contract, plugin_scaffold
from services.trained_lora_registry_service import plan_lora_comparison
from services.lora_training_service import recommend_lora_training_defaults
from services.database_service import DatabaseService
from services.websocket_service import ProgressEventHub, progress_transport_status
from services.project_service import ProjectService
from services.cloud_hub_service import cloud_hub_status, upsert_cloud_node, remove_cloud_node, load_cloud_nodes, plan_cloud_queue_assignments
from services.cloud_image_generation_service import (
    cloud_image_provider_status, build_cloud_generation_plan,
    save_provider_api_key, delete_provider_api_key,
)
from services.training_dataset_service import preview_training_dataset
from services.lpc_parts_service import (
    scan_lpc_parts, build_lpc_part_dataset, compose_lpc_character,
    lpc_catalog_options, compose_lpc_batch, qa_lpc_dataset, lpc_lora_prefill,
    lpc_rules_report, lpc_palette_options, list_lpc_presets, save_lpc_preset,
    delete_lpc_preset, preview_lpc_dataset, bake_lpc_editor_layers,
)
from services.architecture_status_service import architecture_status
from services.advisor_service import advise as advisor_advise
from services.generation_intelligence import (
    cleanup_suggestions, explain_model_profile, preflight_generation,
    mark_review_decision, restore_review_decision, rerun_similar_payload,
    estimate_job_eta
)
from services.prompt_linter_service import lint_prompt, lint_from_payload, quick_score, autofix_from_payload
from services.api_auth_service import get_session_token
from services.project_path_service import ProjectPaths
from services.feature_capability_service import capability_report
from web_helpers import (
    ROOT, UPLOADS, OUTPUT, LOGS, PYTHON, ALLOWED_SUBDIRS, VIDEO_SUFFIXES, IMAGE_SUFFIXES,
    _project_meta_from_query, _project_workspace, _experiment_rows,
    _comfy_output_root, next_step_status, sprite_outputs,
    _ab_run_list, _ab_run_create, open_local_path, rel, _is_relative_to,
    _resolve_sprite_output_dir, build_action_command
)
from web_routes.api_errors import api_exception_response

routes_misc = Blueprint("routes_misc", __name__)


def _misc_route_error(exc: Exception, *, status: int = 500):
    return api_exception_response(exc, default_status=status, context="misc-routes")

@routes_misc.route("/api/auth/token", methods=["GET"])
def get_auth_token():
    return jsonify({"ok": True, "token": get_session_token()})

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

    if job_status.get("exit_code") is not None and job_status.get("exit_code") != 0:
        logs_text = "\n".join(job_status.get("logs", []))
        from services.failure_explainer_service import explain_failure
        job_status["failure_explanation"] = explain_failure(logs_text)

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
        "feature_capabilities": capability_report(),
        "architecture": architecture_status(),
        "next_step": next_step_status(),
        "outputs": sprite_outputs(24, project_meta),
        "project_workspace": _project_workspace(project_meta),
        "job": job_status,
        "time": time.strftime("%H:%M:%S")
    })

@routes_misc.route("/api/heartbeat", methods=["GET"])
def get_heartbeat():
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

    return jsonify({
        "ok": True,
        "comfy_url": ComfyService.get_url(),
        "comfy_running": ComfyService.is_running(),
        "job": job_status,
        "time": time.strftime("%H:%M:%S"),
    })

@routes_misc.route("/api/features/capabilities", methods=["GET"])
def get_feature_capabilities():
    return jsonify({"ok": True, **capability_report()})

@routes_misc.route("/api/plugins/sdk", methods=["GET"])
def get_plugin_sdk():
    plugin_id = str(request.args.get("id") or "my_plugin")
    return jsonify({"ok": True, "contract": plugin_sdk_contract(), "scaffold": plugin_scaffold(plugin_id)})

@routes_misc.route("/api/training-dataset/preview", methods=["POST"])
def post_training_dataset_preview():
    body = request.json or {}
    source_dir = str(body.get("source_dir") or "").strip()
    if not source_dir:
        return jsonify({"ok": False, "message": "source_dir is required"}), 400
    try:
        return jsonify(preview_training_dataset(
            source_dir,
            trigger=str(body.get("trigger") or "sakpix_style"),
            base_caption=str(body.get("base_caption") or "premium pixel art RPG character"),
            cell_size=str(body.get("cell_size") or "").strip() or None,
        ))
    except FileNotFoundError as exc:
        return _misc_route_error(exc)
    except ValueError as exc:
        return _misc_route_error(exc, status=400)
    except Exception as exc:
        return _misc_route_error(exc)

@routes_misc.route("/api/lpc/parts/scan", methods=["POST"])
def post_lpc_parts_scan():
    body = request.json or {}
    source_dir = str(body.get("source_dir") or "").strip()
    if not source_dir:
        return jsonify({"ok": False, "message": "source_dir is required"}), 400
    try:
        return jsonify(scan_lpc_parts(
            source_dir,
            output_dir=str(body.get("output") or "").strip() or None,
            thumbnail_limit=int(body.get("thumbnail_limit") or 24),
            max_files=int(body.get("max_files") or 0),
        ))
    except FileNotFoundError as exc:
        return _misc_route_error(exc)
    except ValueError as exc:
        return _misc_route_error(exc, status=400)
    except Exception as exc:
        return _misc_route_error(exc)

@routes_misc.route("/api/lpc/parts/dataset", methods=["POST"])
def post_lpc_part_dataset():
    body = request.json or {}
    source_dir = str(body.get("source_dir") or "").strip()
    if not source_dir:
        return jsonify({"ok": False, "message": "source_dir is required"}), 400
    try:
        return jsonify(build_lpc_part_dataset(
            source_dir,
            output_dir=str(body.get("output") or "").strip() or None,
            trigger=str(body.get("trigger") or "lpc_parts"),
            max_samples=int(body.get("max_samples") or 0),
        ))
    except FileNotFoundError as exc:
        return _misc_route_error(exc)
    except ValueError as exc:
        return _misc_route_error(exc, status=400)
    except Exception as exc:
        return _misc_route_error(exc)

@routes_misc.route("/api/lpc/compose", methods=["POST"])
def post_lpc_compose():
    body = request.json or {}
    source_dir = str(body.get("source_dir") or "").strip()
    if not source_dir:
        return jsonify({"ok": False, "message": "source_dir is required"}), 400
    selections = body.get("selections")
    if not isinstance(selections, (dict, list)):
        selections = str(body.get("parts") or "").strip()
    try:
        return jsonify(compose_lpc_character(
            source_dir,
            output_dir=str(body.get("compose_output") or body.get("output_dir") or "").strip() or None,
            action=str(body.get("compose_action") or body.get("action") or "idle"),
            body_type=str(body.get("body_type") or "male"),
            selections=selections,
            name=str(body.get("compose_name") or body.get("name") or ""),
            include_body=str(body.get("include_body", body.get("show_body", True))).lower() not in {"0", "false", "no"},
            palette=str(body.get("palette") or "default"),
            preview_direction=str(body.get("preview_direction") or "front"),
        ))
    except FileNotFoundError as exc:
        return _misc_route_error(exc)
    except ValueError as exc:
        return _misc_route_error(exc, status=400)
    except Exception as exc:
        return _misc_route_error(exc)

@routes_misc.route("/api/lpc/options", methods=["POST"])
def post_lpc_options():
    body = request.json or {}
    source_dir = str(body.get("source_dir") or "").strip()
    if not source_dir:
        return jsonify({"ok": False, "message": "source_dir is required"}), 400
    categories = body.get("categories")
    if isinstance(categories, str):
        categories = [part.strip() for part in categories.split(",") if part.strip()]
    try:
        return jsonify(lpc_catalog_options(
            source_dir,
            categories=list(categories) if isinstance(categories, list) else None,
            limit_per_category=int(body.get("limit_per_category") or 240),
            action=str(body.get("action") or body.get("compose_action") or "idle"),
            body_type=str(body.get("body_type") or "male"),
        ))
    except FileNotFoundError as exc:
        return _misc_route_error(exc)
    except ValueError as exc:
        return _misc_route_error(exc, status=400)
    except Exception as exc:
        return _misc_route_error(exc)

@routes_misc.route("/api/lpc/bake-edits", methods=["POST"])
def post_lpc_bake_edits():
    body = request.json or {}
    try:
        sheet_value = str(body.get("sheet") or body.get("sheet_path") or "").strip()
        sheet_path = ProjectPaths.resolve_root_path(sheet_value)
        if not ProjectPaths.is_relative_to(sheet_path, Path(ROOT)):
            raise ValueError("LPC editor sheet must stay inside the SpriteForge workspace.")
        output_value = str(body.get("output_dir") or "").strip()
        output_path = ProjectPaths.resolve_root_path(output_value) if output_value else None
        if output_path is not None and not ProjectPaths.is_relative_to(output_path, Path(ROOT)):
            raise ValueError("LPC editor output must stay inside the SpriteForge workspace.")
        return jsonify(bake_lpc_editor_layers(
            str(sheet_path),
            body.get("layers") if isinstance(body.get("layers"), list) else [],
            output_dir=output_path,
            name=str(body.get("name") or "lpc_edited"),
            preview_direction=str(body.get("preview_direction") or "front"),
        ))
    except FileNotFoundError as exc:
        return _misc_route_error(exc)
    except ValueError as exc:
        return _misc_route_error(exc, status=400)
    except Exception as exc:
        return _misc_route_error(exc)

@routes_misc.route("/api/lpc/palettes", methods=["GET"])
def get_lpc_palettes():
    return jsonify(lpc_palette_options())

@routes_misc.route("/api/lpc/rules", methods=["POST"])
def post_lpc_rules():
    body = request.json or {}
    source_dir = str(body.get("source_dir") or "").strip()
    if not source_dir:
        return jsonify({"ok": False, "message": "source_dir is required"}), 400
    include_body = str(body.get("include_body", body.get("show_body", True))).lower() not in {"0", "false", "no"}
    try:
        return jsonify(lpc_rules_report(
            source_dir,
            action=str(body.get("compose_action") or body.get("action") or "idle"),
            body_type=str(body.get("body_type") or "male"),
            selections=body.get("selections") if isinstance(body.get("selections"), (dict, list)) else str(body.get("parts") or ""),
            include_body=include_body,
        ))
    except FileNotFoundError as exc:
        return _misc_route_error(exc)
    except ValueError as exc:
        return _misc_route_error(exc, status=400)
    except Exception as exc:
        return _misc_route_error(exc)

@routes_misc.route("/api/lpc/presets", methods=["GET"])
def get_lpc_presets():
    return jsonify(list_lpc_presets())

@routes_misc.route("/api/lpc/presets", methods=["POST"])
def post_lpc_preset():
    body = request.json or {}
    try:
        return jsonify(save_lpc_preset(body))
    except ValueError as exc:
        return _misc_route_error(exc, status=400)
    except Exception as exc:
        return _misc_route_error(exc)

@routes_misc.route("/api/lpc/presets/delete", methods=["POST"])
def post_lpc_preset_delete():
    body = request.json or {}
    try:
        return jsonify(delete_lpc_preset(str(body.get("id") or body.get("name") or "")))
    except ValueError as exc:
        return _misc_route_error(exc, status=400)
    except Exception as exc:
        return _misc_route_error(exc)

@routes_misc.route("/api/lpc/batch-compose", methods=["POST"])
def post_lpc_batch_compose():
    body = request.json or {}
    source_dir = str(body.get("source_dir") or "").strip()
    if not source_dir:
        return jsonify({"ok": False, "message": "source_dir is required"}), 400
    categories = body.get("batch_categories") or body.get("categories")
    if isinstance(categories, str):
        categories = [part.strip() for part in categories.split(",") if part.strip()]
    try:
        return jsonify(compose_lpc_batch(
            source_dir,
            output_dir=str(body.get("batch_output") or body.get("output_dir") or "").strip() or None,
            count=int(body.get("batch_count") or body.get("count") or 24),
            action=str(body.get("batch_action") or body.get("compose_action") or body.get("action") or "idle"),
            body_type=str(body.get("body_type") or "male"),
            actions=[part.strip() for part in str(body.get("batch_actions") or "").split(",") if part.strip()] or None,
            body_types=[part.strip() for part in str(body.get("batch_body_types") or "").split(",") if part.strip()] or None,
            categories=list(categories) if isinstance(categories, list) else None,
            seed=int(body.get("batch_seed")) if str(body.get("batch_seed") or "").strip() else None,
            trigger=str(body.get("trigger") or "lpc_composed"),
            palette=str(body.get("palette") or "default"),
        ))
    except FileNotFoundError as exc:
        return _misc_route_error(exc)
    except ValueError as exc:
        return _misc_route_error(exc, status=400)
    except Exception as exc:
        return _misc_route_error(exc)

@routes_misc.route("/api/lpc/dataset-preview", methods=["POST"])
def post_lpc_dataset_preview():
    body = request.json or {}
    dataset_dir = str(body.get("dataset_dir") or body.get("batch_output") or body.get("output_dir") or "").strip()
    if not dataset_dir:
        return jsonify({"ok": False, "message": "dataset_dir is required"}), 400
    try:
        return jsonify(preview_lpc_dataset(dataset_dir, limit=int(body.get("limit") or 12)))
    except FileNotFoundError as exc:
        return _misc_route_error(exc)
    except ValueError as exc:
        return _misc_route_error(exc, status=400)
    except Exception as exc:
        return _misc_route_error(exc)

@routes_misc.route("/api/lpc/dataset-qa", methods=["POST"])
def post_lpc_dataset_qa():
    body = request.json or {}
    dataset_dir = str(body.get("dataset_dir") or body.get("batch_output") or body.get("output_dir") or "").strip()
    if not dataset_dir:
        return jsonify({"ok": False, "message": "dataset_dir is required"}), 400
    try:
        return jsonify(qa_lpc_dataset(
            dataset_dir,
            min_layers=int(body.get("min_layers") or 3),
            max_balance_delta=int(body.get("max_balance_delta") or 2),
        ))
    except FileNotFoundError as exc:
        return _misc_route_error(exc)
    except ValueError as exc:
        return _misc_route_error(exc, status=400)
    except Exception as exc:
        return _misc_route_error(exc)

@routes_misc.route("/api/lpc/lora-prefill", methods=["POST"])
def post_lpc_lora_prefill():
    body = request.json or {}
    dataset_dir = str(body.get("dataset_dir") or body.get("batch_output") or body.get("output_dir") or "").strip()
    if not dataset_dir:
        return jsonify({"ok": False, "message": "dataset_dir is required"}), 400
    try:
        return jsonify(lpc_lora_prefill(dataset_dir))
    except FileNotFoundError as exc:
        return _misc_route_error(exc)
    except ValueError as exc:
        return _misc_route_error(exc, status=400)
    except Exception as exc:
        return _misc_route_error(exc)

@routes_misc.route("/api/architecture/status", methods=["GET"])
def get_architecture_status():
    return jsonify(architecture_status())

@routes_misc.route("/api/cloud/nodes", methods=["GET"])
def get_cloud_nodes():
    check = str(request.args.get("check") or "").lower() in {"1", "true", "yes"}
    prefer_id = str(request.args.get("prefer") or "")
    return jsonify(cloud_hub_status(check=check, prefer_id=prefer_id))

@routes_misc.route("/api/cloud/nodes", methods=["POST"])
def save_cloud_node():
    body = request.json or {}
    if not str(body.get("url") or body.get("server") or "").strip():
        return jsonify({"ok": False, "message": "Cloud node URL is required."}), 400
    node = upsert_cloud_node(body)
    return jsonify({"ok": True, "node": node, **cloud_hub_status(prefer_id=node["id"])})

@routes_misc.route("/api/cloud/nodes/<node_id>", methods=["DELETE"])
def delete_cloud_node(node_id):
    removed = remove_cloud_node(node_id)
    status = cloud_hub_status()
    return jsonify({"ok": removed, "removed": removed, **status}), (200 if removed else 404)

@routes_misc.route("/api/cloud/image-providers", methods=["GET"])
def get_cloud_image_providers():
    provider = str(request.args.get("provider") or "").strip() or None
    return jsonify(cloud_image_provider_status(provider))

@routes_misc.route("/api/cloud/image-provider-key", methods=["POST", "DELETE"])
def update_cloud_image_provider_key():
    body = request.json or {}
    provider = str(body.get("provider") or "").strip()
    try:
        if request.method == "DELETE":
            result = delete_provider_api_key(provider)
            return jsonify({"ok": True, **result, **cloud_image_provider_status()})
        api_key = str(body.get("api_key") or "").strip()
        result = save_provider_api_key(provider, api_key)
        return jsonify({"ok": True, **result, **cloud_image_provider_status()})
    except (ValueError, RuntimeError) as exc:
        return _misc_route_error(exc, status=400)

@routes_misc.route("/api/cloud/image-generation-plan", methods=["POST"])
def get_cloud_image_generation_plan():
    body = request.json or {}
    try:
        return jsonify(build_cloud_generation_plan(
            prompt=str(body.get("prompt") or ""),
            provider=str(body.get("provider") or "openai"),
            model=str(body.get("model") or "").strip() or None,
            size=str(body.get("size") or "1024x1024"),
            cell_size=str(body.get("cell_size") or "64x64"),
            frame_count=int(body.get("frames") or body.get("frame_count") or 1),
            frame_prompts=body.get("frame_prompts") if isinstance(body.get("frame_prompts"), list) else [],
            source_images=body.get("source_images") if isinstance(body.get("source_images"), list) else [],
            key_color=str(body.get("key_color") or "#ff00ff"),
            palette_colors=None if body.get("no_palette_cleanup") else int(body.get("palette_colors") or 24),
            constraints=str(body.get("constraints") or ""),
            negative=str(body.get("negative") or ""),
        ))
    except (ValueError, RuntimeError) as exc:
        return _misc_route_error(exc, status=400)

@routes_misc.route("/api/cloud/queue-plan", methods=["POST"])
def get_cloud_queue_plan():
    body = request.json or {}
    jobs = body.get("jobs") if isinstance(body.get("jobs"), list) else []
    capability = str(body.get("capability") or "remote_generate")
    prefer_id = str(body.get("prefer") or body.get("prefer_id") or "")
    return jsonify(plan_cloud_queue_assignments(jobs, load_cloud_nodes(), capability=capability, prefer_id=prefer_id))

@routes_misc.route("/api/lora/compare-plan", methods=["POST"])
def get_lora_compare_plan():
    body = request.json or {}
    prompt = str(body.get("prompt") or "").strip()
    loras = body.get("loras") or body.get("lora_names") or []
    if isinstance(loras, str):
        loras = [part.strip() for part in loras.split(",") if part.strip()]
    try:
        return jsonify(plan_lora_comparison(prompt, list(loras), base_payload=body.get("base_payload") if isinstance(body.get("base_payload"), dict) else {}))
    except ValueError as exc:
        return _misc_route_error(exc, status=400)

@routes_misc.route("/api/lora/recommended-defaults", methods=["GET"])
def get_lora_recommended_defaults():
    family = str(request.args.get("model_family") or "sdxl")
    vram = request.args.get("vram_gb")
    if vram is None:
        try:
            gpu = ComfyService.get_gpu_info()
            vram = gpu.get("vram_gb") if isinstance(gpu, dict) else None
        except Exception:
            vram = None
    return jsonify(recommend_lora_training_defaults(vram, model_family=family))

@routes_misc.route("/api/config", methods=["GET"])
def get_config():
    return jsonify(ConfigService.get_config())

@routes_misc.route("/api/config/effective-profile", methods=["GET"])
def get_effective_config_profile():
    profile = str(request.args.get("profile") or "auto").strip()
    return jsonify({"ok": True, **ConfigService.explain_effective_profile(profile)})

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

@routes_misc.route("/api/prompt/lint", methods=["POST"])
def lint_prompt_endpoint():
    body = request.json or {}
    prompt = str(body.get("prompt") or "").strip()
    negative = str(body.get("negative") or "").strip()
    action = str(body.get("action") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "message": "prompt is required"}), 400
    try:
        full = body.get("full_payload")
        if full and isinstance(full, dict):
            result = lint_from_payload(full)
        else:
            result = lint_prompt(prompt, negative=negative, action=action)
        result["ok"] = True
        return jsonify(result)
    except Exception as exc:
        return _misc_route_error(exc)

@routes_misc.route("/api/prompt/autofix", methods=["GET", "POST"])
def autofix_prompt_endpoint():
    if request.method == "GET":
        return jsonify({
            "ok": False,
            "message": "Prompt auto-fix must be triggered from the Generate form."
        }), 400
    body = request.json or {}
    if not isinstance(body, dict):
        return jsonify({"ok": False, "message": "JSON object is required"}), 400
    try:
        result = autofix_from_payload(body)
        result["ok"] = True
        return jsonify(result)
    except Exception as exc:
        return _misc_route_error(exc)

@routes_misc.route("/api/archetypes", methods=["GET"])
def get_archetypes():
    from spriteforge_utils import load_json
    archetypes_path = ROOT / "config" / "character_archetypes.json"
    data = load_json(archetypes_path, {"archetypes": [], "meta": {}})
    tag = request.args.get("tag", "")
    search = request.args.get("search", "")
    archetypes = data.get("archetypes", [])
    if tag:
        archetypes = [a for a in archetypes if tag in a.get("tags", [])]
    if search:
        sl = search.lower()
        archetypes = [a for a in archetypes if sl in a.get("name", "").lower() or sl in a.get("description", "").lower() or any(sl in t.lower() for t in a.get("tags", []))]
    return jsonify({"ok": True, "archetypes": archetypes, "meta": data.get("meta", {}), "total": len(archetypes)})

@routes_misc.route("/api/advisor", methods=["GET"])
def get_advisor():
    quality = request.args.get("quality", "balanced")
    try:
        return jsonify(advisor_advise(quality))
    except Exception as exc:
        return _misc_route_error(exc)

@routes_misc.route("/api/model/explain", methods=["GET"])
def get_model_explanation():
    tier = request.args.get("tier", "")
    profile = request.args.get("profile", "")
    return jsonify(explain_model_profile(tier, profile))

@routes_misc.route("/api/model/addons", methods=["GET"])
def get_model_addons():
    return jsonify(ModelService.get_addons_status())

@routes_misc.route("/api/model/addons/install", methods=["POST"])
def install_model_addon():
    body = request.json or {}
    addon_id = str(body.get("id") or "").strip()
    if not addon_id:
        return jsonify({"ok": False, "message": "add-on id required"}), 400

    addons = ModelService.get_addons_status().get("addons", [])
    addon = next((row for row in addons if row.get("id") == addon_id), None)
    if not addon:
        return jsonify({"ok": False, "message": f"Unknown model add-on: {addon_id}"}), 404
    if addon.get("installed") and not body.get("force"):
        return jsonify({"ok": True, "message": "Add-on is already installed.", "job": None})

    from services.job_service import JobService
    cmd = [PYTHON, "spriteforge_unified.py", "download-model-addon", "--addon", addon_id]
    if body.get("force"):
        cmd.append("--force")
    title = f"Install model add-on: {addon.get('label') or addon_id}"
    ok, job_id_or_err = JobService.start_job(title, cmd, metadata={
        "addon_id": addon_id,
        "addon_label": addon.get("label") or addon_id,
        "repo_id": addon.get("repo_id") or "",
    })
    if ok:
        return jsonify({"ok": True, "message": "Add-on install started.", "job": JobService.get_job(job_id_or_err)})
    return jsonify({"ok": False, "message": job_id_or_err, "job": None}), 409

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

@routes_misc.route("/api/generation/estimate", methods=["GET"])
def get_generation_estimate():
    payload = {k: v[0] for k, v in request.args.to_dict(flat=False).items() if v}
    eta = estimate_job_eta(payload)
    return jsonify({"ok": True, "eta": eta})

@routes_misc.route("/api/experiments", methods=["GET"])
def get_experiments():
    project_meta = _project_meta_from_query(request.args.to_dict(flat=False))
    return jsonify({
        "experiments": _experiment_rows(project_meta),
        "project_workspace": _project_workspace(project_meta)
    })

@routes_misc.route("/api/experiments/analytics", methods=["GET"])
def get_experiments_analytics():
    query = request.args.to_dict(flat=False)
    project_meta = _project_meta_from_query(query) if "project" in query else None
    analytics = ExperimentService.analytics(_experiment_rows(project_meta))
    analytics["project_workspace"] = _project_workspace(project_meta)
    return jsonify(analytics)

@routes_misc.route("/api/experiments/prompts", methods=["GET"])
def get_experiment_prompts():
    query = request.args.to_dict(flat=False)
    project_meta = _project_meta_from_query(query) if "project" in query else None
    try:
        limit = int(request.args.get("limit") or 40)
    except ValueError:
        limit = 40
    data = ExperimentService.search_prompts(
        request.args.get("q") or "",
        records=_experiment_rows(project_meta),
        limit=limit,
        starred_only=str(request.args.get("starred") or "").lower() in {"1", "true", "yes"},
    )
    data["project_workspace"] = _project_workspace(project_meta)
    return jsonify(data)

@routes_misc.route("/api/experiments/winning-prompts", methods=["GET"])
def get_experiment_winning_prompts():
    query = request.args.to_dict(flat=False)
    project_meta = _project_meta_from_query(query) if "project" in query else None
    try:
        limit = int(request.args.get("limit") or 24)
    except ValueError:
        limit = 24
    pack = ExperimentService.winning_prompt_pack(_experiment_rows(project_meta), limit=limit)
    pack["project_workspace"] = _project_workspace(project_meta)
    return jsonify({"ok": True, **pack})

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

@routes_misc.route("/api/marketplace/import", methods=["POST"])
def post_marketplace_import():
    body = request.json or {}
    entry = body.get("entry") if isinstance(body.get("entry"), dict) else body
    return jsonify(import_marketplace_bundle(ROOT, entry))

@routes_misc.route("/api/marketplace/share-manifest", methods=["POST"])
def post_marketplace_share_manifest():
    body = request.json or {}
    bundle_paths = body.get("bundle_paths") if isinstance(body.get("bundle_paths"), list) else []
    return jsonify({
        "ok": True,
        **build_marketplace_share_manifest(
            ROOT,
            bundle_paths=[str(path) for path in bundle_paths],
            author=str(body.get("author") or "Local workspace"),
            license_name=str(body.get("license") or ""),
        ),
    })

@routes_misc.route("/api/plugins", methods=["GET"])
def get_plugins():
    return jsonify({
        "ok": True,
        "sdk_version": PLUGIN_SDK_VERSION,
        "known_hooks": sorted(KNOWN_HOOKS),
        "plugins": PluginManager.discover_plugins(),
    })

@routes_misc.route("/api/database/migrate", methods=["POST"])
def migrate_database_records():
    return jsonify(DatabaseService().migrate_default_json())

@routes_misc.route("/api/database/search", methods=["GET"])
def search_database_records():
    query = str(request.args.get("q") or "").strip()
    kind = str(request.args.get("kind") or "").strip()
    try:
        limit = max(1, min(200, int(request.args.get("limit") or 50)))
    except ValueError:
        limit = 50
    rows = DatabaseService().search(query, kind=kind, limit=limit)
    return jsonify({"ok": True, "kind": kind, "query": query, "count": len(rows), "records": rows})

@routes_misc.route("/api/database/recent", methods=["GET"])
def recent_database_records():
    kind = str(request.args.get("kind") or "experiment").strip() or "experiment"
    try:
        limit = max(1, min(200, int(request.args.get("limit") or 50)))
    except ValueError:
        limit = 50
    rows = DatabaseService().recent(kind, limit=limit)
    return jsonify({"ok": True, "kind": kind, "count": len(rows), "records": rows})

@routes_misc.route("/api/database/stats", methods=["GET"])
def get_database_stats():
    project_name = str(request.args.get("project_name") or request.args.get("project") or "").strip()
    counts = DatabaseService().counts_by_kind(project_name=project_name)
    return jsonify({"ok": True, "project_name": project_name, "counts": counts, "total": sum(counts.values())})

@routes_misc.route("/api/database/health", methods=["GET"])
def get_database_health():
    return jsonify(DatabaseService().health())

@routes_misc.route("/api/progress/events", methods=["GET"])
def get_progress_events():
    try:
        after = int(request.args.get("after") or 0)
    except ValueError:
        after = 0
    try:
        limit = int(request.args.get("limit") or 50)
    except ValueError:
        limit = 50
    events = ProgressEventHub.recent(after=after, limit=limit)
    return jsonify({"ok": True, "events": events, "latest_seq": events[-1]["seq"] if events else after})

@routes_misc.route("/api/progress/transport", methods=["GET"])
def get_progress_transport():
    return jsonify({"ok": True, **progress_transport_status()})

@routes_misc.route("/api/progress/stream", methods=["GET"])
def stream_progress_events():
    def generate():
        subscriber = ProgressEventHub.subscribe()
        try:
            for event in ProgressEventHub.recent(limit=25):
                yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
            last_heartbeat = time.time()
            while True:
                try:
                    event = subscriber.get(timeout=10)
                    yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
                    last_heartbeat = time.time()
                except Exception:
                    now = time.time()
                    if now - last_heartbeat >= 10:
                        yield ": heartbeat\n\n"
                        last_heartbeat = now
        finally:
            ProgressEventHub.unsubscribe(subscriber)

    return Response(stream_with_context(generate()), mimetype="text/event-stream")

@routes_misc.route("/api/selftest", methods=["GET"])
def get_self_test():
    from services.startup_self_test_service import run_self_test
    return jsonify(run_self_test())

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
            except Exception as exc:
                import logging
                logging.getLogger("routes_misc").warning("Cleanup failed to remove path: %s. Error: %s", path_target, exc, exc_info=True)
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


@routes_misc.route("/api/experiments/restore", methods=["POST"])
def restore_experiment_review():
    body = request.json or {}
    run_id = str(body.get("id") or "").strip()
    if not run_id:
        return jsonify({"ok": False, "message": "id is required"}), 400
    try:
        rec = restore_review_decision(run_id)
    except KeyError:
        return jsonify({"ok": False, "message": "Experiment not found"}), 404
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

@routes_misc.route("/api/experiments/pick-winner", methods=["POST"])
def pick_experiment_winner():
    body = request.json or {}
    compared = body.get("compared_sprites") if isinstance(body.get("compared_sprites"), list) else []
    return jsonify(ExperimentService.pick_winner(
        run_id=str(body.get("id") or body.get("experiment_id") or ""),
        sprite_folder=str(body.get("sprite_folder") or body.get("path") or ""),
        compared_sprites=[str(path) for path in compared],
        note=str(body.get("note") or ""),
    ))

@routes_misc.route("/api/experiments/clear", methods=["POST"])
def clear_experiments():
    body = request.get_json(silent=True) or {}
    keep_starred = bool(body.get("keep_starred", True))
    query = request.args.to_dict(flat=False)
    explicit_project_scope = bool(body.get("active_project") or query.get("project"))
    project_meta = (
        ProjectService.metadata_for_path(str(body.get("active_project") or ""))
        or _project_meta_from_query(query)
    )
    if explicit_project_scope and not project_meta:
        return jsonify({"ok": False, "message": "Project scope could not be resolved"}), 400
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
    except Exception as exc:
        import logging
        logging.getLogger("routes_misc").debug("Disk usage check failed in ab_run_create: %s", exc, exc_info=True)
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
        return _misc_route_error(exc)
    except ValueError as exc:
        return _misc_route_error(exc, status=403)
    except Exception as exc:
        return _misc_route_error(exc)

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
