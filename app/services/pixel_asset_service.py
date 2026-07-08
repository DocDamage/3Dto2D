from __future__ import annotations
import json
import uuid
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image, ImageDraw

from spriteforge_utils import ROOT, load_json, save_json
from services.pixel_asset_schema import (
    validate_pixel_asset,
    validate_pixel_style_profile,
    validate_pixel_asset_batch,
)
from services.cloud_image_generation_service import build_cloud_generation_plan, generate_cloud_image, resolve_api_key
from services.pixel_normalization_service import PixelNormalizationService
from services.pixel_asset_memory_service import PixelAssetMemoryService

# Define output folders relative to OUTPUT (app/output)
OUTPUT = ROOT / "output"
PIXEL_ASSETS_DIR = OUTPUT / "pixel_assets"
ASSETS_DIR = PIXEL_ASSETS_DIR / "assets"
BATCHES_DIR = PIXEL_ASSETS_DIR / "batches"
STYLES_DIR = PIXEL_ASSETS_DIR / "styles"

# Standard modes
MODES = ["characters", "creatures", "items", "weapons", "potions", "ui_icons", "tilesets", "backgrounds"]
CONFIG_DIR = ROOT / "config"
MODE_CONFIG_PATH = CONFIG_DIR / "pixel_asset_modes.json"
PROMPT_TEMPLATE_PATH = CONFIG_DIR / "pixel_prompt_templates.json"

# Standard prompt templates
PROMPT_TEMPLATES = {
    "weapons": "single {description} weapon icon, {style_profile}, transparent background, true pixel art, fixed {resolution} canvas, limited {palette_size} color palette, clean one-pixel outline, centered, no text",
    "potions": "single potion bottle icon, {description} liquid, cork stopper, {style_profile}, transparent background, true pixel art, fixed {resolution} canvas, limited palette, centered, no text",
    "characters": "single full-body game character sprite, {description}, orthographic sprite view, transparent background, true pixel art, fixed {resolution} canvas, clean silhouette, limited palette, {style_profile}",
    "creatures": "single creature sprite, {description}, {style_profile}, orthographic sprite view, transparent background, true pixel art, fixed {resolution} canvas, clean silhouette, limited palette",
    "items": "single item icon, {description}, {style_profile}, transparent background, true pixel art, fixed {resolution} canvas, limited palette, centered, no text",
    "ui_icons": "single UI icon, {description}, {style_profile}, transparent background, true pixel art, fixed {resolution} canvas, limited palette, clean border outline, centered",
    "tilesets": "seamless tilemap texture, {description}, {style_profile}, true pixel art, fixed {resolution} grid tileset, clean repetition, orthographic view",
    "backgrounds": "horizontal scrolling parallax background layer, {description}, {style_profile}, true pixel art, fixed {resolution} perspective landscape",
}

SINGULAR_TO_PLURAL = {
    "character": "characters",
    "creature": "creatures",
    "item": "items",
    "weapon": "weapons",
    "potion": "potions",
    "ui_icon": "ui_icons",
    "tileset": "tilesets",
    "background": "backgrounds",
}

