from flask import Blueprint, request, jsonify, send_file
import os
from pathlib import Path
from PIL import Image
from services.pixel_asset_service import PixelAssetService, ASSETS_DIR
from services.pixel_normalization_service import PixelNormalizationService
from services.pixel_direction_service import PixelDirectionService
from services.pixel_export_service import PixelExportService
from services.pixel_tileset_service import PixelTilesetService
from spriteforge_utils import load_json, ROOT, save_json

routes_pixel_asset = Blueprint("routes_pixel_asset", __name__)

@routes_pixel_asset.route("/api/pixel-assets/modes", methods=["GET"])
def get_pixel_modes():
    try:
        modes = PixelAssetService.get_modes()
        return jsonify({"ok": True, "modes": modes})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

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
        return jsonify({"ok": False, "message": str(exc)}), 400

@routes_pixel_asset.route("/api/pixel-assets/style/list", methods=["GET"])
def get_pixel_styles():
    try:
        styles = PixelAssetService.list_style_profiles()
        return jsonify({"ok": True, "styles": styles})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_pixel_asset.route("/api/pixel-assets/style/save", methods=["POST"])
def save_pixel_style():
    body = request.json or {}
    try:
        saved = PixelAssetService.save_style_profile(body)
        return jsonify({"ok": True, "style": saved})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

@routes_pixel_asset.route("/api/pixel-assets/history", methods=["GET"])
def get_pixel_history():
    try:
        PixelAssetService.initialize()
        history = []
        for file in ASSETS_DIR.glob("**/pixel_asset.json"):
            try:
                data = load_json(file, {})
                if data:
                    history.append(data)
            except Exception:
                pass
        return jsonify({"ok": True, "history": history})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_pixel_asset.route("/api/pixel-assets/normalize", methods=["POST"])
def normalize_pixel_asset():
    body = request.json or {}
    image_path_str = body.get("path", "")
    if not image_path_str:
        return jsonify({"ok": False, "message": "path is required"}), 400

    try:
        # Resolve path safely inside the workspace
        resolved_path = (ROOT / image_path_str.strip("/")).resolve()
        if not resolved_path.exists() or not resolved_path.is_file():
            return jsonify({"ok": False, "message": f"File not found: {image_path_str}"}), 404

        # Verify relative path guardrails
        try:
            resolved_path.relative_to(ROOT.resolve())
        except ValueError:
            return jsonify({"ok": False, "message": "Security error: Path must stay inside workspace"}), 403

        # Open and normalize image
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
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_pixel_asset.route("/api/pixel-assets/directions", methods=["POST"])
def generate_pixel_directions():
    body = request.json or {}
    try:
        result = PixelDirectionService.generate_directions(body)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

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
        return jsonify({"ok": False, "message": str(exc)}), 500

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
        return jsonify({"ok": False, "message": str(exc)}), 404
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_pixel_asset.route("/api/pixel-assets/tileset", methods=["POST"])
def generate_pixel_tileset():
    body = request.json or {}
    try:
        result = PixelTilesetService.generate_tileset(body)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

@routes_pixel_asset.route("/api/pixel-assets/edit", methods=["POST"])
def edit_pixel_asset():
    body = request.json or {}
    asset_id = body.get("asset_id", "")
    image_data = body.get("image_data", "")

    if not asset_id or not image_data:
        return jsonify({"ok": False, "message": "Missing asset_id or image_data"}), 400

    asset_dir = ASSETS_DIR / asset_id
    if not asset_dir.exists() or not asset_dir.is_dir():
        return jsonify({"ok": False, "message": f"Asset {asset_id} not found"}), 404

    try:
        import base64
        from io import BytesIO

        # Decode image data url
        header, encoded = image_data.split(",", 1)
        missing_padding = len(encoded) % 4
        if missing_padding:
            encoded += "=" * (4 - missing_padding)
        data = base64.b64decode(encoded)
        img = Image.open(BytesIO(data)).convert("RGBA")

        # Save backup of the original asset.png if not present
        orig_png = asset_dir / "asset.png"
        backup_png = asset_dir / "asset_before_edit.png"
        if orig_png.exists() and not backup_png.exists():
            import shutil
            shutil.copy(orig_png, backup_png)

        # Overwrite asset.png
        img.save(orig_png)

        # Extract unique colors
        colors_list = []
        unique_colors = img.getcolors(maxcolors=256)
        if unique_colors:
            for count_val, col in unique_colors:
                if len(col) >= 3 and (len(col) == 3 or col[3] > 0):
                    hex_color = f"#{col[0]:02x}{col[1]:02x}{col[2]:02x}"
                    colors_list.append(hex_color)

        # Update metadata JSON
        meta_path = asset_dir / "pixel_asset.json"
        meta_data = {}
        if meta_path.exists():
            meta_data = load_json(meta_path, {})
        
        # Populate updated attributes
        meta_data["palette"]["colors"] = colors_list[:meta_data.get("palette", {}).get("max_colors", 24)]
        meta_data["qa"]["color_count"] = len(colors_list)
        meta_data["qa"]["alpha_ok"] = True
        meta_data["qa"]["blur_score"] = 0.00 # edited pixel art is perfectly sharp

        save_json(meta_path, meta_data)

        return jsonify({"ok": True, "asset": meta_data})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

@routes_pixel_asset.route("/api/pixel-assets/inpaint", methods=["POST"])
def inpaint_pixel_asset():
    body = request.json or {}
    try:
        from services.pixel_inpaint_service import PixelInpaintService
        result = PixelInpaintService.inpaint_asset(body)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

@routes_pixel_asset.route("/api/pixel-assets/animate", methods=["POST"])
def animate_pixel_asset():
    body = request.json or {}
    try:
        from services.pixel_animation_service import PixelAnimationService
        result = PixelAnimationService.generate_animation(body)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

@routes_pixel_asset.route("/api/pixel-assets/animation-transfer", methods=["POST"])
def transfer_pixel_animation():
    body = request.json or {}
    try:
        from services.pixel_transfer_service import PixelTransferService
        result = PixelTransferService.transfer_animation(body)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

@routes_pixel_asset.route("/api/pixel-assets/rig/render", methods=["POST"])
def render_pixel_rig():
    body = request.json or {}
    try:
        from services.pixel_rig_service import PixelRigService
        result = PixelRigService.render_rig_animation(body)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

@routes_pixel_asset.route("/api/pixel-assets/pack/generate", methods=["POST"])
def generate_pixel_pack():
    body = request.json or {}
    try:
        from services.pixel_pack_service import PixelPackService
        result = PixelPackService.generate_pack(body)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

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
        return jsonify({"ok": False, "message": str(exc)}), 400
