from flask import Blueprint, request, jsonify, send_file
import json
from pathlib import Path
from PIL import Image
from services.project_path_service import ProjectPaths
from services.pixel_asset_service import PixelAssetService, ASSETS_DIR
from services.pixel_normalization_service import PixelNormalizationService
from services.pixel_direction_service import PixelDirectionService
from services.pixel_export_service import PixelExportService
from services.pixel_tileset_service import PixelTilesetService
from services.pixel_recipe_service import PixelRecipeService
from services.pixel_style_service import PixelStyleService
from services.pixel_asset_memory_service import PixelAssetMemoryService
from services.failure_explainer_service import explain_pixel_failure
from spriteforge_utils import load_json, ROOT, save_json
from web_routes.api_errors import ApiError, api_exception_response

routes_pixel_asset = Blueprint("routes_pixel_asset", __name__)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _pixel_route_error(exc: Exception, *, status: int = 500):
    return api_exception_response(exc, default_status=status, context="pixel-assets")


def _resolve_workspace_image_path(value: str) -> Path:
    if not value:
        raise ApiError("path is required")
    candidate = Path(value.strip().lstrip("/\\"))
    path = candidate.resolve() if candidate.is_absolute() else (ROOT / candidate).resolve()
    if not ProjectPaths.is_relative_to(path, ROOT):
        raise ApiError("Security error: Path must stay inside workspace", 403, code="path_escape")
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        raise ApiError("Unsupported image type", 400, code="unsupported_image")
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File not found: {value}")
    return path

@routes_pixel_asset.route("/api/pixel-assets/modes", methods=["GET"])
def get_pixel_modes():
    try:
        modes = PixelAssetService.get_modes()
        return jsonify({"ok": True, "modes": modes, "mode_configs": PixelAssetService.get_mode_configs()})
    except Exception as exc:
        return _pixel_route_error(exc)

@routes_pixel_asset.route("/api/pixel-assets/failure/explain", methods=["POST"])
def explain_pixel_asset_failure():
    body = request.json or {}
    message = str(body.get("message") or body.get("error") or "")
    return jsonify({"ok": True, "explainer": explain_pixel_failure(message)})

@routes_pixel_asset.route("/api/pixel-assets/qa/report", methods=["POST"])
def pixel_asset_qa_report():
    body = request.json or {}
    try:
        from services.pixel_qa_report_service import PixelQAReportService
        return jsonify(PixelQAReportService.build_report(body))
    except Exception as exc:
        return _pixel_route_error(exc, status=400)
@routes_pixel_asset.route("/api/pixel-assets/qa/report.html", methods=["GET"])
def pixel_asset_qa_report_html():
    body = {"asset_id": request.args.get("asset_id", "")}
    try:
        from services.pixel_qa_report_service import PixelQAReportService
        html_path = PixelQAReportService.write_html_report(body)
        return send_file(html_path, mimetype="text/html")
    except FileNotFoundError as exc:
        return _pixel_route_error(exc)
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/generate", methods=["POST"])
def generate_pixel_asset():
    body = request.json or {}
    dry_run = body.get("dry_run", False)
    if isinstance(dry_run, str):
        dry_run = dry_run.lower() == "true"

    try:
        if dry_run:
            plan = PixelAssetService.generate_dry_run_plan(body)
            return jsonify({"ok": True, "plan": plan})
        else:
            result = PixelAssetService.generate_pixel_asset_batch(body)
            return jsonify(result)
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/style/list", methods=["GET"])
def get_pixel_styles():
    try:
        styles = PixelAssetService.list_style_profiles()
        return jsonify({"ok": True, "styles": styles})
    except Exception as exc:
        return _pixel_route_error(exc)

