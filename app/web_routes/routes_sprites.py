from flask import Blueprint, request, jsonify
import json
from pathlib import Path

from services.sprite_service import SpriteService
from services.frame_status_service import sanitize_frame_filename, update_frame_status
from services.frame_repack_service import repack_sprite_sheet
from services.animated_export_service import export_animation
from services.lighting_preview_service import export_lighting_preview_gif
from services.qa_advisor_service import advise_sprite_quality, record_advisor_feedback
from services.palette_harmonizer_service import harmonize_palette
from services.audio_cue_service import load_audio_cues, remove_audio_cue, upsert_audio_cue
from services.rate_limit_service import route_rate_limited
from services.skeletal_export_service import export_skeletal_parts
from web_helpers import (
    ROOT, _resolve_sprite_output_dir, _project_meta_from_query,
    _project_workspace, sprite_outputs, sprite_preview_bundle,
    _sprite_version_list, _sprite_version_save, _sprite_version_rollback,
    _sprite_edit_frames, _qa_batch_summary
)
from spriteforge_utils import save_json, load_json

routes_sprites = Blueprint("routes_sprites", __name__)


def _resolve_workspace_output_dir(value: str) -> Path:
    raw = str(value or "").replace("\\", "/").strip()
    if not raw:
        raise ValueError("output must be a relative workspace path.")
    output_path = Path(raw)
    if output_path.is_absolute() or output_path.drive:
        raise ValueError("output must be a relative workspace path.")
    resolved = (ROOT / raw.strip("/")).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("output must stay inside the SpriteForge workspace.") from exc
    return resolved


@routes_sprites.route("/api/outputs", methods=["GET"])
def get_outputs():
    project_meta = _project_meta_from_query(request.args.to_dict(flat=False))
    outputs = sprite_outputs(80, project_meta)
    return jsonify({
        "outputs": outputs,
        "project_workspace": {
            "active": project_meta,
            "outputs": len(outputs),
        },
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
@route_rate_limited("sprite_version_save", limit=20, window_seconds=60)
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
@route_rate_limited("sprite_version_rollback", limit=10, window_seconds=60)
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
@route_rate_limited("sprite_save_metadata", limit=30, window_seconds=60)
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
@route_rate_limited("sprite_edit_frames", limit=20, window_seconds=60)
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

@routes_sprites.route("/api/repack-sheet", methods=["POST"])
@route_rate_limited("sprite_repack_sheet", limit=20, window_seconds=60)
def repack_sheet():
    body = request.json or {}
    sprite_path = str(body.get("path") or "").strip()
    if not sprite_path:
        return jsonify({"ok": False, "message": "path is required"}), 400
    try:
        sprite_dir = _resolve_sprite_output_dir(sprite_path)
        result = repack_sprite_sheet(sprite_dir, body)
        result["path"] = sprite_path
        return jsonify(result)
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_sprites.route("/api/sprite/export_animation", methods=["POST"])
def export_sprite_animation():
    body = request.json or {}
    sprite_path = str(body.get("path") or "").strip()
    fmt = str(body.get("format") or "lottie").strip().lower()
    if not sprite_path:
        return jsonify({"ok": False, "message": "path is required"}), 400
    try:
        quality = int(body.get("quality") or 85)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "quality must be a number"}), 400
    try:
        sprite_dir = _resolve_sprite_output_dir(sprite_path)
        result = export_animation(sprite_dir, fmt, quality=quality)
        result["path"] = str(Path(result["path"]).relative_to(ROOT))
        return jsonify(result)
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_sprites.route("/api/sprite/export_lighting_preview", methods=["POST"])
def export_sprite_lighting_preview():
    body = request.json or {}
    sprite_path = str(body.get("path") or "").strip()
    if not sprite_path:
        return jsonify({"ok": False, "message": "path is required"}), 400
    try:
        sprite_dir = _resolve_sprite_output_dir(sprite_path)
        result = export_lighting_preview_gif(
            sprite_dir,
            light_x=body.get("light_x", 0.35),
            light_y=body.get("light_y", -0.45),
            intensity=body.get("intensity", 1.15),
            ambient=body.get("ambient", 0.35),
        )
        for key in ["path", "manifest_path"]:
            result[key] = str(Path(result[key]).resolve().relative_to(ROOT.resolve())).replace("\\", "/")
        return jsonify(result)
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_sprites.route("/api/sprite/export_skeletal", methods=["POST"])
def export_sprite_skeletal():
    body = request.json or {}
    sprite_path = str(body.get("path") or "").strip()
    if not sprite_path:
        return jsonify({"ok": False, "message": "path is required"}), 400
    try:
        sprite_dir = _resolve_sprite_output_dir(sprite_path)
        output = body.get("output")
        output_dir = None
        if output:
            output_dir = _resolve_workspace_output_dir(str(output))
        result = export_skeletal_parts(sprite_dir, output_dir=output_dir, name=str(body.get("name") or ""))
        for key in ["spine_json", "dragonbones_json", "skeletal_manifest"]:
            result[key] = str(Path(result[key]).resolve().relative_to(ROOT.resolve())).replace("\\", "/")
        return jsonify(result)
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_sprites.route("/api/sprite/frame/status", methods=["POST"])
@route_rate_limited("sprite_frame_status", limit=60, window_seconds=60)
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
@route_rate_limited("sprite_palette_harmonize", limit=10, window_seconds=60)
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
@route_rate_limited("sprite_audio_cue_write", limit=40, window_seconds=60)
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

@routes_sprites.route("/api/qa/advisor", methods=["GET"])
def get_qa_advisor():
    sprite_path = request.args.get("path", "")
    if not sprite_path:
        return jsonify({"ok": False, "message": "path is required"}), 400
    try:
        sprite_dir = _resolve_sprite_output_dir(sprite_path)
        return jsonify(advise_sprite_quality(sprite_dir))
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_sprites.route("/api/qa/advisor/feedback", methods=["POST"])
def post_qa_advisor_feedback():
    body = request.json or {}
    sprite_path = str(body.get("path") or "").strip()
    if not sprite_path:
        return jsonify({"ok": False, "message": "path is required"}), 400
    try:
        sprite_dir = _resolve_sprite_output_dir(sprite_path)
        return jsonify(record_advisor_feedback(
            sprite_dir,
            str(body.get("code") or ""),
            str(body.get("decision") or ""),
            str(body.get("note") or ""),
        ))
    except FileNotFoundError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

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
@route_rate_limited("sprite_frame_save", limit=30, window_seconds=60)
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
        
        safe_frame_name = sanitize_frame_filename(frame_name)
        dest_file = dest_folder / safe_frame_name
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
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500
