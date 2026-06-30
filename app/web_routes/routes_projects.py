from flask import Blueprint, request, jsonify
import time
import json
from pathlib import Path

from services.project_service import ProjectService
from services.consistency_lock_service import build_consistency_lock
from services.prompt_builder_service import build_structured_prompt, prompt_builder_options
from services.scene_compositor_service import build_scene_manifest
from services.state_machine_service import build_state_machine
from web_helpers import (
    ROOT, UPLOADS, VIDEO_SUFFIXES, IMAGE_SUFFIXES, AUDIO_SUFFIXES,
    _get_presets, _library_list, _library_save, _library_delete,
    _project_artifact_path, rel, safe_name
)
from spriteforge_utils import load_json, save_json

routes_projects = Blueprint("routes_projects", __name__)

@routes_projects.route("/api/projects", methods=["GET"])
def get_projects():
    return jsonify({
        "projects": ProjectService.list_projects(),
        "active": ProjectService.get_active_project()
    })

@routes_projects.route("/api/projects/create", methods=["POST"])
def create_project():
    body = request.json or {}
    name = str(body.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "message": "Project name required."}), 400
    project = ProjectService.create_project(
        name=name,
        character=str(body.get("character") or "single full body original game character, professional appealing character design, heroic adult proportions, distinctive outfit, readable silhouette"),
        style=str(body.get("style") or "high quality 2D game sprite animation, polished concept-art quality, crisp cel-shaded edges, clean linework, readable silhouette"),
    )
    return jsonify({"ok": True, "project": project})

@routes_projects.route("/api/projects/active", methods=["POST"])
def set_active_project():
    body = request.json or {}
    requested = str(body.get("path") or "")
    if not requested:
        ProjectService.clear_active_project()
        return jsonify({"ok": True, "project": None})
    project = ProjectService.set_active_project(requested)
    if not project:
        return jsonify({"ok": False, "message": "Project not found."}), 404
    return jsonify({"ok": True, "project": project})

@routes_projects.route("/api/presets", methods=["GET"])
def get_presets():
    return jsonify({"presets": _get_presets()})

@routes_projects.route("/api/prompt_builder/options", methods=["GET"])
def get_prompt_builder_options():
    return jsonify(prompt_builder_options())

@routes_projects.route("/api/prompt_builder/build", methods=["POST"])
def build_prompt_from_fields():
    body = request.json or {}
    try:
        return jsonify({"ok": True, "prompt": build_structured_prompt(body)})
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

@routes_projects.route("/api/consistency_lock/save", methods=["POST"])
def save_consistency_lock():
    body = request.json or {}
    name = safe_name(str(body.get("name") or "character_lock"))
    active_project = str(body.get("active_project") or "")
    project_meta = ProjectService.metadata_for_path(active_project) if active_project else None
    output_dir = (
        _project_artifact_path(project_meta, "references", name)
        if project_meta
        else ROOT / "output" / "consistency_locks" / name
    )
    try:
        return jsonify(build_consistency_lock(ROOT, body, output_dir))
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_projects.route("/api/presets/save", methods=["POST"])
def save_preset():
    body = request.json or {}
    name = str(body.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "message": "Preset name required."}), 400
    user_presets_path = ROOT / "config" / "user_presets.json"
    user_presets_path.parent.mkdir(parents=True, exist_ok=True)
    user_presets = load_json(user_presets_path, {})
    preset_fields = {}
    for field in [
        "character", "style", "tier", "profile", "fps", "cell_size",
        "default_actions", "default_directions", "negative",
        "qa_threshold_loop_rmse", "qa_threshold_foot_drift", "qa_threshold_center_drift"
    ]:
        preset_fields[field] = str(body.get(field) or "").strip()
    user_presets[name] = preset_fields
    save_json(user_presets_path, user_presets)
    return jsonify({"ok": True, "presets": _get_presets()})

@routes_projects.route("/api/presets/delete", methods=["POST"])
def delete_preset():
    body = request.json or {}
    name = str(body.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "message": "Preset name required."}), 400
    user_presets_path = ROOT / "config" / "user_presets.json"
    user_presets = load_json(user_presets_path, {})
    if name in user_presets:
        del user_presets[name]
        save_json(user_presets_path, user_presets)
        return jsonify({"ok": True, "presets": _get_presets()})
    return jsonify({"ok": False, "message": f"Preset '{name}' is a default preset or not found."}), 400

