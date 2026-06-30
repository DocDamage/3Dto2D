from flask import Blueprint, request, jsonify
import json
from pathlib import Path

from services.sprite_service import SpriteService
from services.frame_status_service import update_frame_status
from services.palette_harmonizer_service import harmonize_palette
from services.audio_cue_service import load_audio_cues, remove_audio_cue, upsert_audio_cue
from web_helpers import (
    ROOT, _resolve_sprite_output_dir, _project_meta_from_query,
    _project_workspace, sprite_outputs, sprite_preview_bundle,
    _sprite_version_list, _sprite_version_save, _sprite_version_rollback,
    _sprite_edit_frames, _qa_batch_summary
)
from spriteforge_utils import save_json

routes_sprites = Blueprint("routes_sprites", __name__)

@routes_sprites.route("/api/outputs", methods=["GET"])
def get_outputs():
    project_meta = _project_meta_from_query(request.args.to_dict(flat=False))
    return jsonify({
        "outputs": sprite_outputs(80, project_meta),
        "project_workspace": _project_workspace(project_meta)
    })

@routes_sprites.route("/api/sprite/preview", methods=["GET"])
def get_sprite_preview():
    sprite_path = request.args.get("path", "")
    if not sprite_path:
        return jsonify({"error": "Missing sprite path"}), 400
    try:
        return jsonify(sprite_preview_bundle(sprite_path))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 404

@routes_sprites.route("/api/sprite/version/list", methods=["GET"])
def get_sprite_versions():
    sprite_path = request.args.get("path", "")
    if not sprite_path:
        return jsonify({"error": "Missing sprite path"}), 400
    try:
        return jsonify(_sprite_version_list(sprite_path))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@routes_sprites.route("/api/sprite/version/save", methods=["POST"])
def save_sprite_version():
    body = request.json or {}
    sprite_path = body.get("path")
    label = body.get("label")
    if not sprite_path:
        return jsonify({"ok": False, "message": "path is required"}), 400
    try:
        res = _sprite_version_save(sprite_path, label)
        return jsonify(res)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_sprites.route("/api/sprite/version/rollback", methods=["POST"])
def rollback_sprite_version():
    body = request.json or {}
    sprite_path = body.get("path")
    version_id = body.get("version_id")
    if not sprite_path or not version_id:
        return jsonify({"ok": False, "message": "path and version_id are required"}), 400
    try:
        res = _sprite_version_rollback(sprite_path, version_id)
        return jsonify(res)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_sprites.route("/api/sprite/save_metadata", methods=["POST"])
def save_sprite_metadata():
    body = request.json or {}
    sprite_path = str(body.get("path") or "").strip()
    meta_data = body.get("metadata")
    if not sprite_path or meta_data is None:
        return jsonify({"ok": False, "message": "path and metadata are required."}), 400
    try:
        sprite_dir = _resolve_sprite_output_dir(sprite_path)
        sheet_json_path = sprite_dir / "sheet.json"
        save_json(sheet_json_path, meta_data)
        return jsonify({"ok": True, "message": "Metadata saved successfully."})
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 403
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_sprites.route("/api/sprite/edit_frames", methods=["POST"])
def edit_sprite_frames():
    body = request.json or {}
    sprite_path = body.get("path")
    actions = body.get("actions", [])
    new_fps = body.get("fps")
    if not sprite_path:
        return jsonify({"ok": False, "message": "path is required"}), 400
    try:
        res = _sprite_edit_frames(sprite_path, actions, new_fps)
        return jsonify(res)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_sprites.route("/api/sprite/frame/status", methods=["POST"])
def set_sprite_frame_status():
    body = request.json or {}
    sprite_path = str(body.get("path") or "").strip()
    status = str(body.get("status") or "").strip()
    note = str(body.get("note") or "").strip()
    try:
        frame_index = int(body.get("frame_index"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "frame_index is required."}), 400
    if not sprite_path or not status:
        return jsonify({"ok": False, "message": "path and status are required."}), 400
    try:
        sprite_dir = _resolve_sprite_output_dir(sprite_path)
        summary = update_frame_status(sprite_dir, frame_index, status, note)
        return jsonify({"ok": True, "summary": summary})
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 404
    except (IndexError, ValueError) as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_sprites.route("/api/sprites/palette_harmonize", methods=["POST"])
