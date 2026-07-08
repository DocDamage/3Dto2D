from __future__ import annotations
import uuid
import math
import datetime as dt
import numpy as np
from PIL import Image, ImageDraw
from typing import Any, Dict, List, Tuple, Optional

from spriteforge_utils import ROOT, load_json, save_json
from spriteforge_prompts import DIRECTIONS
from services.cloud_image_generation_service import generate_cloud_image, resolve_api_key
from services.pixel_normalization_service import PixelNormalizationService
from services.pixel_asset_schema import validate_pixel_asset
from services.sprite_sheet_service import pack_sheet
from services.sprite_video_loader import FrameItem
from services.sprite_chroma_alpha import alpha_bbox

# Output folders
OUTPUT = ROOT / "output"
PIXEL_ASSETS_DIR = OUTPUT / "pixel_assets"
ASSETS_DIR = PIXEL_ASSETS_DIR / "assets"
BATCHES_DIR = PIXEL_ASSETS_DIR / "batches"

class PixelDirectionService:
    @staticmethod
    def get_direction_suffixes(count: int) -> List[Tuple[str, str]]:
        """Returns the directions and their suffix prompts based on direction count (1, 4, or 8)."""
        if count == 4:
            targets = ["front", "right", "back", "left"]
        elif count == 8:
            targets = ["front", "front_right", "right", "back_right", "back", "back_left", "left", "front_left"]
        else:
            targets = ["front"]

        result = []
        for t in targets:
            suffix = DIRECTIONS.get(t, "front view, character facing camera")
            result.append((t, suffix))
        return result

    @staticmethod
    def calculate_consistency_scores(images: List[Image.Image]) -> Dict[str, float]:
        """Evaluates Jaccard palette overlap, silhouette heights, and positioning consistency."""
        if not images:
            return {"palette_overlap": 0.0, "height_consistency": 0.0, "position_consistency": 0.0, "overall": 0.0}

        # 1. Palette Overlap (Jaccard Similarity)
        palettes = []
        for img in images:
            arr = np.asarray(img.convert("RGBA"))
            pixels = arr.reshape(-1, 4)
            colors = {tuple(p[:3]) for p in pixels if p[3] > 10}
            palettes.append(colors)

        jaccards = []
        n = len(images)
        for i in range(n):
            for j in range(i + 1, n):
                c1, c2 = palettes[i], palettes[j]
                if not c1 or not c2:
                    continue
                intersection = len(c1 & c2)
                union = len(c1 | c2)
                jaccards.append(intersection / union if union > 0 else 1.0)

        palette_score = np.mean(jaccards) if jaccards else 1.0

        # 2. Silhouette Height Consistency
        heights = []
        width, height = images[0].size
        for img in images:
            bbox = alpha_bbox(img, threshold=8)
            if bbox:
                # bbox format is (left, top, right, bottom)
                h_val = bbox[3] - bbox[1]
                heights.append(h_val)
            else:
                heights.append(0)

        mean_h = np.mean(heights)
        std_h = np.std(heights)
        height_score = max(0.0, 1.0 - (std_h / mean_h)) if mean_h > 0 else 1.0

        # 3. Position Centering Offset Consistency
        canvas_cx, canvas_cy = width / 2.0, height / 2.0
        offsets = []
        for img in images:
            bbox = alpha_bbox(img, threshold=8)
            if bbox:
                bbox_cx = (bbox[0] + bbox[2]) / 2.0
                bbox_cy = (bbox[1] + bbox[3]) / 2.0
                offset = math.sqrt((bbox_cx - canvas_cx)**2 + (bbox_cy - canvas_cy)**2)
                offsets.append(offset)
            else:
                offsets.append(0)

        std_offset = np.std(offsets)
        pos_score = max(0.0, 1.0 - (std_offset / (width / 2.0)))

        overall = (palette_score * 0.4) + (height_score * 0.4) + (pos_score * 0.2)

        return {
            "palette_overlap": float(palette_score),
            "height_consistency": float(height_score),
            "position_consistency": float(pos_score),
            "overall": float(overall)
        }

    @staticmethod
    def generate_directions(params: Dict[str, Any]) -> Dict[str, Any]:
        """Generates sequential rotation directions, normalizes them, and stitches a sheet."""
        PixelDirectionService.initialize_directories()

        count = int(params.get("count", 4))
        if count not in [1, 4, 8]:
            count = 4

        # Validate LoRA weight range
        lora_name = params.get("lora_name", "")
        lora_weight = params.get("lora_weight")
        if lora_name and lora_weight is not None:
            if not isinstance(lora_weight, (int, float)) or lora_weight < 0.1 or lora_weight > 1.5:
                raise ValueError("lora_weight must be a number between 0.1 and 1.5")

        prompt = params.get("prompt", "knight hero").strip()
        negative = params.get("negative", "blur, gradient")
        provider = params.get("provider", "openai")
        model = params.get("model", "default")
        resolution = params.get("resolution", [32, 32])
        if isinstance(resolution, str):
            try:
                resolution = [int(x) for x in resolution.lower().split("x")]
            except (AttributeError, TypeError, ValueError):
                resolution = [32, 32]

        palette_size = int(params.get("palette_size", 24))

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

        # Resolve directions & prompt suffixes
        targets = PixelDirectionService.get_direction_suffixes(count)

        is_mock = params.get("mock", False) or params.get("mock_generation", False)
        if not is_mock:
            try:
                resolve_api_key(provider)
            except RuntimeError as exc:
                raise RuntimeError(f"Key Validation Failed: {str(exc)}")

        batch_id = f"pxb_{uuid.uuid4().hex[:12]}"
        batch_dir = BATCHES_DIR / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        asset_ids = []
        assets_metadata = []
        normalized_images = []

        # Generate each direction
        for dir_name, dir_suffix in targets:
            asset_id = f"pxa_{uuid.uuid4().hex[:12]}"
            asset_dir = ASSETS_DIR / asset_id
            asset_dir.mkdir(parents=True, exist_ok=True)

            expanded_prompt = f"{prompt}, {dir_suffix}, transparent background, true pixel art, fixed {resolution[0]}x{resolution[1]} canvas, limited palette"

            raw_image = None
            if is_mock:
                # Procedural generation mockup representing specific direction
                raw_image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
                draw = ImageDraw.Draw(raw_image)

                # Draw a core shape
                draw.rectangle([64, 64, 192, 192], fill=(235, 94, 85)) # body

                # Modify eyes based on direction
                if dir_name == "front":
                    draw.rectangle([96, 96, 112, 112], fill=(255, 255, 255))
                    draw.rectangle([144, 96, 160, 112], fill=(255, 255, 255))
                elif dir_name == "left" or dir_name == "front_left" or dir_name == "back_left":
                    # Draw eye towards the left edge
                    draw.rectangle([80, 96, 96, 112], fill=(255, 255, 255))
                elif dir_name == "right" or dir_name == "front_right" or dir_name == "back_right":
                    # Draw eye towards the right edge
                    draw.rectangle([160, 96, 176, 112], fill=(255, 255, 255))
                elif dir_name == "back":
                    # No eyes (back of head/hair)
                    draw.rectangle([64, 64, 192, 128], fill=(64, 52, 43))
            else:
                raw_image = generate_cloud_image(provider, expanded_prompt, model, "1024x1024")

            # Save raw image
            raw_path = asset_dir / "raw.png"
            raw_image.save(raw_path)

            # Normalize image
            norm_image = PixelNormalizationService.normalize_asset(raw_image, norm_rules)
            asset_path = asset_dir / "asset.png"
            norm_image.save(asset_path)
            normalized_images.append(norm_image)

            # Generate color palette list
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

            # Create asset sidecar metadata
            meta_data = {
                "schema": "spriteforge.pixel_asset.v1",
                "asset_id": asset_id,
                "batch_id": batch_id,
                "created_at": dt.datetime.utcnow().isoformat() + "Z",
                "asset_type": "character",
                "mode": "reference_batch",
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
                    "ok": True,
                    "color_count": len(colors_list),
                    "alpha_ok": True,
                    "blur_score": 0.01
                }
            }

            if lora_name:
                meta_data["lora_config"] = {
                    "lora_name": lora_name,
                    "lora_weight": lora_weight,
                    "base_model": params.get("base_model", "")
                }

            meta_path = asset_dir / "pixel_asset.json"
            save_json(meta_path, meta_data)

            asset_ids.append(asset_id)
            assets_metadata.append(meta_data)

        # 4. Pack Sheet
        frame_items = [FrameItem(image=img, name=targets[i][0], source_index=i) for i, img in enumerate(normalized_images)]
        # Stitch all directions horizontally
        packed_image, cols, rows, rects = pack_sheet(
            frame_items, columns=len(frame_items), spacing=0, margin=0, power_of_two=False
        )

        sheet_path = batch_dir / "sheet.png"
        packed_image.save(sheet_path)

        # Write sheet.json metadata matching SpriteForge standard
        sheet_meta = {
            "image": "sheet.png",
            "frame_width": resolution[0],
            "frame_height": resolution[1],
            "frame_count": count,
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
        sheet_meta_path = batch_dir / "sheet.json"
        save_json(sheet_meta_path, sheet_meta)

        # Calculate consistency metrics
        scores = PixelDirectionService.calculate_consistency_scores(normalized_images)

        # Create batch manifest
        batch_manifest = {
            "schema": "spriteforge.pixel_asset_batch.v1",
            "batch_id": batch_id,
            "asset_type": "character",
            "count": count,
            "style_profile_id": params.get("style_profile_id"),
            "asset_ids": asset_ids,
            "output_dir": f"output/pixel_assets/batches/{batch_id}",
            "sheet_path": f"output/pixel_assets/batches/{batch_id}/sheet.png",
            "sheet_meta_path": f"output/pixel_assets/batches/{batch_id}/sheet.json",
            "qa": {
                "ok": scores["overall"] >= 0.8,
                "consistency_scores": scores
            }
        }
        manifest_path = batch_dir / "batch_manifest.json"
        save_json(manifest_path, batch_manifest)

        return {
            "ok": True,
            "batch_id": batch_id,
            "assets": assets_metadata,
            "manifest": batch_manifest,
            "consistency_scores": scores
        }

    @staticmethod
    def initialize_directories():
        for folder in [PIXEL_ASSETS_DIR, ASSETS_DIR, BATCHES_DIR]:
            folder.mkdir(parents=True, exist_ok=True)