@routes_pixel_asset.route("/api/pixel-assets/style/save", methods=["POST"])
def save_pixel_style():
    body = request.json or {}
    try:
        saved = PixelAssetService.save_style_profile(body)
        return jsonify({"ok": True, "style": saved})
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/style/extract", methods=["POST"])
def extract_pixel_style():
    body = request.json or {}
    try:
        saved = PixelStyleService.extract_style_profile(body)
        return jsonify({"ok": True, "style": saved})
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/style/compare", methods=["POST"])
def compare_pixel_style():
    body = request.json or {}
    try:
        match = PixelStyleService.compare_asset_to_style(body)
        return jsonify({"ok": True, "match": match})
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/history", methods=["GET"])
def get_pixel_history():
    try:
        PixelAssetService.initialize()
        query = (request.args.get("q") or "").strip().lower()
        asset_type = (request.args.get("asset_type") or request.args.get("mode") or "").strip().lower()
        limit_raw = (request.args.get("limit") or "80").strip()
        try:
            limit = max(1, min(int(limit_raw), 250))
        except ValueError:
            limit = 80

        def matches_filters(item):
            mode = str(item.get("asset_type") or item.get("mode") or item.get("type") or "").lower()
            if asset_type and mode != asset_type:
                return False
            if not query:
                return True
            searchable = " ".join(
                str(item.get(key) or "")
                for key in ("asset_id", "prompt", "role", "mode", "type", "provider")
            ).lower()
            outputs = item.get("outputs") if isinstance(item.get("outputs"), dict) else {}
            searchable += " " + " ".join(str(value) for value in outputs.values()).lower()
            return query in searchable

        history = []
        for file in ASSETS_DIR.glob("**/pixel_asset.json"):
            try:
                data = load_json(file, {})
                if data and matches_filters(data):
                    history.append(data)
            except (OSError, json.JSONDecodeError, ValueError):
                continue
        history = sorted(history, key=lambda item: item.get("created_at", ""), reverse=True)
        experiment_history = PixelAssetMemoryService.pixel_experiment_rows()
        if query:
            experiment_history = [
                row for row in experiment_history
                if query in json.dumps(row, default=str).lower()
            ]
        return jsonify({
            "ok": True,
            "history": history[:limit],
            "experiment_history": experiment_history[:limit],
            "filters": {"q": query, "asset_type": asset_type, "limit": limit},
        })
    except Exception as exc:
        return _pixel_route_error(exc)

@routes_pixel_asset.route("/api/pixel-assets/normalize", methods=["POST"])
def normalize_pixel_asset():
    body = request.json or {}
    image_path_str = body.get("path", "")

    try:
        resolved_path = _resolve_workspace_image_path(str(image_path_str or ""))
        img = Image.open(resolved_path)
        
        res_val = body.get("resolution", [32, 32])
        if isinstance(res_val, str):
            try:
                res_val = [int(x) for x in res_val.lower().split("x")]
            except Exception:
                res_val = [32, 32]
        
        norm_rules = {
            "resolution": res_val,
            "clean_alpha": body.get("clean_alpha", True),
            "quantize_palette": body.get("quantize_palette", True),
            "max_colors": int(body.get("max_colors", 24)),
            "remove_islands": body.get("remove_islands", True),
            "min_island_size": int(body.get("min_island_size", 2)),
            "outline": body.get("outline", "none")
        }

        normalized_img = PixelNormalizationService.normalize_asset(img, norm_rules)
        
        # Save normalized image adjacent to the source, e.g. as normalized.png
        output_path = resolved_path.parent / "normalized.png"
        normalized_img.save(output_path)

        relative_out = str(output_path.relative_to(ROOT)).replace("\\", "/")

        return jsonify({
            "ok": True,
            "normalized_path": relative_out,
            "resolution": res_val,
            "rules_applied": norm_rules
        })
    except Exception as exc:
        return _pixel_route_error(exc)

@routes_pixel_asset.route("/api/pixel-assets/cleanup", methods=["POST"])
def cleanup_pixel_asset():
    body = request.json or {}
    try:
        from services.pixel_cleanup_service import PixelCleanupService
        result = PixelCleanupService.cleanup_asset(body)
        return jsonify(result)
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/directions", methods=["POST"])
def generate_pixel_directions():
    body = request.json or {}
    try:
        result = PixelDirectionService.generate_directions(body)
        return jsonify(result)
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/loras", methods=["GET"])
def get_pixel_loras():
    try:
        loras = [
            {"lora_id": "pixel-art-v1", "name": "Retro Pixel Art v1", "base_model": "stable-diffusion-xl"},
            {"lora_id": "cozy-rpg-lora", "name": "Cozy RPG Style", "base_model": "stable-diffusion-xl"},
            {"lora_id": "neon-cyberpunk-lora", "name": "Cyberpunk Neon Grid", "base_model": "stable-diffusion-xl"}
        ]
        return jsonify({"ok": True, "loras": loras})
    except Exception as exc:
        return _pixel_route_error(exc)

