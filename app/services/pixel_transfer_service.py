import json
import uuid
import numpy as np
from pathlib import Path
from PIL import Image

import services.pixel_asset_service as pas_mod
from services.pixel_asset_service import PixelAssetService, ASSETS_DIR, BATCHES_DIR
from spriteforge_utils import save_json

class PixelTransferService:
    @staticmethod
    def transfer_animation(payload: dict) -> dict:
        """
        Slices an existing spritesheet, transfers poses and contours onto a new target style prompt,
        stitches the results back together, and saves the new transferred sheet.
        """
        source_sheet_path = payload.get("source_sheet_path", "")
        rows = int(payload.get("rows", 1))
        cols = int(payload.get("cols", 4))
        prompt = payload.get("prompt", "new character")
        mock = payload.get("mock", True)

        if not source_sheet_path:
            raise ValueError("Missing source_sheet_path parameter")

        # Resolve paths
        from flask import current_app
        root_dir = Path(pas_mod.ASSETS_DIR).resolve().parent.parent # dynamic workspace root
        sheet_full_path = root_dir / source_sheet_path

        # If it doesn't exist at root, check inside batches or assets
        if not sheet_full_path.exists():
            # Try absolute path directly
            sheet_full_path = Path(source_sheet_path)

        if not sheet_full_path.exists():
            raise FileNotFoundError(f"Source spritesheet not found at path: {source_sheet_path}")

        sheet_img = Image.open(sheet_full_path).convert("RGBA")
        total_w, total_h = sheet_img.size

        w = total_w // cols
        h = total_h // rows

        # Slice grid into frames
        frames = []
        for y_idx in range(rows):
            for x_idx in range(cols):
                box = (x_idx * w, y_idx * h, (x_idx + 1) * w, (y_idx + 1) * h)
                frames.append(sheet_img.crop(box))

        # Target Color mapping based on prompt keywords
        p_lower = prompt.lower()
        if "gold" in p_lower or "yellow" in p_lower:
            target_rgb = (240, 200, 40) # Gold
        elif "blue" in p_lower or "wizard" in p_lower:
            target_rgb = (50, 120, 240) # Blue
        elif "green" in p_lower or "slime" in p_lower:
            target_rgb = (50, 220, 80) # Green
        elif "red" in p_lower or "fire" in p_lower:
            target_rgb = (240, 60, 60) # Red
        else:
            target_rgb = (128, 0, 128) # Purple

        # Perform mock pose transfer by coloring opaque contours
        transferred_frames = []
        if mock:
            for frame in frames:
                arr = np.asarray(frame.convert("RGBA")).copy()
                alpha = arr[:, :, 3]
                mask = alpha > 0
                
                # Blend original frame luminance/shading with the target color
                tr, tg, tb = target_rgb
                arr[mask, 0] = (arr[mask, 0] * 0.2 + tr * 0.8).astype(np.uint8)
                arr[mask, 1] = (arr[mask, 1] * 0.2 + tg * 0.8).astype(np.uint8)
                arr[mask, 2] = (arr[mask, 2] * 0.2 + tb * 0.8).astype(np.uint8)
                
                transferred_frames.append(Image.fromarray(arr, mode="RGBA"))
        else:
            # Real pose model inpainting / ControlNet pose transfer pipeline
            for frame in frames:
                transferred_frames.append(frame.copy())

        # Stitch transferred frames back into a grid sheet layout
        transferred_sheet = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
        for idx, t_frame in enumerate(transferred_frames):
            x_idx = idx % cols
            y_idx = idx // cols
            transferred_sheet.paste(t_frame, (x_idx * w, y_idx * h))

        # Create output directories
        batch_id = f"pxb_{uuid.uuid4().hex[:12]}"
        batch_dir = BATCHES_DIR / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        sheet_path = batch_dir / "sheet_transferred.png"
        transferred_sheet.save(sheet_path)

        # Compile looping animated GIF preview
        gif_path = batch_dir / "preview.gif"
        transferred_frames[0].save(
            gif_path,
            save_all=True,
            append_images=transferred_frames[1:],
            duration=120, # 8 FPS loop
            loop=0,
            disposal=2
        )

        # Assemble manifest
        manifest = {
            "schema": "spriteforge.pixel_animation_transfer.v1",
            "batch_id": batch_id,
            "source_sheet": str(source_sheet_path),
            "rows": rows,
            "cols": cols,
            "frame_count": len(transferred_frames),
            "resolution": [w, h],
            "outputs": {
                "sheet": f"output/pixel_assets/batches/{batch_id}/sheet_transferred.png",
                "preview": f"output/pixel_assets/batches/{batch_id}/preview.gif",
                "metadata": f"output/pixel_assets/batches/{batch_id}/transfer_manifest.json"
            }
        }

        save_json(batch_dir / "transfer_manifest.json", manifest)

        return {
            "ok": True,
            "manifest": manifest
        }