def harmonize_sprite_palettes():
    body = request.json or {}
    sprites = body.get("sprites") or []
    if isinstance(sprites, str):
        sprites = [line.strip() for line in sprites.splitlines() if line.strip()]
    if len(sprites) < 2:
        return jsonify({"ok": False, "message": "At least two sprite folders are required."}), 400
    try:
        colors = int(body.get("colors") or 32)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "colors must be a number."}), 400
    write_images = bool(body.get("write_images", True))
    try:
        sprite_dirs = [_resolve_sprite_output_dir(str(path)) for path in sprites]
        report = harmonize_palette(sprite_dirs, colors=colors, write_images=write_images, root=ROOT)
        return jsonify(report)
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_sprites.route("/api/sprite/audio_cue", methods=["GET", "POST", "DELETE"])
def sprite_audio_cue():
    body = request.get_json(silent=True) or {}
    sprite_path = str(body.get("path") or request.args.get("path") or "").strip()
    if not sprite_path:
        return jsonify({"ok": False, "message": "path is required."}), 400
    try:
        sprite_dir = _resolve_sprite_output_dir(sprite_path)
        if request.method == "GET":
            return jsonify({"ok": True, "audio_cues": load_audio_cues(sprite_dir)})
        try:
            frame_index = int(body.get("frame_index"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "message": "frame_index is required."}), 400
        if request.method == "DELETE":
            return jsonify({"ok": True, "audio_cues": remove_audio_cue(sprite_dir, frame_index)})
        audio_path = str(body.get("audio_path") or "").strip()
        if not audio_path:
            return jsonify({"ok": False, "message": "audio_path is required."}), 400
        manifest = upsert_audio_cue(sprite_dir, frame_index, audio_path, str(body.get("label") or ""))
        return jsonify({"ok": True, "audio_cues": manifest})
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_sprites.route("/api/qa/batch_summary", methods=["GET"])
def get_qa_batch_summary():
    project_meta = _project_meta_from_query(request.args.to_dict(flat=False))
    return jsonify(_qa_batch_summary(project_meta))

@routes_sprites.route("/api/sprite/validate_engine", methods=["GET"])
def validate_engine_export():
    sprite_path = request.args.get("path", "")
    engine = request.args.get("engine", None)
    if not sprite_path:
        return jsonify({"error": "Missing sprite path"}), 400
    try:
        sprite_dir = _resolve_sprite_output_dir(sprite_path)
        from spriteforge_engine_export import validate_export
        res = validate_export(sprite_dir, engine=engine, return_dict=True)
        return jsonify(res)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@routes_sprites.route("/api/release/precheck", methods=["POST"])
def release_precheck():
    body = request.json or {}
    sprites = body.get("sprites") or []
    if isinstance(sprites, str):
        sprites = [s.strip() for s in sprites.splitlines() if s.strip()]
    if not sprites:
        return jsonify({"ok": True, "errors": [], "warnings": ["No sprites selected for precheck."]})
    resolved_paths = []
    for s in sprites:
        try:
            resolved_paths.append(_resolve_sprite_output_dir(s))
        except Exception as exc:
            return jsonify({"ok": False, "errors": [f"Invalid sprite folder '{s}': {exc}"], "warnings": []})
            
    from spriteforge_final import check_release_quality_gates
    gate = check_release_quality_gates(resolved_paths)
    return jsonify(gate)

@routes_sprites.route("/api/sprite/frame/save", methods=["POST"])
def save_edited_frame():
    body = request.json or {}
    sprite_path = body.get("path")
    frame_name = body.get("frame_name")
    image_data = body.get("image_data")
    
    if not sprite_path or not frame_name or not image_data:
        return jsonify({"ok": False, "message": "path, frame_name, and image_data are required."}), 400
        
    try:
        sprite_dir = _resolve_sprite_output_dir(sprite_path)
        
        if "," in image_data:
            header, base64_str = image_data.split(",", 1)
        else:
            base64_str = image_data
            
        import base64
        img_bytes = base64.b64decode(base64_str)
        
        dest_folder = sprite_dir / "frames_processed"
        if not dest_folder.exists():
            dest_folder = sprite_dir / "frames"
        dest_folder.mkdir(parents=True, exist_ok=True)
        
        dest_file = dest_folder / frame_name
        dest_file.write_bytes(img_bytes)
        
        sheet_json_path = sprite_dir / "sheet.json"
        meta = load_json(sheet_json_path, {})
        
        import sys
        cmd = [
            sys.executable, "spriteforge.py", "pack",
            "--input", str(dest_folder),
            "--output", str(sprite_dir),
            "--fps", str(meta.get("fps", 12.0)),
            "--cell-size", f"{meta.get('frame_width', 256)}x{meta.get('frame_height', 256)}",
            "--animation", str(meta.get("animation", "anim")),
            "--anchor", str(meta.get("anchor", "bottom-center")),
            "--solidify", "0",
            "--preview-gif",
            "--report"
        ]
        
        from services.job_service import JobService
        ok, job_id_or_err = JobService.start_job(f"Repack painted frame: {sprite_dir.name}", cmd)
        
        return jsonify({
            "ok": True,
            "message": "Frame saved successfully. Repack job started.",
            "job_id": job_id_or_err if ok else None
        })
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500