@routes_pixel_asset.route("/api/pixel-assets/providers/capabilities", methods=["GET"])
def get_pixel_provider_capabilities():
    try:
        from services.pixel_provider_capability_service import pixel_provider_capabilities
        provider = request.args.get("provider", "")
        return jsonify(pixel_provider_capabilities(provider or None))
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/providers/plan", methods=["POST"])
def plan_pixel_provider_workflow():
    body = request.json or {}
    try:
        from services.pixel_provider_capability_service import provider_workflow_plan
        return jsonify(provider_workflow_plan(body))
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/export", methods=["GET"])
def export_pixel_batch():
    batch_id = request.args.get("batch_id", "")
    engine = request.args.get("engine", "godot")
    if not batch_id:
        return jsonify({"ok": False, "message": "batch_id parameter is required"}), 400

    try:
        zip_path = PixelExportService.export_batch_to_zip(batch_id, engine)
        if not zip_path.exists():
            return jsonify({"ok": False, "message": "Failed to compile export package"}), 500
        return send_file(
            zip_path,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{batch_id}_export_{engine}.zip"
        )
    except FileNotFoundError as exc:
        return _pixel_route_error(exc)
    except Exception as exc:
        return _pixel_route_error(exc)

@routes_pixel_asset.route("/api/pixel-assets/tileset", methods=["POST"])
def generate_pixel_tileset():
    body = request.json or {}
    try:
        result = PixelTilesetService.generate_tileset(body)
        return jsonify(result)
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/tileset/repair", methods=["POST"])
def repair_pixel_tileset_tile():
    body = request.json or {}
    try:
        result = PixelTilesetService.repair_tile_seams(body)
        return jsonify(result)
    except FileNotFoundError as exc:
        return _pixel_route_error(exc)
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

def _save_pixel_asset_edit(body):
    asset_id = body.get("asset_id", "")
    image_data = body.get("image_data", "")

    if not asset_id or not image_data:
        return None, ("Missing asset_id or image_data", 400)

    asset_dir = ASSETS_DIR / asset_id
    if not asset_dir.exists() or not asset_dir.is_dir():
        return None, (f"Asset {asset_id} not found", 404)

    import base64
    from io import BytesIO

    header, encoded = image_data.split(",", 1)
    missing_padding = len(encoded) % 4
    if missing_padding:
        encoded += "=" * (4 - missing_padding)
    data = base64.b64decode(encoded)
    img = Image.open(BytesIO(data)).convert("RGBA")

    orig_png = asset_dir / "asset.png"
    backup_png = asset_dir / "asset_before_edit.png"
    if orig_png.exists() and not backup_png.exists():
        import shutil
        shutil.copy(orig_png, backup_png)

    img.save(orig_png)

    colors_list = []
    unique_colors = img.getcolors(maxcolors=256)
    if unique_colors:
        for count_val, col in unique_colors:
            if len(col) >= 3 and (len(col) == 3 or col[3] > 0):
                hex_color = f"#{col[0]:02x}{col[1]:02x}{col[2]:02x}"
                colors_list.append(hex_color)

    meta_path = asset_dir / "pixel_asset.json"
    meta_data = {}
    if meta_path.exists():
        meta_data = load_json(meta_path, {})

    meta_data.setdefault("palette", {"max_colors": 24, "colors": []})
    meta_data.setdefault("qa", {})
    meta_data["palette"]["colors"] = colors_list[:meta_data.get("palette", {}).get("max_colors", 24)]
    meta_data["qa"]["color_count"] = len(colors_list)
    meta_data["qa"]["alpha_ok"] = True
    meta_data["qa"]["blur_score"] = 0.00

    save_json(meta_path, meta_data)
    return meta_data, None

@routes_pixel_asset.route("/api/pixel-assets/edit", methods=["POST"])
@routes_pixel_asset.route("/api/pixel-assets/edit/save", methods=["POST"])
def edit_pixel_asset():
    body = request.json or {}
    try:
        meta_data, error = _save_pixel_asset_edit(body)
        if error:
            message, status = error
            return jsonify({"ok": False, "message": message}), status
        return jsonify({"ok": True, "asset": meta_data})
    except Exception as exc:
        return _pixel_route_error(exc)

