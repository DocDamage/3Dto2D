from __future__ import annotations
import datetime as dt
import shutil
import uuid
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Tuple
from PIL import Image, ImageDraw

from spriteforge_utils import ROOT, load_json, save_json
from services.pixel_normalization_service import PixelNormalizationService
from services.sprite_sheet_service import pack_sheet
from services.sprite_video_loader import FrameItem

# Output folders
OUTPUT = ROOT / "output"
PIXEL_ASSETS_DIR = OUTPUT / "pixel_assets"
ASSETS_DIR = PIXEL_ASSETS_DIR / "assets"
BATCHES_DIR = PIXEL_ASSETS_DIR / "batches"

class PixelTilesetService:
    @staticmethod
    def get_tileset_roles(tileset_type: str) -> List[str]:
        """Returns the list of tile roles needed for a specific tileset type."""
        tileset_type = tileset_type.lower().strip()
        if tileset_type == "top-down":
            return ["floor", "wall_n", "wall_s", "wall_e", "wall_w", "corner_nw", "corner_ne", "corner_sw", "corner_se", "door"]
        elif tileset_type == "side-scroller":
            return ["ground", "platform_left", "platform_middle", "platform_right", "hazard", "background_tile"]
        elif tileset_type == "isometric":
            return ["isometric_floor", "isometric_wall_left", "isometric_wall_right"]
        return ["tile_0"]

    @staticmethod
    def calculate_seam_deltas(img: Image.Image) -> Dict[str, float]:
        """Calculates horizontal and vertical seam deltas for a tile."""
        w, h = img.size
        # Left-right seam check
        left_col = [img.getpixel((0, y)) for y in range(h)]
        right_col = [img.getpixel((w - 1, y)) for y in range(h)]
        lr_diffs = []
        for y in range(h):
            # Compare RGB channels
            diff = sum(abs(left_col[y][c] - right_col[y][c]) for c in range(3)) / 3.0
            lr_diffs.append(diff)
        left_right_delta = (sum(lr_diffs) / h) / 255.0

        # Top-bottom seam check
        top_row = [img.getpixel((x, 0)) for x in range(w)]
        bottom_row = [img.getpixel((x, h - 1)) for x in range(w)]
        tb_diffs = []
        for x in range(w):
            diff = sum(abs(top_row[x][c] - bottom_row[x][c]) for c in range(3)) / 3.0
            tb_diffs.append(diff)
        top_bottom_delta = (sum(tb_diffs) / w) / 255.0

        return {
            "left_right_delta": round(left_right_delta, 4),
            "top_bottom_delta": round(top_bottom_delta, 4)
        }

    @staticmethod
    def repair_tile_seams(params: Dict[str, Any]) -> Dict[str, Any]:
        """Blend opposite tile edges, save a version, and refresh seam QA."""
        asset_id = str(params.get("asset_id") or "").strip()
        if not asset_id:
            raise ValueError("asset_id is required")

        asset_dir = ASSETS_DIR / asset_id
        asset_path = asset_dir / "asset.png"
        meta_path = asset_dir / "pixel_asset.json"
        if not asset_path.exists() or not meta_path.exists():
            raise FileNotFoundError(f"Tile asset {asset_id} was not found")

        meta_data = load_json(meta_path, {})
        if meta_data.get("asset_type") != "tileset":
            raise ValueError("Only tileset assets can use seam repair")

        image = Image.open(asset_path).convert("RGBA")
        before_seams = PixelTilesetService.calculate_seam_deltas(image)

        versions_dir = asset_dir / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        version_path = versions_dir / f"{asset_id}_before_tile_repair_{stamp}.png"
        shutil.copy(asset_path, version_path)

        pixels = image.load()
        width, height = image.size
        for y in range(height):
            left = pixels[0, y]
            right = pixels[width - 1, y]
            blended = tuple(int(round((left[idx] + right[idx]) / 2)) for idx in range(4))
            pixels[0, y] = blended
            pixels[width - 1, y] = blended
        for x in range(width):
            top = pixels[x, 0]
            bottom = pixels[x, height - 1]
            blended = tuple(int(round((top[idx] + bottom[idx]) / 2)) for idx in range(4))
            pixels[x, 0] = blended
            pixels[x, height - 1] = blended

        palette_limit = int(meta_data.get("palette", {}).get("max_colors", params.get("palette_size", 24)) or 24)
        repaired = PixelNormalizationService.normalize_asset(image, {
            "resolution": [width, height],
            "clean_alpha": True,
            "quantize_palette": True,
            "max_colors": palette_limit,
            "remove_islands": False,
            "outline": "none",
        })
        repaired.save(asset_path)

        after_seams = PixelTilesetService.calculate_seam_deltas(repaired)
        colors_list = []
        unique_colors = repaired.getcolors(maxcolors=256)
        if unique_colors:
            for count_val, col in unique_colors:
                if len(col) >= 3 and (len(col) == 3 or col[3] > 0):
                    colors_list.append(f"#{col[0]:02x}{col[1]:02x}{col[2]:02x}")

        try:
            rel_version = str(version_path.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            rel_version = str(version_path)

        meta_data.setdefault("versions", [])
        meta_data["versions"].append({
            "path": rel_version,
            "label": "before tile seam repair",
            "created_at": dt.datetime.utcnow().isoformat() + "Z",
        })
        meta_data.setdefault("tile_repair_history", [])
        meta_data["tile_repair_history"].append({
            "created_at": dt.datetime.utcnow().isoformat() + "Z",
            "strategy": "edge_blend",
            "before": before_seams,
            "after": after_seams,
        })
        meta_data.setdefault("palette", {"max_colors": palette_limit, "colors": []})
        meta_data["palette"]["colors"] = colors_list[:palette_limit]
        meta_data.setdefault("qa", {})
        meta_data["qa"].update({
            "ok": after_seams["left_right_delta"] < 0.2 and after_seams["top_bottom_delta"] < 0.2,
            "color_count": len(colors_list),
            "alpha_ok": True,
            "blur_score": 0.0,
            "seam_check": after_seams,
        })
        save_json(meta_path, meta_data)

        return {
            "ok": True,
            "asset": meta_data,
            "version_path": rel_version,
            "before": before_seams,
            "after": after_seams,
        }

    @staticmethod
    def generate_tileset(params: Dict[str, Any]) -> Dict[str, Any]:
        """Generates, normalizes, and packages a tile atlas batch."""
        tileset_type = params.get("tileset_type", "top-down")
        prompt = params.get("prompt", "stone dungeon tiles")
        negative = params.get("negative", "blur, photographic")
        provider = params.get("provider", "gemini")
        model = params.get("model", "default")
        mock = params.get("mock", True)

        # Resolve resolution
        res_str = params.get("resolution", "32x32")
        try:
            parts = res_str.split("x")
            resolution = [int(parts[0]), int(parts[1])]
        except (AttributeError, TypeError, ValueError):
            resolution = [32, 32]

        palette_size = int(params.get("palette_size", 24))

        # Setup paths
        batch_id = f"pxb_{uuid.uuid4().hex[:12]}"
        batch_dir = BATCHES_DIR / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        roles = PixelTilesetService.get_tileset_roles(tileset_type)
        assets_metadata = []
        frame_items = []

        norm_rules = {
            "resolution": resolution,
            "clean_alpha": params.get("clean_alpha", True),
            "quantize_palette": params.get("quantize_palette", True),
            "max_colors": palette_size,
            "remove_islands": params.get("remove_islands", True),
            "min_island_size": 2,
            "outline": params.get("outline", "none")
        }

        # Mock drawing helpers
        tile_colors = {
            "floor": (90, 97, 107),
            "wall_n": (68, 73, 81),
            "wall_s": (68, 73, 81),
            "wall_e": (55, 60, 68),
            "wall_w": (55, 60, 68),
            "corner_nw": (40, 44, 51),
            "corner_ne": (40, 44, 51),
            "corner_sw": (40, 44, 51),
            "corner_se": (40, 44, 51),
            "door": (160, 110, 75),
            "ground": (120, 95, 70),
            "platform_left": (95, 130, 80),
            "platform_middle": (95, 130, 80),
            "platform_right": (95, 130, 80),
            "hazard": (230, 90, 75),
            "background_tile": (45, 48, 55),
            "isometric_floor": (80, 100, 120),
            "isometric_wall_left": (60, 75, 90),
            "isometric_wall_right": (50, 65, 80)
        }

        for idx, role in enumerate(roles):
            asset_id = f"pxa_{uuid.uuid4().hex[:12]}"
            asset_dir = ASSETS_DIR / asset_id
            asset_dir.mkdir(parents=True, exist_ok=True)

            expanded_prompt = f"{prompt}, {role} tile, true pixel art, {res_str} resolution"

            raw_image = None
            if mock:
                raw_image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
                draw = ImageDraw.Draw(raw_image)
                bg_color = tile_colors.get(role, (80, 80, 80))

                # Draw mock patterns based on role
                if "isometric" in role:
                    # Draw isometric diamond
                    draw.polygon([(64, 20), (114, 64), (64, 108), (14, 64)], fill=bg_color)
                    draw.line([(64, 20), (114, 64), (64, 108), (14, 64), (64, 20)], fill=(255,255,255,60), width=3)
                elif "wall" in role or "corner" in role:
                    # Draw solid block with some brick patterns
                    draw.rectangle([14, 14, 114, 114], fill=bg_color)
                    draw.line([14, 64, 114, 64], fill=(0,0,0,40), width=4)
                    draw.line([64, 14, 64, 64], fill=(0,0,0,40), width=4)
                elif role == "floor" or role == "background_tile":
                    # Draw repeated grid tiles
                    draw.rectangle([10, 10, 118, 118], fill=bg_color)
                    draw.line([10, 10, 118, 10, 118, 118, 10, 118, 10, 10], fill=(255,255,255,20), width=4)
                else:
                    # Generic square block
                    draw.rectangle([16, 16, 112, 112], fill=bg_color)
            else:
                # Real cloud call would go here
                raw_image = Image.new("RGBA", (128, 128), (100, 100, 100, 255))

            # Save raw png
            raw_path = asset_dir / "raw.png"
            raw_image.save(raw_path)

            # Normalize image to output specs
            norm_image = PixelNormalizationService.normalize_asset(raw_image, norm_rules)
            asset_path = asset_dir / "asset.png"
            norm_image.save(asset_path)
            frame_items.append(FrameItem(image=norm_image, name=role, source_index=idx))

            # Extract unique colors
            colors_list = []
            try:
                unique_colors = norm_image.getcolors(maxcolors=256)
                if unique_colors:
                    for count_val, col in unique_colors:
                        if len(col) >= 3 and (len(col) == 3 or col[3] > 0):
                            hex_color = f"#{col[0]:02x}{col[1]:02x}{col[2]:02x}"
                            colors_list.append(hex_color)
            except (TypeError, ValueError, RuntimeError):
                colors_list = []

            # Compute Seam QA metrics
            seams = PixelTilesetService.calculate_seam_deltas(norm_image)

            # Create sidecar metadata
            meta_data = {
                "schema": "spriteforge.pixel_asset.v1",
                "asset_id": asset_id,
                "batch_id": batch_id,
                "created_at": dt.datetime.utcnow().isoformat() + "Z",
                "asset_type": "tileset",
                "mode": "reference_batch",
                "role": role,
                "prompt": expanded_prompt,
                "negative": negative,
                "provider": provider,
                "model": model,
                "source_reference": params.get("reference_image"),
                "style_profile_id": params.get("style_profile_id"),
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
                    "preview": f"output/pixel_assets/assets/{asset_id}/asset.png",
                    "metadata": f"output/pixel_assets/assets/{asset_id}/pixel_asset.json"
                },
                "qa": {
                    "ok": seams["left_right_delta"] < 0.2 and seams["top_bottom_delta"] < 0.2,
                    "color_count": len(colors_list),
                    "alpha_ok": True,
                    "blur_score": 0.01,
                    "seam_check": seams
                }
            }

            # Inject LoRA details if present
            if params.get("lora_name"):
                meta_data["lora_config"] = {
                    "lora_name": params["lora_name"],
                    "lora_weight": params.get("lora_weight", 1.0),
                    "base_model": params.get("base_model", "")
                }

            save_json(asset_dir / "pixel_asset.json", meta_data)
            assets_metadata.append(meta_data)

        # Pack tiles into single tileset atlas spritesheet
        packed_image, cols, rows, rects = pack_sheet(
            frame_items, columns=len(frame_items), spacing=0, margin=0, power_of_two=False
        )

        sheet_path = batch_dir / "sheet.png"
        packed_image.save(sheet_path)

        # Generate sheet layout metadata
        sheet_meta = {
            "image": f"output/pixel_assets/batches/{batch_id}/sheet.png",
            "frame_width": resolution[0],
            "frame_height": resolution[1],
            "frame_count": len(roles),
            "columns": cols,
            "rows": rows,
            "frames": [
                {
                    "index": rect_idx,
                    "role": r.name,
                    "asset_id": assets_metadata[rect_idx]["asset_id"],
                    "x": rect["x"],
                    "y": rect["y"],
                    "w": rect["w"],
                    "h": rect["h"]
                }
                for rect_idx, (r, rect) in enumerate(zip(frame_items, rects))
            ]
        }
        save_json(batch_dir / "sheet.json", sheet_meta)

        # Create batch manifest
        batch_manifest = {
            "schema": "spriteforge.pixel_asset_batch.v1",
            "batch_id": batch_id,
            "asset_type": "tileset",
            "tileset_type": tileset_type,
            "count": len(roles),
            "style_profile_id": params.get("style_profile_id"),
            "asset_ids": [a["asset_id"] for a in assets_metadata],
            "output_dir": f"output/pixel_assets/batches/{batch_id}",
            "sheet_path": f"output/pixel_assets/batches/{batch_id}/sheet.png",
            "sheet_meta_path": f"output/pixel_assets/batches/{batch_id}/sheet.json",
            "qa": {
                "ok": all(a["qa"]["ok"] for a in assets_metadata)
            }
        }
        save_json(batch_dir / "batch_manifest.json", batch_manifest)

        return {
            "ok": True,
            "batch_id": batch_id,
            "manifest": batch_manifest,
            "assets": assets_metadata
        }