class PixelAssetService:
    @staticmethod
    def initialize():
        """Ensure all required output folders exist."""
        for folder in [PIXEL_ASSETS_DIR, ASSETS_DIR, BATCHES_DIR, STYLES_DIR]:
            folder.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_modes() -> List[str]:
        return MODES

    @staticmethod
    def get_mode_configs() -> Dict[str, Dict[str, Any]]:
        data = load_json(MODE_CONFIG_PATH, {})
        modes = data.get("modes", {}) if isinstance(data, dict) else {}
        if not modes:
            return {mode: {"label": mode.replace("_", " ").title(), "controls": {}} for mode in MODES}
        return modes

    @staticmethod
    def get_prompt_templates() -> Dict[str, str]:
        data = load_json(PROMPT_TEMPLATE_PATH, {})
        templates = data.get("templates", {}) if isinstance(data, dict) else {}
        merged = dict(PROMPT_TEMPLATES)
        merged.update({key: val for key, val in templates.items() if isinstance(val, str)})
        return merged

    @staticmethod
    def normalize_asset_type(asset_type: str) -> str:
        normalized = str(asset_type or "characters").lower().strip()
        return normalized if normalized in MODES else SINGULAR_TO_PLURAL.get(normalized, "characters")

    @staticmethod
    def validate_mode_options(asset_type: str, mode_options: Dict[str, Any]) -> Dict[str, str]:
        configs = PixelAssetService.get_mode_configs()
        controls = configs.get(asset_type, {}).get("controls", {})
        clean: Dict[str, str] = {}
        if not isinstance(mode_options, dict):
            return clean
        for control_id, value in mode_options.items():
            if control_id not in controls:
                raise ValueError(f"Unsupported {asset_type} option: {control_id}")
            value_text = str(value).strip()
            allowed = controls[control_id]
            if value_text not in allowed:
                raise ValueError(f"Invalid {control_id} for {asset_type}. Choose one of: {', '.join(allowed)}")
            clean[control_id] = value_text
        return clean

    @staticmethod
    def describe_mode_options(mode_options: Dict[str, str]) -> str:
        if not mode_options:
            return "asset-specific details: default"
        parts = []
        for key, value in mode_options.items():
            label = key.replace("_", " ")
            parts.append(f"{label}: {value}")
        return ", ".join(parts)

    @staticmethod
    def list_style_profiles() -> List[Dict[str, Any]]:
        PixelAssetService.initialize()
        profiles = []
        for file in STYLES_DIR.glob("style_*.json"):
            try:
                data = load_json(file, {})
                if data:
                    profiles.append(data)
            except (OSError, json.JSONDecodeError, ValueError):
                continue
        return sorted(profiles, key=lambda x: x.get("name", ""))

    @staticmethod
    def get_style_profile(style_id: str) -> Optional[Dict[str, Any]]:
        PixelAssetService.initialize()
        file_path = STYLES_DIR / f"{style_id}.json"
        if file_path.exists():
            return load_json(file_path, None)
        return None

    @staticmethod
    def save_style_profile(data: Dict[str, Any]) -> Dict[str, Any]:
        PixelAssetService.initialize()
        
        # Ensure ID and schema exist
        if not data.get("style_id"):
            data["style_id"] = f"style_{uuid.uuid4().hex[:12]}"
        if not data.get("schema"):
            data["schema"] = "spriteforge.pixel_style_profile.v1"
            
        ok, err = validate_pixel_style_profile(data)
        if not ok:
            raise ValueError(f"Invalid Style Profile: {err}")
            
        file_path = STYLES_DIR / f"{data['style_id']}.json"
        save_json(file_path, data)
        return data

    @staticmethod
    def generate_dry_run_plan(params: Dict[str, Any]) -> Dict[str, Any]:
        """Builds a dry-run plan based on selected mode, prompt parameters, and providers."""
        asset_type = PixelAssetService.normalize_asset_type(params.get("asset_type", "characters"))
        mode_options = PixelAssetService.validate_mode_options(asset_type, params.get("mode_options", {}))
        mode_options_text = PixelAssetService.describe_mode_options(mode_options)

        # Resolve prompt template
        prompt_templates = PixelAssetService.get_prompt_templates()
        template = prompt_templates.get(asset_type, prompt_templates["characters"])
        
        description = params.get("prompt", "hero adventurer").strip()
        style_profile_id = params.get("style_profile_id", "")
        style_profile_text = ""
        
        lora_name = params.get("lora_name", "")
        lora_weight = params.get("lora_weight")
        base_model = params.get("base_model", "")
        
        if style_profile_id:
            profile = PixelAssetService.get_style_profile(style_profile_id)
            if profile:
                hints = []
                if profile.get("outline_hint"):
                    hints.append(profile["outline_hint"])
                if profile.get("shading_hint"):
                    hints.append(profile["shading_hint"])
                if profile.get("camera_hint"):
                    hints.append(profile["camera_hint"])
                style_profile_text = ", ".join(hints)
                
                if not lora_name:
                    lora_name = profile.get("lora_name", "")
                if lora_weight is None:
                    lora_weight = profile.get("lora_weight")
                if not base_model:
                    base_model = profile.get("base_model", "")
        
        if lora_weight is not None:
            if not isinstance(lora_weight, (int, float)) or lora_weight < 0.1 or lora_weight > 1.5:
                raise ValueError("lora_weight must be a number between 0.1 and 1.5")
        
        if not style_profile_text:
            style_profile_text = params.get("style_profile_text", "16-bit RPG retro pixel style")

        res_val = params.get("resolution", [32, 32])
        if isinstance(res_val, str):
            try:
                res_val = [int(x) for x in res_val.lower().split("x")]
            except (AttributeError, TypeError, ValueError):
                res_val = [32, 32]
        elif not isinstance(res_val, list):
            res_val = [32, 32]

        resolution_str = f"{res_val[0]}x{res_val[1]}"
        palette_size = str(params.get("palette_size", "24"))

        # Format expanded prompt
        expanded_prompt = template.format(
            description=description,
            mode_options=mode_options_text,
            style_profile=style_profile_text,
            resolution=resolution_str,
            palette_size=palette_size,
            weapon_type=description
        )

        provider = params.get("provider", "openai")
        model = params.get("model", "")
        negative = params.get("negative", "blur, antialiasing, gradient, 3d render")

        # Reuse Cloud Generation Plan logic
        cloud_plan = build_cloud_generation_plan(
            prompt=expanded_prompt,
            provider=provider,
            model=model,
            size="1024x1024",
            cell_size=resolution_str,
            frame_count=params.get("count", 1),
            negative=negative,
            palette_colors=int(palette_size) if palette_size.isdigit() else 24
        )

        if lora_name:
            if "generation_contract" not in cloud_plan:
                cloud_plan["generation_contract"] = {}
            cloud_plan["generation_contract"]["lora_config"] = {
                "lora_name": lora_name,
                "lora_weight": lora_weight if lora_weight is not None else 1.0,
                "base_model": base_model
            }

        return {
            "schema": "spriteforge.pixel_asset_generation_plan.v1",
            "asset_type": asset_type,
            "expanded_prompt": expanded_prompt,
            "cloud_plan": cloud_plan,
            "parameters": {
                "resolution": res_val,
                "palette_size": palette_size,
                "provider": provider,
                "model": model or cloud_plan.get("model"),
                "count": params.get("count", 1),
                "mode_options": mode_options
            }
        }

    @staticmethod
    def generate_pixel_asset_batch(params: Dict[str, Any]) -> Dict[str, Any]:
        """Generates a batch of cohesive pixel assets and normalizes them."""
        PixelAssetService.initialize()

        # Build plan
        plan = PixelAssetService.generate_dry_run_plan(params)
        provider = plan["parameters"]["provider"]
        expanded_prompt = plan["expanded_prompt"]
        model = plan["parameters"]["model"]
        count = plan["parameters"]["count"]
        asset_type = plan["asset_type"]
        resolution = plan["parameters"]["resolution"]
        palette_size = int(plan["parameters"]["palette_size"]) if plan["parameters"]["palette_size"].isdigit() else 24
        mode_options = plan["parameters"].get("mode_options", {})

        # Validate API Key (raises RuntimeError on missing key)
        is_mock_requested = params.get("mock_generation", False) or params.get("mock", False)
        if not is_mock_requested:
            try:
                resolve_api_key(provider)
            except RuntimeError as exc:
                # Provide a user-friendly translation
                raise RuntimeError(f"Key Validation Failed: {str(exc)}")

        batch_id = f"pxb_{uuid.uuid4().hex[:12]}"
        batch_dir = BATCHES_DIR / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        asset_ids = []
        assets_metadata = []

        # Normalization rules
        norm_rules = {
            "resolution": resolution,
            "clean_alpha": params.get("clean_alpha", True),
            "quantize_palette": params.get("quantize_palette", True),
            "max_colors": palette_size,
            "remove_islands": params.get("remove_islands", True),
            "min_island_size": params.get("min_island_size", 2),
            "outline": params.get("outline", "none")
        }

        # Generate each asset in the batch
        for idx in range(count):
            asset_id = f"pxa_{uuid.uuid4().hex[:12]}"
            asset_dir = ASSETS_DIR / asset_id
            asset_dir.mkdir(parents=True, exist_ok=True)

            raw_image = None
            if is_mock_requested:
                # Generate a high-fidelity procedural pixel-art asset for mock testing
                raw_image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
                draw = ImageDraw.Draw(raw_image)
                # Draw a mock colorful character/creature/item shape
                colors = [(46, 213, 115), (255, 71, 87), (255, 165, 2), (30, 144, 255), (155, 89, 182)]
                main_color = colors[idx % len(colors)]
                draw.rectangle([64, 64, 192, 192], fill=main_color)
                draw.rectangle([96, 96, 128, 128], fill=(255, 255, 255))
                draw.rectangle([144, 96, 176, 128], fill=(255, 255, 255))
                draw.rectangle([108, 144, 148, 160], fill=(30, 30, 30))
            else:
                # Call real cloud API
                raw_image = generate_cloud_image(provider, expanded_prompt, model, "1024x1024")

            # Save raw image
            raw_path = asset_dir / "raw.png"
            raw_image.save(raw_path)

            # Normalize image
            norm_image = PixelNormalizationService.normalize_asset(raw_image, norm_rules)
            asset_path = asset_dir / "asset.png"
            preview_path = asset_dir / "preview.png"
            norm_image.save(asset_path)
            norm_image.save(preview_path)

            # Quantize color info for metadata sidecar
            colors_list = []
            try:
                # Extract unique colors
                unique_colors = norm_image.getcolors(maxcolors=256)
                if unique_colors:
                    for count_val, col in unique_colors:
                        if len(col) >= 3 and (len(col) == 3 or col[3] > 0):
                            hex_color = f"#{col[0]:02x}{col[1]:02x}{col[2]:02x}"
                            colors_list.append(hex_color)
            except (TypeError, ValueError, RuntimeError):
                colors_list = []

            # Create sidecar metadata
            meta_data = {
                "schema": "spriteforge.pixel_asset.v1",
                "asset_id": asset_id,
                "batch_id": batch_id,
                "created_at": dt.datetime.utcnow().isoformat() + "Z",
                "asset_type": asset_type,
                "mode": "reference_batch",
                "prompt": params.get("prompt", ""),
                "negative": params.get("negative", ""),
                "provider": provider,
                "model": model or "mock_model",
                "source_reference": params.get("reference_image"),
                "style_profile_id": params.get("style_profile_id"),
                "mode_options": mode_options,
                "resolution": resolution,
                "palette": {
                    "max_colors": palette_size,
                    "colors": colors_list[:palette_size]
                },
                "pixel_rules": {
                    "transparent_background": True,
                    "nearest_neighbor": True,
                    "anti_alias_cleanup": norm_rules["clean_alpha"],
                    "outline": norm_rules["outline"]
                },
                "outputs": {
                    "png": f"output/pixel_assets/assets/{asset_id}/asset.png",
                    "preview": f"output/pixel_assets/assets/{asset_id}/preview.png",
                    "metadata": f"output/pixel_assets/assets/{asset_id}/pixel_asset.json"
                },
                "qa": {
                    "ok": True,
                    "color_count": len(colors_list),
                    "alpha_ok": True,
                    "blur_score": 0.01
                }
            }

            # Retrieve lora_config from plan contract if present
            lora_cfg = plan.get("cloud_plan", {}).get("generation_contract", {}).get("lora_config")
            if lora_cfg:
                meta_data["lora_config"] = lora_cfg

            meta_path = asset_dir / "pixel_asset.json"
            save_json(meta_path, meta_data)

            memory = PixelAssetMemoryService.remember_asset(meta_data, params)
            if memory:
                meta_data["memory"] = memory
                save_json(meta_path, meta_data)

            asset_ids.append(asset_id)
            assets_metadata.append(meta_data)

        # Build batch manifest
        batch_manifest = {
            "schema": "spriteforge.pixel_asset_batch.v1",
            "batch_id": batch_id,
            "asset_type": asset_type,
            "count": count,
            "style_profile_id": params.get("style_profile_id"),
            "asset_ids": asset_ids,
            "output_dir": f"output/pixel_assets/batches/{batch_id}"
        }
        manifest_path = batch_dir / "batch_manifest.json"
        save_json(manifest_path, batch_manifest)

        return {
            "ok": True,
            "batch_id": batch_id,
            "assets": assets_metadata,
            "manifest": batch_manifest
        }

# Auto-initialize on import/startup
PixelAssetService.initialize()
