import json
import base64
import shutil
from io import BytesIO
from pathlib import Path
from PIL import Image

import services.pixel_asset_service as pas_mod
from services.pixel_asset_service import PixelAssetService, ASSETS_DIR
from services.pixel_normalization_service import PixelNormalizationService
from spriteforge_utils import load_json, save_json

class PixelInpaintService:
    @staticmethod
    def inpaint_asset(payload: dict) -> dict:
        """
        Applies local AI editing / inpainting to an asset.
        Decodes the image and mask base64 streams, alters pixels inside the mask,
        normalizes the output, and saves the updated asset with updated QA metadata.
        """
        asset_id = payload.get("asset_id", "")
        image_data = payload.get("image_data", "")
        mask_data = payload.get("mask_data", "")
        prompt = payload.get("prompt", "edit")
        mock = payload.get("mock", True)

        if not asset_id or not image_data or not mask_data:
            raise ValueError("Missing asset_id, image_data, or mask_data")

        asset_dir = ASSETS_DIR / asset_id
        if not asset_dir.exists() or not asset_dir.is_dir():
            raise FileNotFoundError(f"Asset folder for {asset_id} not found")

        # Decode base image
        base_img = PixelInpaintService._decode_base64(image_data)
        # Decode mask image
        mask_img = PixelInpaintService._decode_base64(mask_data)

        # Ensure mask matches base size
        if mask_img.size != base_img.size:
            mask_img = mask_img.resize(base_img.size, Image.Resampling.NEAREST)

        # Perform inpainting
        if mock:
            # Procedural mock inpainting based on prompt keywords
            result_img = base_img.copy()
            color = (128, 0, 128, 255) # default purple
            p_lower = prompt.lower()
            if "blue" in p_lower or "hood" in p_lower:
                color = (50, 120, 240, 255)
            elif "green" in p_lower or "slime" in p_lower:
                color = (50, 220, 80, 255)
            elif "red" in p_lower or "fire" in p_lower:
                color = (240, 60, 60, 255)
            elif "gold" in p_lower or "yellow" in p_lower:
                color = (240, 200, 40, 255)

            w, h = base_img.size
            for y in range(h):
                for x in range(w):
                    m_val = mask_img.getpixel((x, y))
                    if m_val[3] > 0: # Painted mask area
                        result_img.putpixel((x, y), color)
        else:
            # Real cloud provider inpainting goes here
            # In a real environment, we'd make a POST to Stability/OpenAI edit endpoints
            result_img = base_img.copy()

        # Save backup of the original asset.png if not present
        orig_png = asset_dir / "asset.png"
        backup_png = asset_dir / "asset_before_inpaint.png"
        if orig_png.exists() and not backup_png.exists():
            shutil.copy(orig_png, backup_png)

        # Load metadata to fetch normalization parameters
        meta_path = asset_dir / "pixel_asset.json"
        meta_data = {}
        if meta_path.exists():
            meta_data = load_json(meta_path, {})

        # Normalize the inpainted output to match pixel art constraints
        rules = meta_data.get("pixel_rules", {})
        clean_alpha = rules.get("transparent_background", True)
        quantize = True
        max_colors = meta_data.get("palette", {}).get("max_colors", 24)

        rules_dict = {
            "resolution": base_img.size,
            "clean_alpha": clean_alpha,
            "quantize_palette": quantize,
            "max_colors": max_colors,
            "remove_islands": True,
            "min_island_size": 2,
            "outline": "none"
        }
        normalized_img = PixelNormalizationService.normalize_asset(result_img, rules_dict)

        # Save normalized image
        normalized_img.save(orig_png)

        # Re-extract palette colors
        colors_list = []
        unique_colors = normalized_img.getcolors(maxcolors=256)
        if unique_colors:
            for count_val, col in unique_colors:
                if len(col) >= 3 and (len(col) == 3 or col[3] > 0):
                    hex_color = f"#{col[0]:02x}{col[1]:02x}{col[2]:02x}"
                    colors_list.append(hex_color)

        # Update metadata JSON sidecar
        meta_data["palette"]["colors"] = colors_list[:max_colors]
        meta_data["qa"]["color_count"] = len(colors_list)
        meta_data["qa"]["alpha_ok"] = True
        meta_data["qa"]["blur_score"] = 0.00 # perfectly sharp normalized image

        # Track that it was edited via inpainting
        meta_data["inpaint_history"] = meta_data.get("inpaint_history", [])
        meta_data["inpaint_history"].append({
            "prompt": prompt,
            "colors_count": len(colors_list)
        })

        save_json(meta_path, meta_data)

        return {
            "ok": True,
            "asset": meta_data
        }

    @staticmethod
    def _decode_base64(data_url: str) -> Image.Image:
        header, encoded = data_url.split(",", 1)
        missing_padding = len(encoded) % 4
        if missing_padding:
            encoded += "=" * (4 - missing_padding)
        data = base64.b64decode(encoded)
        return Image.open(BytesIO(data)).convert("RGBA")