@routes_projects.route("/api/project/config", methods=["GET"])
def get_project_config():
    active = ProjectService.get_active_project()
    if not active:
        return jsonify({"error": "No active project"}), 400
    p_path = ROOT / active["path"]
    if not p_path.exists():
        return jsonify({"error": "Project file not found"}), 404
    try:
        data = json.loads(p_path.read_text(encoding="utf-8"))
        if "quality_gates" not in data:
            data["quality_gates"] = {
                "max_foot_drift": 2.0,
                "max_flicker": 1.0,
                "loop_seam_threshold": 15.0,
                "required_frame_count": None,
                "alpha_cleanliness": 0.05
            }
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@routes_projects.route("/api/project/config", methods=["POST"])
def save_project_config():
    active = ProjectService.get_active_project()
    if not active:
        return jsonify({"error": "No active project"}), 400
    p_path = ROOT / active["path"]
    if not p_path.exists():
        return jsonify({"error": "Project file not found"}), 404
    
    body = request.json or {}
    try:
        data = json.loads(p_path.read_text(encoding="utf-8"))
        for key in ["character", "style", "actions", "directions", "fps", "cell_size", "frames_by_action", "quality_gates"]:
            if key in body:
                data[key] = body[key]
        data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        save_json(p_path, data)
        return jsonify({"ok": True, "config": data})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_projects.route("/api/library/list", methods=["GET"])
def get_library_list():
    project_name = request.args.get("project_name", "")
    if not project_name:
        active = ProjectService.get_active_project()
        project_name = active["name"] if active else ""
    return jsonify({"library": _library_list(project_name)})

@routes_projects.route("/api/library/save", methods=["POST"])
def save_library_asset():
    body = request.json or {}
    project_name = body.get("project_name")
    if not project_name:
        active = ProjectService.get_active_project()
        project_name = active["name"] if active else ""
    if not project_name:
        return jsonify({"ok": False, "message": "No project context"}), 400
    res = _library_save(project_name, body)
    return jsonify(res)

@routes_projects.route("/api/library/delete", methods=["POST"])
def delete_library_asset():
    body = request.json or {}
    project_name = body.get("project_name")
    asset_id = body.get("id")
    if not project_name:
        active = ProjectService.get_active_project()
        project_name = active["name"] if active else ""
    if not project_name or not asset_id:
        return jsonify({"ok": False, "message": "project_name and id are required"}), 400
    res = _library_delete(project_name, asset_id)
    return jsonify(res)

@routes_projects.route("/api/state_machine/build", methods=["POST"])
def build_state_machine_route():
    body = request.json or {}
    name = safe_name(str(body.get("name") or "sprite_state_machine"))
    active_project = str(body.get("active_project") or "")
    project_meta = ProjectService.metadata_for_path(active_project) if active_project else None
    output_dir = _project_artifact_path(project_meta, "exports", name) if project_meta else ROOT / "output" / "state_machines" / name
    try:
        result = build_state_machine(body, output_dir)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_projects.route("/api/scene_compositor/preview", methods=["POST"])
def build_scene_compositor_preview():
    body = request.json or {}
    try:
        return jsonify(build_scene_manifest(ROOT, body))
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_projects.route("/api/upload", methods=["POST"])
def upload_file():
    # Check upload size limit (100MB)
    content_length = request.content_length
    if content_length and content_length > 100 * 1024 * 1024:
        return jsonify({"ok": False, "message": "Upload size exceeds 100MB limit"}), 413

    if 'file' not in request.files:

        return jsonify({"ok": False, "message": "No file payload found in multipart data."}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"ok": False, "message": "No file selected."}), 400
        
    active_project = request.form.get("active_project", "")
    filename = safe_name(Path(file.filename).name)
    suffix = Path(filename).suffix.lower()
    if suffix not in VIDEO_SUFFIXES and suffix not in IMAGE_SUFFIXES and suffix not in AUDIO_SUFFIXES:
        return jsonify({"ok": False, "message": "Unsupported file type."}), 400
        
    project_meta = ProjectService.metadata_for_path(active_project) if active_project else None
    upload_dir = _project_artifact_path(project_meta, "references", "upload").parent if project_meta else UPLOADS
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / filename
    if dest.exists():
        dest = upload_dir / f"{dest.stem}_{int(time.time())}{dest.suffix}"
        
    file.save(dest)
    return jsonify({"ok": True, "path": str(dest), "relative": rel(dest), "name": dest.name})

