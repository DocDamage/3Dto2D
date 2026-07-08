import json
import uuid
import zipfile
import datetime
from pathlib import Path
from PIL import Image

import services.pixel_asset_service as pas_mod
from services.pixel_asset_service import PixelAssetService
from services.pixel_recipe_service import PixelRecipeService
from spriteforge_utils import save_json, load_json

def _get_assets_dir():
    """Indirection to pick up monkeypatched ASSETS_DIR at call time."""
    return pas_mod.ASSETS_DIR

PACKS_DIR = Path("output/pixel_assets/packs")

class PixelPackService:
    @staticmethod
    def get_recipes() -> dict:
        """Returns predefined pack recipes."""
        return {recipe["recipe_id"]: recipe["items"] for recipe in PixelRecipeService.list_recipes()}

    @staticmethod
    def generate_pack(payload: dict) -> dict:
        """
        Processes a predefined pack recipe, generates a batch of matching assets,
        and saves a unified pack_manifest.json.
        """
        recipe_type = payload.get("recipe_type", "rpg_starter")
        style_profile_id = payload.get("style_profile_id", "")
        mock = payload.get("mock", True)

        recipe = PixelRecipeService.get_recipe(recipe_type)
        recipe_items = recipe["items"]
        generated_assets = []

        # Trigger asset generation for each recipe item
        for item in recipe_items:
            # Construct standard asset payload
            asset_payload = {
                "asset_type": item["type"],
                "prompt": item["prompt"],
                "resolution": item["resolution"],
                "palette_size": "16",
                "provider": "openai",
                "count": int(item.get("count", 1)),
                "style_profile_id": style_profile_id,
                "mock": mock
            }
            # Dispatch to PixelAssetService
            res = PixelAssetService.generate_pixel_asset_batch(asset_payload)
            if res.get("ok") and res.get("assets"):
                generated_assets.extend(res["assets"])

        # Create pack folder
        pack_id = f"pxpk_{uuid.uuid4().hex[:12]}"
        pack_dir = PACKS_DIR / pack_id
        pack_dir.mkdir(parents=True, exist_ok=True)

        # Assemble manifest
        manifest = {
            "schema": "spriteforge.pixel_pack.v1",
            "pack_id": pack_id,
            "recipe_type": recipe_type,
            "recipe_name": recipe.get("name", recipe_type),
            "style_profile_id": style_profile_id,
            "assets": generated_assets,
            "created_at": datetime.datetime.utcnow().isoformat() + "Z"
        }

        manifest_path = pack_dir / "pack_manifest.json"
        save_json(manifest_path, manifest)

        return {
            "ok": True,
            "manifest": manifest
        }

    @staticmethod
    def export_pack_to_zip(pack_id: str) -> Path:
        """
        Bundles all assets inside a pack manifest into a release ZIP archive,
        including a responsive HTML catalog index.
        """
        pack_dir = PACKS_DIR / pack_id
        manifest_path = pack_dir / "pack_manifest.json"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Pack manifest not found for pack: {pack_id}")

        manifest = load_json(manifest_path, {})
        zip_path = pack_dir / f"{pack_id}_release.zip"

        assets_dir = _get_assets_dir()

        with zipfile.ZipFile(zip_path, "w") as zf:
            # 1. Add all assets files (PNG + sidecar JSON metadata)
            for index, asset in enumerate(manifest.get("assets", []), start=1):
                asset_id = asset.get("asset_id") or f"asset_{index:03d}"
                png_rel = asset["outputs"]["png"]
                json_rel = asset["outputs"]["metadata"]

                def _resolve(rel_str):
                    p = Path(rel_str)
                    if p.exists():
                        return p
                    # Fallback: strip prefix and resolve via live ASSETS_DIR
                    parts = p.parts
                    try:
                        idx = parts.index("assets") + 1
                        candidate = assets_dir.joinpath(*parts[idx:])
                        if candidate.exists():
                            return candidate
                    except (ValueError, TypeError):
                        pass
                    return None

                # PNG – scoped to asset_id subfolder to prevent name collisions
                png_path = _resolve(png_rel)
                if png_path:
                    zf.write(png_path, arcname=f"assets/{asset_id}/{png_path.name}")

                # Sidecar JSON
                json_path = _resolve(json_rel)
                if json_path:
                    zf.write(json_path, arcname=f"assets/{asset_id}/{json_path.name}")

            # 2. Add pack manifest itself
            zf.write(manifest_path, arcname="pack_manifest.json")

            # 3. Add responsive HTML catalog index
            html_content = PixelPackService._generate_html_catalog(manifest)
            html_path = pack_dir / "catalog.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            zf.write(html_path, arcname="catalog.html")

        return zip_path

    @staticmethod
    def _generate_html_catalog(manifest: dict) -> str:
        """Generates a responsive HTML catalog dashboard showing all asset thumbnails."""
        recipe_title = manifest.get("recipe_type", "RPG Starter Pack").replace("_", " ").title()
        
        cards_html = ""
        for index, asset in enumerate(manifest.get("assets", []), start=1):
            asset_id = asset.get("asset_id") or f"asset_{index:03d}"
            name = asset["prompt"].title()
            res = f"{asset['resolution'][0]}x{asset['resolution'][1]}"
            png_name = Path(asset["outputs"]["png"]).name
            cards_html += f"""
            <div class="card">
                <div class="img-container">
                    <img src="assets/{asset_id}/{png_name}" alt="{name}" />
                </div>
                <h3>{name}</h3>
                <p class="meta">Type: <strong>{asset['asset_type']}</strong> | Size: <strong>{res}</strong></p>
                <p class="id">ID: {asset['asset_id']}</p>
            </div>
            """

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{recipe_title} - SpriteForge Release</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0b0e1c;
            color: #f1f1f1;
            margin: 0;
            padding: 40px 20px;
        }}
        .header {{
            max-width: 1200px;
            margin: 0 auto 30px auto;
            border-bottom: 1px solid rgba(255,255,255,0.08);
            padding-bottom: 20px;
        }}
        h1 {{ margin: 0; color: #55f1ff; font-size: 28px; }}
        .subtitle {{ margin: 5px 0 0 0; color: #8892b0; font-size: 14px; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }}
        .card {{
            background: #0f1322;
            border: 1px solid rgba(85,241,255,0.15);
            border-radius: 12px;
            padding: 16px;
            text-align: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }}
        .img-container {{
            background: #000;
            background-image: 
                linear-gradient(45deg, #111 25%, transparent 25%), 
                linear-gradient(-45deg, #111 25%, transparent 25%), 
                linear-gradient(45deg, transparent 75%, #111 75%), 
                linear-gradient(-45deg, transparent 75%, #111 75%);
            background-size: 16px 16px;
            background-position: 0 0, 0 8px, 8px -8px, -8px 0px;
            border-radius: 8px;
            height: 120px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 12px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.04);
        }}
        .img-container img {{
            max-width: 90px;
            max-height: 90px;
            image-rendering: pixelated;
            object-fit: contain;
        }}
        h3 {{ margin: 0; font-size: 16px; color: #fff; }}
        .meta {{ font-size: 12px; color: #8892b0; margin: 6px 0 4px 0; }}
        .id {{ font-family: monospace; font-size: 11px; color: #55f1ff; opacity: 0.8; margin: 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{recipe_title} Catalog</h1>
        <p class="subtitle">Generated via SpriteForge Studio | Pack ID: {manifest['pack_id']}</p>
    </div>
    <div class="grid">
        {cards_html}
    </div>
</body>
</html>
"""