@routes_pixel_asset.route("/api/pixel-assets/version/save", methods=["POST"])
def save_pixel_asset_version():
    body = request.json or {}
    asset_id = body.get("asset_id", "")
    if not asset_id:
        return jsonify({"ok": False, "message": "asset_id is required"}), 400

    asset_dir = ASSETS_DIR / asset_id
    if not asset_dir.exists() or not asset_dir.is_dir():
        return jsonify({"ok": False, "message": f"Asset {asset_id} not found"}), 404

    try:
        import datetime as dt
        import shutil

        versions_dir = asset_dir / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        source_png = asset_dir / "asset.png"
        version_png = versions_dir / f"{asset_id}_{stamp}.png"
        if not source_png.exists():
            return jsonify({"ok": False, "message": "asset.png is missing"}), 404
        shutil.copy(source_png, version_png)

        meta_path = asset_dir / "pixel_asset.json"
        meta_data = load_json(meta_path, {}) if meta_path.exists() else {}
        meta_data.setdefault("versions", [])
        try:
            rel_version = str(version_png.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            rel_version = str(version_png)
        meta_data["versions"].append({
            "path": rel_version,
            "label": body.get("label", "manual version"),
            "created_at": dt.datetime.utcnow().isoformat() + "Z",
        })
        save_json(meta_path, meta_data)
        return jsonify({"ok": True, "asset": meta_data, "version_path": rel_version})
    except Exception as exc:
        return _pixel_route_error(exc)

@routes_pixel_asset.route("/api/pixel-assets/inpaint", methods=["POST"])
def inpaint_pixel_asset():
    body = request.json or {}
    try:
        from services.pixel_inpaint_service import PixelInpaintService
        result = PixelInpaintService.inpaint_asset(body)
        return jsonify(result)
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/part/apply", methods=["POST"])
def apply_pixel_part():
    body = request.json or {}
    try:
        from services.pixel_part_apply_service import PixelPartApplyService
        result = PixelPartApplyService.create_variants(body)
        return jsonify(result)
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/part/accept", methods=["POST"])
def accept_pixel_part_variant():
    body = request.json or {}
    try:
        from services.pixel_part_apply_service import PixelPartApplyService
        result = PixelPartApplyService.accept_variant(body)
        return jsonify(result)
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/reskin", methods=["POST"])
def reskin_pixel_asset():
    body = request.json or {}
    try:
        from services.pixel_reskin_service import PixelReskinService
        result = PixelReskinService.create_variants(body)
        return jsonify(result)
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/reskin/accept", methods=["POST"])
def accept_pixel_reskin_variant():
    body = request.json or {}
    try:
        from services.pixel_reskin_service import PixelReskinService
        result = PixelReskinService.accept_variant(body)
        return jsonify(result)
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/animate", methods=["POST"])
def animate_pixel_asset():
    body = request.json or {}
    try:
        from services.pixel_animation_service import PixelAnimationService
        result = PixelAnimationService.generate_animation(body)
        return jsonify(result)
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/animation-transfer", methods=["POST"])
def transfer_pixel_animation():
    body = request.json or {}
    try:
        from services.pixel_transfer_service import PixelTransferService
        result = PixelTransferService.transfer_animation(body)
        return jsonify(result)
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/rig/render", methods=["POST"])
@routes_pixel_asset.route("/api/pixel-assets/skeleton/render", methods=["POST"])
def render_pixel_rig():
    body = request.json or {}
    try:
        from services.pixel_rig_service import PixelRigService
        result = PixelRigService.render_rig_animation(body)
        return jsonify(result)
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/pack/generate", methods=["POST"])
@routes_pixel_asset.route("/api/pixel-assets/pack/build", methods=["POST"])
def generate_pixel_pack():
    body = request.json or {}
    try:
        from services.pixel_pack_service import PixelPackService
        result = PixelPackService.generate_pack(body)
        return jsonify(result)
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/pack/export", methods=["GET"])
def export_pixel_pack():
    pack_id = request.args.get("pack_id", "")
    try:
        from services.pixel_pack_service import PixelPackService
        zip_path = PixelPackService.export_pack_to_zip(pack_id)
        from flask import send_file
        return send_file(
            zip_path,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{pack_id}_release.zip"
        )
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/recipes", methods=["GET"])
def list_pixel_recipes():
    try:
        recipes = PixelRecipeService.list_recipes()
        return jsonify({"ok": True, "recipes": recipes})
    except Exception as exc:
        return _pixel_route_error(exc)

@routes_pixel_asset.route("/api/pixel-assets/recipes/save", methods=["POST"])
def save_pixel_recipe():
    body = request.json or {}
    try:
        recipe = PixelRecipeService.save_recipe(body)
        return jsonify({"ok": True, "recipe": recipe})
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/recipes/import", methods=["POST"])
def import_pixel_recipe():
    body = request.json or {}
    try:
        recipe = PixelRecipeService.import_recipe(body)
        return jsonify({"ok": True, "recipe": recipe})
    except Exception as exc:
        return _pixel_route_error(exc, status=400)

@routes_pixel_asset.route("/api/pixel-assets/recipes/export", methods=["GET"])
def export_pixel_recipe():
    recipe_id = request.args.get("recipe_id", "")
    if not recipe_id:
        return jsonify({"ok": False, "message": "recipe_id parameter is required"}), 400
    try:
        export_path = PixelRecipeService.export_recipe(recipe_id)
        return send_file(
            export_path,
            mimetype="application/json",
            as_attachment=True,
            download_name=f"{recipe_id}.json"
        )
    except Exception as exc:
        return _pixel_route_error(exc, status=400)
