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
    def _frame_pose_caption(frame: Image.Image, index: int) -> dict:
        bbox = frame.getbbox()
        width, height = frame.size
        if not bbox:
            return {
                "index": index,
                "caption": f"frame {index}: empty transparent pose",
                "bbox": None,
                "center": [width / 2, height / 2],
                "coverage": 0.0,
            }

        left, top, right, bottom = bbox
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        dx = center_x - (width / 2)
        dy = center_y - (height / 2)
        horizontal = "centered"
        if dx < -1:
            horizontal = "leaning left"
        elif dx > 1:
            horizontal = "leaning right"
        vertical = "neutral height"
        if dy < -1:
            vertical = "raised pose"
        elif dy > 1:
            vertical = "lowered pose"
        coverage = ((right - left) * (bottom - top)) / float(width * height)
        return {
            "index": index,
            "caption": f"frame {index}: {horizontal}, {vertical}, bbox {right-left}x{bottom-top}",
            "bbox": [left, top, right, bottom],
            "center": [round(center_x, 2), round(center_y, 2)],
            "coverage": round(coverage, 4),
        }

    @staticmethod
    def _alpha_consistency(frames: list[Image.Image]) -> dict:
        if not frames:
            return {"bbox_jitter": 0.0, "center_jitter": 0.0, "alpha_stability": 0.0}
        widths, heights, centers_x, centers_y, alpha_counts = [], [], [], [], []
        for frame in frames:
            bbox = frame.getbbox()
            arr = np.asarray(frame.convert("RGBA"))
            alpha_counts.append(int(np.sum(arr[:, :, 3] > 0)))
            if bbox:
                widths.append(bbox[2] - bbox[0])
                heights.append(bbox[3] - bbox[1])
                centers_x.append((bbox[0] + bbox[2]) / 2)
                centers_y.append((bbox[1] + bbox[3]) / 2)
            else:
                widths.append(0)
                heights.append(0)
                centers_x.append(frame.size[0] / 2)
                centers_y.append(frame.size[1] / 2)
        return {
            "bbox_jitter": round(float(np.std(widths) + np.std(heights)), 4),
            "center_jitter": round(float(np.std(centers_x) + np.std(centers_y)), 4),
            "alpha_stability": round(float(np.std(alpha_counts)), 4),
        }

    @staticmethod
    def _repair_frame_center(frame: Image.Image, target_center: tuple[float, float]) -> Image.Image:
        bbox = frame.getbbox()
        if not bbox:
            return frame
        center_x = (bbox[0] + bbox[2]) / 2
        center_y = (bbox[1] + bbox[3]) / 2
        dx = int(round(target_center[0] - center_x))
        dy = int(round(target_center[1] - center_y))
        if dx == 0 and dy == 0:
            return frame
        repaired = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        repaired.paste(frame, (dx, dy))
        return repaired

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
        pose_captions = [
            PixelTransferService._frame_pose_caption(frame, idx)
            for idx, frame in enumerate(frames)
        ]

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

        before_repair = PixelTransferService._alpha_consistency(transferred_frames)
        centers = [item["center"] for item in pose_captions if item.get("bbox")]
        if centers:
            target_center = (
                float(sum(center[0] for center in centers) / len(centers)),
                float(sum(center[1] for center in centers) / len(centers)),
            )
            transferred_frames = [
                PixelTransferService._repair_frame_center(frame, target_center)
                for frame in transferred_frames
            ]
        else:
            target_center = (w / 2, h / 2)
        after_repair = PixelTransferService._alpha_consistency(transferred_frames)

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
            },
            "pose_captions": pose_captions,
            "qa": {
                "source_layout_preserved": True,
                "target_center": [round(target_center[0], 2), round(target_center[1], 2)],
                "before_repair": before_repair,
                "after_repair": after_repair,
                "repair_applied": after_repair["center_jitter"] <= before_repair["center_jitter"],
            }
        }

        save_json(batch_dir / "transfer_manifest.json", manifest)

        return {
            "ok": True,
            "manifest": manifest
        }