@routes_projects.route("/api/projects/export_bundle", methods=["GET"])
def export_project_bundle():
    project_path = request.args.get("path", "")
    if not project_path:
        active = ProjectService.get_active_project()
        if active:
            project_path = active["path"]
    if not project_path:
        return jsonify({"ok": False, "message": "No active project to export."}), 400
        
    try:
        from services.project_service import PROJECTS_DIR
        p_path = ROOT / project_path
        if p_path.is_file():
            p_dir = p_path.parent
        else:
            p_dir = p_path
            
        if not p_dir.exists() or p_dir == PROJECTS_DIR:
            return jsonify({"ok": False, "message": "Invalid project directory."}), 400
            
        releases_dir = ROOT / "output" / "releases"
        releases_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = releases_dir / f"{p_dir.name}.spriteforge"
        
        import zipfile
        with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in p_dir.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, file_path.relative_to(p_dir))
                    
        from flask import send_from_directory
        return send_from_directory(releases_dir, f"{p_dir.name}.spriteforge", as_attachment=True)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_projects.route("/api/projects/import_bundle", methods=["POST"])
def import_project_bundle():
    if 'file' not in request.files:
        return jsonify({"ok": False, "message": "No file payload found."}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"ok": False, "message": "No file selected."}), 400
        
    filename = file.filename
    if not (filename.endswith(".spriteforge") or filename.endswith(".zip")):
        return jsonify({"ok": False, "message": "Must be a .spriteforge or .zip bundle."}), 400
        
    try:
        from services.project_service import PROJECTS_DIR
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        
        import tempfile
        import zipfile
        temp_dir = Path(tempfile.gettempdir())
        temp_zip = temp_dir / f"import_{int(time.time())}.zip"
        file.save(temp_zip)
        
        with zipfile.ZipFile(temp_zip, "r") as zf:
            names = zf.namelist()
            if "spriteforge_project.json" not in names:
                return jsonify({"ok": False, "message": "Invalid bundle: missing spriteforge_project.json."}), 400
            
            manifest_bytes = zf.read("spriteforge_project.json")
            manifest_data = json.loads(manifest_bytes.decode("utf-8"))
            project_name = safe_name(manifest_data.get("name") or Path(filename).stem)
            
            dest_dir = PROJECTS_DIR / project_name
            dest_dir.mkdir(parents=True, exist_ok=True)
            zf.extractall(dest_dir)
            
        try:
            temp_zip.unlink()
        except Exception:
            pass
            
        manifest_path = dest_dir / "spriteforge_project.json"
        rel_path = manifest_path.relative_to(ROOT).as_posix()
        ProjectService.set_active_project(rel_path)
        
        return jsonify({"ok": True, "message": f"Successfully imported project '{project_name}'.", "project_path": rel_path})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_projects.route("/api/pose/estimate", methods=["POST"])
def run_pose_estimation():
    body = request.json or {}
    video_path = str(body.get("video_path") or "").strip()
    action_name = str(body.get("action_name") or "walk").strip()
    
    active = ProjectService.get_active_project()
    if not active:
        return jsonify({"ok": False, "message": "No active project found."}), 400
        
    project_dir = str(Path(active["path"]).parent).replace("\\", "/")
    
    if not video_path:
        return jsonify({"ok": False, "message": "video_path is required."}), 400
        
    from services.pose_estimation_service import PoseEstimationService
    res = PoseEstimationService.estimate_pose(video_path, project_dir, action_name)
    return jsonify(res)

@routes_projects.route("/api/tilemap/generate", methods=["POST"])
def generate_tilemap_autotile():
    body = request.json or {}
    base_path = str(body.get("base_path") or "").strip()
    border_path = str(body.get("border_path") or "").strip()
    output_path = str(body.get("output_path") or "output/tilesets/autotile_16.png").strip()
    
    if not base_path or not border_path:
        return jsonify({"ok": False, "message": "base_path and border_path are required."}), 400
        
    from services.tilemap_service import TilemapService
    res = TilemapService.generate_16_autotiles(base_path, border_path, output_path)
    return jsonify(res)
