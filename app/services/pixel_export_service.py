from __future__ import annotations
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List
from PIL import Image

from spriteforge_utils import ROOT, load_json, save_json
from services.sprite_sheet_service import pack_sheet
from services.sprite_video_loader import FrameItem

# Output folders
OUTPUT = ROOT / "output"
PIXEL_ASSETS_DIR = OUTPUT / "pixel_assets"
ASSETS_DIR = PIXEL_ASSETS_DIR / "assets"
BATCHES_DIR = PIXEL_ASSETS_DIR / "batches"

class PixelExportService:
    @staticmethod
    def export_batch_to_zip(batch_id: str, engine_type: str) -> Path:
        """Stitches and packages a batch into a game-ready ZIP for Godot, Unity, or Aseprite."""
        batch_dir = BATCHES_DIR / batch_id
        if not batch_dir.exists() or not batch_dir.is_dir():
            raise FileNotFoundError(f"Batch folder not found: {batch_id}")

        engine_type = engine_type.lower().strip()
        if engine_type not in ["godot", "unity", "aseprite"]:
            engine_type = "godot"

        # Create temporary staging directory
        staging_dir = batch_dir / f"export_{engine_type}_staging"
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)

        sheet_png_path = batch_dir / "sheet.png"
        sheet_json_path = batch_dir / "sheet.json"
        
        # If sheet files do not exist, we construct them from batch manifest
        manifest_path = batch_dir / "batch_manifest.json"
        if manifest_path.exists() and (not sheet_png_path.exists() or not sheet_json_path.exists()):
            manifest = load_json(manifest_path, {})
            asset_ids = manifest.get("asset_ids", [])
            
            frame_items = []
            resolution = [32, 32]
            for idx, asset_id in enumerate(asset_ids):
                asset_json_path = ASSETS_DIR / asset_id / "pixel_asset.json"
                asset_img_path = ASSETS_DIR / asset_id / "asset.png"
                if asset_json_path.exists() and asset_img_path.exists():
                    meta = load_json(asset_json_path, {})
                    resolution = meta.get("resolution", [32, 32])
                    img = Image.open(asset_img_path).convert("RGBA")
                    frame_items.append(FrameItem(image=img, name=f"frame_{idx}", source_index=idx))

            if frame_items:
                packed_image, cols, rows, rects = pack_sheet(
                    frame_items, columns=len(frame_items), spacing=0, margin=0, power_of_two=False
                )
                
                sheet_png_path = staging_dir / "sheet.png"
                packed_image.save(sheet_png_path)

                sheet_meta = {
                    "image": "sheet.png",
                    "frame_width": resolution[0],
                    "frame_height": resolution[1],
                    "frame_count": len(frame_items),
                    "columns": cols,
                    "rows": rows,
                    "frames": [
                        {
                            "index": r.source_index,
                            "name": r.name,
                            "x": rect["x"],
                            "y": rect["y"],
                            "w": rect["w"],
                            "h": rect["h"]
                        }
                        for r, rect in zip(frame_items, rects)
                    ]
                }
                sheet_json_path = staging_dir / "sheet.json"
                save_json(sheet_json_path, sheet_meta)
            else:
                raise RuntimeError("No frames found to export inside batch manifest")
        else:
            # Copy existing sheet files from batch directory
            if sheet_png_path.exists():
                shutil.copy(sheet_png_path, staging_dir / "sheet.png")
            if sheet_json_path.exists():
                shutil.copy(sheet_json_path, staging_dir / "sheet.json")

        # Load sheet.json to resolve layout metrics
        sheet_meta_file = staging_dir / "sheet.json"
        if not sheet_meta_file.exists():
            raise FileNotFoundError("Could not generate or locate sheet.json for export staging")

        sheet_meta = load_json(sheet_meta_file, {})
        frame_width = sheet_meta.get("frame_width", 32)
        frame_height = sheet_meta.get("frame_height", 32)
        frame_count = sheet_meta.get("frame_count", 4)
        columns = sheet_meta.get("columns", 4)
        rows = sheet_meta.get("rows", 1)

        # Generate engine specific notes and import tags
        if engine_type == "godot":
            notes_file = staging_dir / "godot_notes.txt"
            notes_file.write_text(
                f"SpriteForge Godot notes\n\n"
                f"Sprite2D setup:\n- Texture: sheet.png\n- hframes: {columns}\n- vframes: {rows}\n"
                f"- Frame range: 0 to {frame_count - 1}\n- Cell size: {frame_width}x{frame_height}\n\n"
                f"For AnimatedSprite2D:\n- Create SpriteFrames resource.\n- Add animation.\n"
                f"- Add frames from sheet.png using a {frame_width}x{frame_height} grid.\n",
                encoding="utf-8"
            )

            import_file = staging_dir / "sheet.png.import"
            import_file.write_text(
                f"[remap]\n\n"
                f"importer=\"texture\"\n"
                f"type=\"CompressedTexture2D\"\n"
                f"uid=\"uid://sf_{batch_id[:6]}\"\n"
                f"path=\"res://.godot/imported/sheet.png-sf_{batch_id[:6]}.ctex\"\n\n"
                f"[params]\n\n"
                f"compress/mode=0\n"
                f"mipmaps/generate=false\n"
                f"process/fix_alpha_border=true\n"
                f"process/premult_alpha=false\n"
                f"process/normal_map_invert_y=false\n"
                f"process/hdr_as_srgb=false\n"
                f"process/hdr_clamp_exposure=false\n"
                f"process/size_limit=0\n"
                f"detect_3d/compress_to=1\n",
                encoding="utf-8"
            )

        elif engine_type == "unity":
            meta_file = staging_dir / "sheet.png.meta"
            meta_file.write_text(
                f"fileFormatVersion: 2\n"
                f"guid: sf{batch_id[:16]}\n"
                f"TextureImporter:\n"
                f"  internalIDToNameTable: []\n"
                f"  externalObjects: {{}}\n"
                f"  serializedVersion: 12\n"
                f"  mipmaps:\n"
                f"    mipMapMode: 0\n"
                f"    enableMipMap: 0\n"
                f"    sRGBTexture: 1\n"
                f"  textureSettings:\n"
                f"    textureType: 8\n"
                f"    spriteMode: 2\n"
                f"    spritePixelsToUnits: 100\n"
                f"    spritePivot: {{x: 0.5, y: 0.5}}\n"
                f"    spriteBorder: {{x: 0, y: 0, z: 0, w: 0}}\n"
                f"    spriteGenerateMipmap: 0\n"
                f"  spriteSheet:\n"
                f"    serializedVersion: 2\n"
                f"    sprites: []\n",
                encoding="utf-8"
            )

        elif engine_type == "aseprite":
            aseprite_json = {
                "frames": {
                    frame["name"]: {
                        "frame": {
                            "x": frame["x"],
                            "y": frame["y"],
                            "w": frame["w"],
                            "h": frame["h"]
                        },
                        "rotated": False,
                        "trimmed": False,
                        "spriteSourceSize": { "x": 0, "y": 0, "w": frame_width, "h": frame_height },
                        "sourceSize": { "w": frame_width, "h": frame_height },
                        "duration": 100
                    }
                    for frame in sheet_meta.get("frames", [])
                },
                "meta": {
                    "app": "SpriteForge Studio",
                    "version": "12.0",
                    "image": "sheet.png",
                    "format": "RGBA8888",
                    "size": {
                        "w": frame_width * columns,
                        "h": frame_height * rows
                    },
                    "scale": "1"
                }
            }
            save_json(staging_dir / "sheet_aseprite.json", aseprite_json)

        # Build ZIP file
        zip_path = batch_dir / f"export_{engine_type}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in staging_dir.iterdir():
                if item.is_file():
                    zf.write(item, arcname=item.name)

        # Cleanup staging folder
        shutil.rmtree(staging_dir)

        return zip_path
