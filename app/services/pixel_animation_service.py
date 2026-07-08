import json
import uuid
import numpy as np
from pathlib import Path
from PIL import Image

import services.pixel_asset_service as pas_mod
from services.pixel_asset_service import PixelAssetService, ASSETS_DIR, BATCHES_DIR
from spriteforge_utils import save_json

class PixelAnimationService:
    @staticmethod
    def generate_animation(payload: dict) -> dict:
        """
        Generates an animation sheet from a base sprite reference.
        Packs frames horizontally, creates a loop preview GIF, and calculates loop consistency QA metrics.
        """
        asset_id = payload.get("asset_id", "")
        action_type = payload.get("action_type", "idle")
        frame_count = int(payload.get("frame_count", 4))
        fps = int(payload.get("fps", 8))
        mock = payload.get("mock", True)

        if not asset_id:
            raise ValueError("Missing asset_id parameter")

        asset_dir = ASSETS_DIR / asset_id
        if not asset_dir.exists() or not asset_dir.is_dir():
            raise FileNotFoundError(f"Asset folder for {asset_id} not found")

        ref_path = asset_dir / "asset.png"
        if not ref_path.exists():
            raise FileNotFoundError(f"Reference image asset.png not found under {asset_id}")

        ref_img = Image.open(ref_path).convert("RGBA")
        w, h = ref_img.size

        # Generate frames
        frames = []
        if mock:
            # Procedural animation loops using sin/cos offsets
            for i in range(frame_count):
                frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                dx, dy = 0, 0
                if action_type == "walk":
                    dx = int(np.sin(i * np.pi / 2) * 2)
                    dy = int(abs(np.sin(i * np.pi / 2)) * 1)
                elif action_type == "run":
                    dx = int(np.sin(i * np.pi / 2) * 3)
                    dy = int(abs(np.sin(i * np.pi / 2)) * 2)
                elif action_type == "jump":
                    dy = -int((i * (frame_count - 1 - i)) * 1.2)
                elif action_type == "slash":
                    dx = i - (frame_count // 2)
                else: # idle bob
                    dy = 1 if (i % 2 == 1) else 0

                frame.paste(ref_img, (dx, dy))
                frames.append(frame)
        else:
            # Real generative AI frame strip pipeline goes here
            # In production, this would invoke Stable Diffusion Image-to-Image / ControlNet poses
            for i in range(frame_count):
                frames.append(ref_img.copy())

        # Compile horizontal frame strip sheet
        sheet_img = Image.new("RGBA", (w * frame_count, h), (0, 0, 0, 0))
        for i, frame in enumerate(frames):
            sheet_img.paste(frame, (i * w, 0))

        # Create output directories
        batch_id = f"pxb_{uuid.uuid4().hex[:12]}"
        batch_dir = BATCHES_DIR / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        sheet_path = batch_dir / "sheet.png"
        sheet_img.save(sheet_path)

        # Compile looping animated GIF preview
        gif_path = batch_dir / "preview.gif"
        duration_ms = int(1000 / fps)
        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=0,
            disposal=2 # clear frame backgrounds
        )

        # Calculate Frame Consistency QA Checks
        # 1. Bbox jitter
        widths, heights = [], []
        for f in frames:
            bbox = f.getbbox()
            if bbox:
                widths.append(bbox[2] - bbox[0])
                heights.append(bbox[3] - bbox[1])
            else:
                widths.append(0)
                heights.append(0)
        bbox_jitter = float(np.std(widths) + np.std(heights))

        # 2. Palette drift
        color_sets = []
        for f in frames:
            colors = f.getcolors(maxcolors=256)
            c_set = set()
            if colors:
                for count_val, col in colors:
                    if len(col) == 4 and col[3] > 0:
                        c_set.add(col[:3])
            color_sets.append(c_set)

        if color_sets:
            common = set.intersection(*color_sets)
            union = set.union(*color_sets)
            palette_drift = 1.0 - (len(common) / len(union) if union else 1.0)
        else:
            palette_drift = 0.0

        # 3. Alpha stability
        opaque_pixel_counts = []
        for f in frames:
            arr = np.asarray(f)
            opaque_pixel_counts.append(int(np.sum(arr[:, :, 3] > 128)))
        alpha_stability = float(np.std(opaque_pixel_counts))

        # 4. Loop continuity (L1 delta between first and last frame)
        arr0 = np.asarray(frames[0]).astype(float)
        arrN = np.asarray(frames[-1]).astype(float)
        loop_continuity = float(np.mean(np.abs(arr0 - arrN)) / 255.0)

        # Compile sidecar metadata JSON
        meta = {
            "schema": "spriteforge.pixel_animation.v1",
            "animation_id": f"pxan_{uuid.uuid4().hex[:12]}",
            "batch_id": batch_id,
            "action_type": action_type,
            "frame_count": frame_count,
            "fps": fps,
            "resolution": [w, h],
            "outputs": {
                "sheet": f"output/pixel_assets/batches/{batch_id}/sheet.png",
                "preview": f"output/pixel_assets/batches/{batch_id}/preview.gif",
                "metadata": f"output/pixel_assets/batches/{batch_id}/animation.json"
            },
            "qa": {
                "bbox_jitter": bbox_jitter,
                "palette_drift": palette_drift,
                "alpha_stability": alpha_stability,
                "loop_continuity": loop_continuity
            }
        }

        save_json(batch_dir / "animation.json", meta)

        return {
            "ok": True,
            "manifest": meta
        }
