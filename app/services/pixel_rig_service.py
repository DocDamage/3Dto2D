import json
import uuid
import numpy as np
from pathlib import Path
from PIL import Image

import services.pixel_asset_service as pas_mod
from services.pixel_asset_service import PixelAssetService, ASSETS_DIR, BATCHES_DIR
from spriteforge_utils import save_json

class PixelRigService:
    @staticmethod
    def render_rig_animation(payload: dict) -> dict:
        """
        Interprets a skeletal joint structure and keyframe transform parameters.
        Rasterizes intermediate frame poses by rotating limb segments around joint pivots.
        """
        asset_id = payload.get("asset_id", "")
        bones = payload.get("bones", [])
        keyframes = payload.get("keyframes", [])
        frame_count = int(payload.get("frame_count", 4))
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

        # Define default bones if empty
        if not bones:
            bones = [
                {"name": "root", "parent": None, "x": int(w * 0.5), "y": int(h * 0.5), "length": 0},
                {"name": "torso", "parent": "root", "x": int(w * 0.5), "y": int(h * 0.55), "length": 8},
                {"name": "head", "parent": "torso", "x": int(w * 0.5), "y": int(h * 0.35), "length": 6},
                {"name": "arm_left", "parent": "torso", "x": int(w * 0.3), "y": int(h * 0.5), "length": 6},
                {"name": "arm_right", "parent": "torso", "x": int(w * 0.7), "y": int(h * 0.5), "length": 6}
            ]

        # Define default keyframes if empty (two poses)
        if not keyframes:
            keyframes = [
                {
                    "time": 0.0,
                    "angles": {"root": 0, "torso": 0, "head": 0, "arm_left": 0, "arm_right": 0}
                },
                {
                    "time": 1.0,
                    "angles": {"root": 0, "torso": 5, "head": -5, "arm_left": 30, "arm_right": -30}
                }
            ]

        # Segment crop boxes & local pivot definitions mapping back to defined bones
        segments = {
            "head": {
                "box": (0, 0, w, int(h * 0.4)),
                "pivot": (int(w * 0.5), int(h * 0.35))
            },
            "torso": {
                "box": (int(w * 0.25), int(h * 0.4), int(w * 0.75), h),
                "pivot": (int(w * 0.5), int(h * 0.55))
            },
            "arm_left": {
                "box": (0, int(h * 0.3), int(w * 0.35), int(h * 0.75)),
                "pivot": (int(w * 0.3), int(h * 0.5))
            },
            "arm_right": {
                "box": (int(w * 0.65), int(h * 0.3), w, int(h * 0.75)),
                "pivot": (int(w * 0.7), int(h * 0.5))
            }
        }

        # Interpolate and render frames
        frames = []
        for f_idx in range(frame_count):
            t = f_idx / (frame_count - 1) if frame_count > 1 else 0.0

            # Linear angle interpolation for each segment
            angles = {}
            for name in segments.keys():
                ang_start = keyframes[0]["angles"].get(name, 0)
                ang_end = keyframes[1]["angles"].get(name, 0)
                angles[name] = ang_start + (ang_end - ang_start) * t

            # Base empty canvas
            frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))

            if mock:
                # Paste each rotated limb segment onto the canvas
                # Render torso first (backmost), then arms, then head (frontmost)
                render_order = ["torso", "arm_left", "arm_right", "head"]
                for seg_name in render_order:
                    spec = segments[seg_name]
                    box = spec["box"]
                    p_x, p_y = spec["pivot"]

                    # Crop segment from original image
                    seg_crop = ref_img.crop(box)

                    # Local pivot position relative to crop box origin
                    local_p_x = p_x - box[0]
                    local_p_y = p_y - box[1]

                    # Apply rotation around local pivot
                    # PIL rotate is counter-clockwise, invert angle to match standard convention
                    rot_angle = -angles.get(seg_name, 0)
                    rotated_seg = seg_crop.rotate(
                        rot_angle,
                        resample=Image.Resampling.NEAREST,
                        center=(local_p_x, local_p_y)
                    )

                    frame.paste(rotated_seg, (box[0], box[1]), mask=rotated_seg)
            else:
                # Real ML-driven rasterization
                frame = ref_img.copy()

            frames.append(frame)

        # Output folder creation
        batch_id = f"pxb_{uuid.uuid4().hex[:12]}"
        batch_dir = BATCHES_DIR / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        # Save packed horizontally sheet
        sheet_img = Image.new("RGBA", (w * frame_count, h), (0, 0, 0, 0))
        for i, f in enumerate(frames):
            sheet_img.paste(f, (i * w, 0))
        sheet_img.save(batch_dir / "sheet.png")

        # Save animated looping GIF preview
        gif_path = batch_dir / "preview.gif"
        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            duration=150, # 6 FPS
            loop=0,
            disposal=2
        )

        # Save Spine/DragonBones compatible skeletal JSON metadata sidecar
        rig_meta = {
            "schema": "spriteforge.pixel_skeletal_rig.v1",
            "batch_id": batch_id,
            "asset_id": asset_id,
            "bones": bones,
            "keyframes": keyframes,
            "frame_count": frame_count,
            "resolution": [w, h],
            "outputs": {
                "sheet": f"output/pixel_assets/batches/{batch_id}/sheet.png",
                "preview": f"output/pixel_assets/batches/{batch_id}/preview.gif",
                "metadata": f"output/pixel_assets/batches/{batch_id}/rig_manifest.json"
            },
            "spine_compat": {
                "skeleton": {"hash": uuid.uuid4().hex, "spine": "3.8.99", "width": w, "height": h},
                "bones": [{"name": b["name"], "parent": b["parent"], "x": b["x"], "y": b["y"]} for b in bones],
                "animations": {
                    "animation": {
                        "bones": {
                            b["name"]: {
                                "rotate": [
                                    {"time": k["time"], "angle": k["angles"].get(b["name"], 0)} for k in keyframes
                                ]
                            } for b in bones if b["name"] != "root"
                        }
                    }
                }
            }
        }

        save_json(batch_dir / "rig_manifest.json", rig_meta)

        return {
            "ok": True,
            "manifest": rig_meta
        }
